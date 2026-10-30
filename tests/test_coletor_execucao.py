from datetime import date, datetime, timedelta

import pytest

from desperta.coletor.cliente import ErroAPI
from desperta.coletor.execucao import Execucao, MAX_FALHAS_API_SEGUIDAS
from desperta.coletor.janelas import janela_incremental
from desperta.parlamentares.models import Bloco, BlocoPartido, Legislatura, Partido
from desperta.sistema.models import Coleta, LogSistema
from desperta.sistema.services import ultima_coleta_concluida

ANTIGO = datetime(2020, 1, 1)
VALORES = {"id": 57, "data_inicio": date(2023, 2, 1), "data_fim": date(2027, 1, 31)}


def _execucao(cliente, recurso="legislaturas"):
    return Execucao(cliente, recurso, "completa", f"/{recurso}")


def _coleta(db):
    return db.session.scalars(db.select(Coleta).order_by(Coleta.id.desc())).first()


def test_registro_novo_conta_em_itens_novos(db, cliente):
    with _execucao(cliente) as execucao:
        registro = execucao.principal(Legislatura, 57, VALORES)
    assert registro.hash_origem and registro.criado_em
    coleta = _coleta(db)
    assert (coleta.total_itens, coleta.itens_novos, coleta.itens_atualizados) == (1, 1, 0)
    assert coleta.status == "ok" and coleta.finalizado_em is not None


def test_hash_igual_so_marca_sincronizado_em(db, cliente):
    with _execucao(cliente) as execucao:
        execucao.principal(Legislatura, 57, VALORES)
    registro = db.session.get(Legislatura, 57)
    registro.atualizado_em = ANTIGO
    registro.sincronizado_em = ANTIGO
    db.session.commit()

    with _execucao(cliente) as execucao:
        execucao.principal(Legislatura, 57, VALORES)

    db.session.expire_all()
    assert registro.atualizado_em == ANTIGO
    assert registro.sincronizado_em > ANTIGO
    coleta = _coleta(db)
    assert (coleta.itens_novos, coleta.itens_atualizados) == (0, 0)


def test_hash_diferente_atualiza_e_conta(db, cliente):
    with _execucao(cliente) as execucao:
        execucao.principal(Legislatura, 57, VALORES)
    registro = db.session.get(Legislatura, 57)
    hash_antes = registro.hash_origem
    registro.atualizado_em = ANTIGO
    db.session.commit()

    with _execucao(cliente) as execucao:
        execucao.principal(Legislatura, 57, {**VALORES, "data_fim": date(2030, 1, 1)})

    db.session.expire_all()
    assert registro.data_fim == date(2030, 1, 1)
    assert registro.hash_origem != hash_antes
    assert registro.atualizado_em > ANTIGO
    assert _coleta(db).itens_atualizados == 1


def test_campo_obrigatorio_vazio_nao_derruba_a_coleta(db, cliente):
    """Decisao 10.2: desfaz so o registro, registra a coluna e marca a coleta como parcial."""
    with _execucao(cliente) as execucao:
        execucao.principal(Legislatura, 55, {**VALORES, "id": 55})
        assert execucao.principal(Legislatura, 56, {**VALORES, "id": 56, "data_inicio": None}) is None
        execucao.principal(Legislatura, 57, VALORES)

    db.session.rollback()
    ids = set(db.session.scalars(db.select(Legislatura.id)))
    assert ids == {55, 57}
    coleta = _coleta(db)
    assert coleta.status == "parcial"
    assert coleta.itens_novos == 2
    assert coleta.total_itens == 3
    log = db.session.scalar(db.select(LogSistema).where(LogSistema.acao == "gravar_registro"))
    assert log.nivel == "erro"
    assert log.modulo == "coletor"
    assert (log.entidade, log.entidade_id) == ("legislatura", "56")
    assert "legislatura.data_inicio" in log.descricao
    assert log.coleta_id == coleta.id


def test_falha_no_primeiro_registro_nao_afeta_os_seguintes(db, cliente):
    """O primeiro comando da transacao e o SAVEPOINT: o SQLite tem que continuar consistente."""
    with _execucao(cliente) as execucao:
        execucao.concluir_item()
        execucao.principal(Legislatura, 56, {**VALORES, "id": 56, "data_inicio": None})
        execucao.concluir_item()
        execucao.principal(Legislatura, 57, VALORES)
        execucao.concluir_item()
    db.session.rollback()
    assert set(db.session.scalars(db.select(Legislatura.id))) == {57}


def test_vinculo_novo_atualizado_e_igual(db, cliente, api):
    with _execucao(cliente, "blocos") as execucao:
        execucao.principal(Legislatura, 57, VALORES)
        execucao.principal(Partido, 1, {"id": 1, "sigla": "A", "nome": "A", "url_logo": None})
        execucao.principal(Bloco, 9, {"id": 9, "nome": "B", "federacao": False, "id_legislatura": 57})
        assert execucao.vinculo(BlocoPartido, (9, 1), {"bloco_id": 9, "partido_id": 1}) is True
    assert _coleta(db).itens_novos == 4

    with _execucao(cliente, "blocos") as execucao:
        assert execucao.vinculo(BlocoPartido, (9, 1), {"bloco_id": 9, "partido_id": 1}) is True
    coleta = _coleta(db)
    assert (coleta.itens_novos, coleta.itens_atualizados, coleta.total_itens) == (0, 0, 1)


def test_vinculo_com_fk_invalida_vira_falha(db, cliente):
    with _execucao(cliente, "blocos") as execucao:
        assert execucao.vinculo(BlocoPartido, (9, 1), {"bloco_id": 9, "partido_id": 1}) is False
    assert _coleta(db).status == "parcial"


def test_remover_sumidos_so_afeta_aquele_pai(db, cliente):
    with _execucao(cliente, "blocos") as execucao:
        execucao.principal(Legislatura, 57, VALORES)
        for id_partido in (1, 2, 3):
            execucao.principal(Partido, id_partido, {"id": id_partido, "sigla": "A", "nome": "A", "url_logo": None})
        for id_bloco in (8, 9):
            execucao.principal(Bloco, id_bloco, {"id": id_bloco, "nome": "B", "federacao": False, "id_legislatura": 57})
        for chave in [(9, 1), (9, 2), (8, 3)]:
            execucao.vinculo(BlocoPartido, chave, {"bloco_id": chave[0], "partido_id": chave[1]})

    with _execucao(cliente, "blocos") as execucao:
        execucao.vinculo(BlocoPartido, (9, 1), {"bloco_id": 9, "partido_id": 1})
        execucao.remover_sumidos(BlocoPartido, BlocoPartido.bloco_id == 9)

    restantes = {(v.bloco_id, v.partido_id) for v in db.session.scalars(db.select(BlocoPartido))}
    assert restantes == {(9, 1), (8, 3)}


def test_contadores_http_vao_para_a_coleta(db, api, cliente):
    from api_falsa import envelope

    api.responder("temas", [504, envelope([])])
    with _execucao(cliente, "temas"):
        cliente.obter("temas")
    coleta = _coleta(db)
    assert (coleta.requisicoes, coleta.erros_http) == (2, 1)


def test_contadores_sao_so_desta_coleta(db, api, cliente):
    from api_falsa import envelope

    api.responder("temas", envelope([]))
    cliente.obter("temas")
    with _execucao(cliente, "temas"):
        cliente.obter("temas")
    assert _coleta(db).requisicoes == 1


def test_api_fora_do_ar_registra_erro_sem_propagar(db, cliente):
    with _execucao(cliente, "deputados"):
        raise ErroAPI("url", "HTTP 504", 504)
    coleta = _coleta(db)
    assert coleta.status == "erro"
    assert "HTTP 504" in coleta.mensagem_erro
    assert coleta.finalizado_em is not None
    assert db.session.scalar(db.select(LogSistema).where(LogSistema.acao == "falha_api")).nivel == "erro"


def test_erro_de_programacao_nao_e_escondido(db, cliente):
    with pytest.raises(ZeroDivisionError):
        with _execucao(cliente):
            1 / 0
    assert _coleta(db).status == "erro"


def test_processar_segue_depois_de_erro_em_um_item(db, cliente):
    def falhar():
        raise ErroAPI("url", "HTTP 404", 404)

    with _execucao(cliente, "proposicoes") as execucao:
        assert execucao.processar("proposicao", 1, falhar) is False
        assert execucao.processar("proposicao", 2, lambda: None) is True
    assert _coleta(db).status == "parcial"


def test_processar_para_depois_de_varias_falhas_seguidas(db, cliente):
    tentativas = []

    def falhar():
        tentativas.append(1)
        raise ErroAPI("url", "HTTP 504", 504)

    with _execucao(cliente, "proposicoes") as execucao:
        for id_item in range(20):
            execucao.processar("proposicao", id_item, falhar)
    assert len(tentativas) == MAX_FALHAS_API_SEGUIDAS
    assert _coleta(db).status == "erro"


def test_coleta_interrompida_nao_conta_como_concluida(db, cliente):
    execucao = _execucao(cliente)
    execucao.concluir_item()
    coleta = _coleta(db)
    assert coleta.status == "parcial" and coleta.finalizado_em is None
    assert ultima_coleta_concluida() is None


# ======================================================
# JANELA INCREMENTAL
# ======================================================
HOJE = date(2026, 10, 30)


def _coleta_finalizada(db, cliente, status, fim, recurso="proposicoes"):
    execucao = Execucao(cliente, recurso, "incremental", f"/{recurso}", None, date(2026, 1, 1), fim)
    execucao.finalizar(status=status)
    db.session.commit()


def test_primeira_janela_e_de_30_dias(db):
    assert janela_incremental("proposicoes", HOJE) == (HOJE - timedelta(days=30), HOJE)


def test_janela_comeca_na_ultima_ok_com_um_dia_de_sobreposicao(db, cliente):
    _coleta_finalizada(db, cliente, "ok", date(2026, 10, 20))
    assert janela_incremental("proposicoes", HOJE) == (date(2026, 10, 19), HOJE)


@pytest.mark.parametrize("status", ["parcial", "erro"])
def test_janela_ignora_coleta_que_nao_terminou_ok(db, cliente, status):
    _coleta_finalizada(db, cliente, "ok", date(2026, 10, 20))
    _coleta_finalizada(db, cliente, status, date(2026, 10, 29))
    assert janela_incremental("proposicoes", HOJE) == (date(2026, 10, 19), HOJE)


def test_janela_e_por_recurso(db, cliente):
    _coleta_finalizada(db, cliente, "ok", date(2026, 10, 20), recurso="votacoes")
    assert janela_incremental("proposicoes", HOJE)[0] == HOJE - timedelta(days=30)
