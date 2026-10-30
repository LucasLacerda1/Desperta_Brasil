from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError

import fabricas
from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.db import db as _db
from desperta.noticias.services import buscar_noticias
from desperta.parlamentares.models import Bloco, BlocoPartido, Lideranca
from desperta.proposicoes.models import Proposicao, Tema
from desperta.sistema.models import Coleta
from desperta.sistema.services import ultima_coleta_concluida

PRINCIPAIS = [
    "proposicao",
    "votacao",
    "deputado",
    "partido",
    "orgao",
    "evento",
    "legislatura",
    "tema",
    "lideranca",
    "bloco",
    "frente",
]
FILHAS = [
    "proposicao_autor",
    "proposicao_tema",
    "tramitacao",
    "voto",
    "orientacao",
    "votacao_proposicao",
    "deputado_orgao",
    "bloco_partido",
    "frente_membro",
    "pauta_item",
]
COM_FILHOS = ["proposicao", "votacao", "evento", "orgao", "bloco", "frente"]

# Secao 7, com as colunas na ordem indicada
INDICES = [
    ("proposicao_tema", ["cod_tema"]),
    ("voto", ["deputado_id"]),
    ("deputado_orgao", ["orgao_id"]),
    ("bloco_partido", ["partido_id"]),
    ("frente_membro", ["deputado_id"]),
    ("votacao_proposicao", ["proposicao_id"]),
    ("visitante_tema", ["cod_tema"]),
    ("geracao_trecho", ["trecho_id"]),
    ("noticia", ["status", "publicado_em"]),
    ("noticia", ["cod_tema", "status", "publicado_em"]),
    ("noticia_fonte", ["tipo", "ref_id"]),
    ("noticia_revisao", ["noticia_id", "data_hora"]),
    ("proposicao", ["sigla_tipo", "numero", "ano"]),
    ("tramitacao", ["proposicao_id", "data_hora"]),
    ("tramitacao", ["data_hora"]),
    ("votacao", ["proposicao_id", "data"]),
    ("votacao", ["orgao_id", "data"]),
    ("votacao", ["data_hora_registro"]),
    ("evento", ["orgao_id", "data_hora_inicio"]),
    ("evento", ["situacao"]),
    ("deputado", ["id_legislatura", "sigla_partido"]),
    ("deputado", ["sigla_uf"]),
    ("lideranca", ["bancada_nome", "data_inicio"]),
    ("log_sistema", ["modulo", "data_hora"]),
    ("log_sistema", ["nivel"]),
    ("geracao_ia", ["status", "criado_em"]),
    ("visitante", ["ultimo_acesso"]),
    ("trecho_rag", ["hash_texto"]),
    ("coleta", ["recurso", "status", "finalizado_em"]),
]

ANTIGO = datetime(2020, 1, 1)


def _tabelas_do_modelo(db):
    return [t for t in inspect(db.engine).get_table_names() if not t.startswith("noticia_fts")]


def _colunas_dos_indices(db, tabela):
    return [i["column_names"] for i in inspect(db.engine).get_indexes(tabela)]


def _falha_ao_gravar(db, *objetos):
    db.session.add_all(objetos)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


# ======================================================
# ESTRUTURA
# ======================================================
def test_continuam_32_tabelas_e_42_fks(db):
    assert len(db.metadata.tables) == 32
    assert sum(len(t.foreign_keys) for t in db.metadata.tables.values()) == 42
    assert "noticia_fts" not in db.metadata.tables
    assert "noticia_fts" in inspect(db.engine).get_table_names()


def test_total_de_289_colunas(db):
    assert sum(len(t.c) for t in db.metadata.tables.values()) == 222 + 67 == 289


@pytest.mark.parametrize("tabela", PRINCIPAIS)
def test_tabelas_principais_tem_as_colunas_de_sincronizacao(db, tabela):
    colunas = db.metadata.tables[tabela].c
    for nome in ("criado_em", "atualizado_em", "sincronizado_em", "hash_origem"):
        assert colunas[nome].nullable is False


@pytest.mark.parametrize("tabela", FILHAS)
def test_tabelas_filhas_tem_sincronizado_em(db, tabela):
    colunas = db.metadata.tables[tabela].c
    assert colunas["sincronizado_em"].nullable is False
    assert "hash_origem" not in colunas


@pytest.mark.parametrize("tabela", COM_FILHOS)
def test_filhos_sincronizados_em_opcional_e_indexado(db, tabela):
    assert db.metadata.tables[tabela].c["filhos_sincronizados_em"].nullable is True
    assert ["filhos_sincronizados_em"] in _colunas_dos_indices(db, tabela)


def test_so_as_6_tabelas_tem_filhos_sincronizados_em(db):
    tabelas = {t.name for t in db.metadata.tables.values() if "filhos_sincronizados_em" in t.c}
    assert tabelas == set(COM_FILHOS)


def test_nomes_de_restricoes_e_indices_seguem_a_convencao(db):
    inspetor = inspect(db.engine)
    for tabela in _tabelas_do_modelo(db):
        assert inspetor.get_pk_constraint(tabela)["name"] == f"pk_{tabela}"
        for fk in inspetor.get_foreign_keys(tabela):
            assert fk["name"].startswith(f"fk_{tabela}_"), fk
        for ck in inspetor.get_check_constraints(tabela):
            assert ck["name"].startswith(f"ck_{tabela}_"), ck
        for uq in inspetor.get_unique_constraints(tabela):
            assert uq["name"].startswith(f"uq_{tabela}_"), uq
        for indice in inspetor.get_indexes(tabela):
            assert indice["name"].startswith(f"ix_{tabela}_"), indice


def test_nome_final_do_check_continua_igual(db):
    nomes = {c["name"] for c in inspect(db.engine).get_check_constraints("noticia")}
    assert nomes == {"ck_noticia_status", "ck_noticia_tipo", "ck_noticia_origem"}


def test_indice_automatico_so_em_pk_e_unique(db):
    # O SQLite gera sqlite_autoindex para PK e UNIQUE, mesmo com a restricao nomeada
    for tabela in _tabelas_do_modelo(db):
        for linha in db.session.execute(text(f"PRAGMA index_list('{tabela}')")):
            if linha.name.startswith("sqlite_autoindex"):
                assert linha.origin in ("pk", "u"), linha


@pytest.mark.parametrize("tabela, colunas", INDICES)
def test_indice_da_secao_7(db, tabela, colunas):
    assert colunas in _colunas_dos_indices(db, tabela)


def test_nenhum_indice_duplica_pk_ou_composto(db):
    inspetor = inspect(db.engine)
    for tabela in _tabelas_do_modelo(db):
        indices = _colunas_dos_indices(db, tabela)
        cobertos = indices + [inspetor.get_pk_constraint(tabela)["constrained_columns"]]
        for colunas in indices:
            for outro in cobertos:
                assert not (len(colunas) < len(outro) and outro[: len(colunas)] == colunas), (tabela, colunas, outro)


# ======================================================
# SQLITE
# ======================================================
def test_pragmas_em_banco_de_arquivo(tmp_path):
    class ConfigArquivo(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'teste.db'}"

    app = create_app(ConfigArquivo)
    with app.app_context():
        with _db.engine.connect() as conexao:
            assert conexao.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            assert conexao.execute(text("PRAGMA busy_timeout")).scalar() == 5000
            assert conexao.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert conexao.execute(text("PRAGMA synchronous")).scalar() == 1
        _db.engine.dispose()


# ======================================================
# SINCRONIZACAO
# ======================================================
def test_datas_sao_preenchidas_ao_inserir(db):
    db.session.add(fabricas.tema())
    db.session.commit()
    tema = db.session.scalar(db.select(Tema))
    assert tema.criado_em and tema.atualizado_em and tema.sincronizado_em


def test_atualizar_sincronizado_em_nao_muda_atualizado_em(db):
    db.session.add(fabricas.tema(atualizado_em=ANTIGO, sincronizado_em=ANTIGO))
    db.session.commit()
    tema = db.session.scalar(db.select(Tema))
    tema.sincronizado_em = datetime(2026, 1, 1)
    db.session.commit()
    db.session.expire_all()
    assert tema.atualizado_em == ANTIGO
    assert tema.sincronizado_em == datetime(2026, 1, 1)


def test_hash_origem_e_obrigatorio(db):
    _falha_ao_gravar(db, fabricas.legislatura(hash_origem=None))


def _base_lideranca(db):
    db.session.add_all([fabricas.legislatura(), fabricas.deputado()])
    db.session.commit()


def _lideranca(**campos):
    return Lideranca(
        **{
            "deputado_id": 204554,
            "bancada_nome": "PL",
            "bancada_tipo": "partido",
            "titulo": "Lider",
            "data_inicio": date(2024, 1, 1),
            "hash_origem": fabricas.HASH,
            **campos,
        }
    )


def test_lideranca_duplicada_e_barrada(db):
    _base_lideranca(db)
    db.session.add(_lideranca())
    db.session.commit()
    _falha_ao_gravar(db, _lideranca())


def test_lideranca_com_outra_data_e_aceita(db):
    _base_lideranca(db)
    db.session.add_all([_lideranca(), _lideranca(data_inicio=date(2025, 1, 1))])
    db.session.commit()
    assert len(db.session.scalars(db.select(Lideranca)).all()) == 2


def _valores(objeto):
    return {c.name: getattr(objeto, c.name) for c in objeto.__table__.c if getattr(objeto, c.name) is not None}


def test_upsert_em_proposicao_pela_pk(db):
    for ementa in ("Primeira", "Segunda"):
        valores = _valores(fabricas.proposicao(ementa=ementa))
        comando = insert(Proposicao).values(**valores)
        db.session.execute(comando.on_conflict_do_update(index_elements=["id"], set_={"ementa": ementa}))
    db.session.commit()
    proposicoes = db.session.scalars(db.select(Proposicao)).all()
    assert [p.ementa for p in proposicoes] == ["Segunda"]


def test_upsert_em_lideranca_pela_chave_natural(db):
    _base_lideranca(db)
    chave = ["deputado_id", "bancada_nome", "titulo", "data_inicio"]
    for fim in (date(2024, 6, 1), date(2024, 12, 1)):
        comando = insert(Lideranca).values(**_valores(_lideranca(data_fim=fim)))
        db.session.execute(comando.on_conflict_do_update(index_elements=chave, set_={"data_fim": fim}))
    db.session.commit()
    liderancas = db.session.scalars(db.select(Lideranca)).all()
    assert [lideranca.data_fim for lideranca in liderancas] == [date(2024, 12, 1)]


def test_remocao_de_vinculos_que_sumiram(db):
    inicio_coleta = datetime(2026, 1, 1)
    db.session.add_all([fabricas.legislatura(), *(fabricas.partido(id=i) for i in (1, 2, 3, 4))])
    db.session.flush()
    db.session.add_all(
        [
            Bloco(id=590, nome="A", federacao=False, id_legislatura=57, hash_origem=fabricas.HASH),
            Bloco(id=591, nome="B", federacao=False, id_legislatura=57, hash_origem=fabricas.HASH),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            BlocoPartido(bloco_id=590, partido_id=1, sincronizado_em=ANTIGO),
            BlocoPartido(bloco_id=590, partido_id=2, sincronizado_em=ANTIGO),
            BlocoPartido(bloco_id=590, partido_id=3, sincronizado_em=ANTIGO),
            BlocoPartido(bloco_id=591, partido_id=4, sincronizado_em=ANTIGO),
        ]
    )
    db.session.commit()

    for vinculo in db.session.scalars(
        db.select(BlocoPartido).where(BlocoPartido.bloco_id == 590, BlocoPartido.partido_id.in_([1, 2]))
    ):
        vinculo.sincronizado_em = inicio_coleta
    db.session.execute(
        db.delete(BlocoPartido).where(BlocoPartido.bloco_id == 590, BlocoPartido.sincronizado_em < inicio_coleta)
    )
    db.session.commit()

    restantes = db.session.scalars(db.select(BlocoPartido)).all()
    assert {(v.bloco_id, v.partido_id) for v in restantes} == {(590, 1), (590, 2), (591, 4)}


# ======================================================
# COLETA
# ======================================================
def test_tipo_invalido_em_coleta_e_barrado(db):
    _falha_ao_gravar(db, fabricas.coleta(tipo="rapida"))


def test_contadores_da_coleta_comecam_em_zero(db):
    db.session.add(fabricas.coleta())
    db.session.commit()
    coleta = db.session.scalar(db.select(Coleta))
    assert (coleta.requisicoes, coleta.erros_http) == (0, 0)


def test_ultima_coleta_sem_coletas(db):
    assert ultima_coleta_concluida() is None


def test_ultima_coleta_ignora_erro_e_parcial_e_filtra_por_recurso(db):
    db.session.add_all(
        [
            fabricas.coleta(finalizado_em=datetime(2026, 1, 1)),
            fabricas.coleta(finalizado_em=datetime(2026, 1, 2)),
            fabricas.coleta(recurso="votacoes", finalizado_em=datetime(2026, 1, 3)),
            fabricas.coleta(status="erro", finalizado_em=datetime(2026, 1, 4)),
            fabricas.coleta(status="parcial", finalizado_em=datetime(2026, 1, 5)),
        ]
    )
    db.session.commit()
    assert ultima_coleta_concluida() == datetime(2026, 1, 3)
    assert ultima_coleta_concluida("proposicoes") == datetime(2026, 1, 2)
    assert ultima_coleta_concluida("eventos") is None


# ======================================================
# PADROES
# ======================================================
def test_tema_sem_icone_grava_article(db):
    db.session.add(Tema(cod_tema=1, nome="Geral", hash_origem=fabricas.HASH))
    db.session.commit()
    assert db.session.scalar(db.select(Tema)).icone == "article"


def test_atualizado_em_do_administrador_muda_ao_alterar_o_nome(db):
    admin = fabricas.administrador(atualizado_em=ANTIGO)
    db.session.add(admin)
    db.session.commit()
    assert admin.atualizado_em == ANTIGO
    admin.nome = "Outro nome"
    db.session.commit()
    db.session.expire_all()
    assert admin.atualizado_em > ANTIGO


# ======================================================
# BUSCA (FTS5)
# ======================================================
PUBLICADA_EM = datetime(2024, 5, 14, 12, 0)


def _noticia(db, slug="saude", **campos):
    if db.session.get(Tema, 46) is None:
        db.session.add(fabricas.tema())
        db.session.flush()
    noticia = fabricas.noticia(
        **{
            "slug": slug,
            "titulo": "Saúde pública em debate",
            "status": "publicada",
            "publicado_em": PUBLICADA_EM,
            **campos,
        }
    )
    db.session.add(noticia)
    db.session.commit()
    return noticia


def test_busca_ignora_acentos(db):
    noticia = _noticia(db)
    assert buscar_noticias("saude") == [noticia]
    assert buscar_noticias("SAÚDE") == [noticia]


@pytest.mark.parametrize("status", ["rascunho", "em_revisao", "rejeitada", "arquivada"])
def test_busca_nao_devolve_noticia_nao_publicada(db, status):
    _noticia(db, status=status)
    assert buscar_noticias("saude") == []


def test_busca_acompanha_edicao_do_corpo(db):
    noticia = _noticia(db, corpo="palavraantiga no texto")
    assert buscar_noticias("palavraantiga") == [noticia]
    noticia.corpo = "palavranova no texto"
    db.session.commit()
    assert buscar_noticias("palavranova") == [noticia]
    assert buscar_noticias("palavraantiga") == []


def test_noticia_apagada_some_da_busca(db):
    noticia = _noticia(db)
    db.session.delete(noticia)
    db.session.commit()
    assert buscar_noticias("saude") == []


def _indice_fts(db):
    return db.session.execute(text("SELECT id, block FROM noticia_fts_data ORDER BY id")).all()


def test_somar_visualizacoes_nao_reindexa(db):
    noticia = _noticia(db)
    linhas = db.session.scalar(text("SELECT count(*) FROM noticia_fts_docsize"))
    indice = _indice_fts(db)
    alterado_em = noticia.alterado_em

    noticia.visualizacoes += 1
    db.session.commit()

    assert db.session.scalar(text("SELECT count(*) FROM noticia_fts_docsize")) == linhas
    assert _indice_fts(db) == indice
    assert noticia.alterado_em == alterado_em


def test_editar_o_texto_reindexa(db):
    noticia = _noticia(db)
    indice = _indice_fts(db)
    noticia.corpo = "outro texto"
    db.session.commit()
    assert _indice_fts(db) != indice


@pytest.mark.parametrize(
    "termo", ['"PL 1234"', "saúde*", "'", '"', "AND", "OR NOT", "NEAR(", "-", "*", "a:b", "(", "^x"]
)
def test_termo_com_caracteres_especiais_nao_gera_erro(db, termo):
    _noticia(db)
    assert isinstance(buscar_noticias(termo), list)


def test_aspas_e_asterisco_ainda_encontram_a_palavra(db):
    noticia = _noticia(db, corpo="O PL 1234 foi votado")
    assert buscar_noticias('"PL 1234"') == [noticia]
    assert buscar_noticias("saúde*") == [noticia]


@pytest.mark.parametrize("termo", ["", "   ", None])
def test_termo_vazio_devolve_lista_vazia(db, termo):
    _noticia(db)
    assert buscar_noticias(termo) == []


def test_filtro_por_periodo(db):
    noticia = _noticia(db)
    dia = PUBLICADA_EM.date()
    um_dia = timedelta(days=1)
    assert buscar_noticias("saude", inicio=dia, fim=dia) == [noticia]
    assert buscar_noticias("saude", inicio=dia + um_dia) == []
    assert buscar_noticias("saude", fim=dia - um_dia) == []
    assert buscar_noticias("saude", fim=PUBLICADA_EM - timedelta(hours=1)) == []


def test_filtro_por_tema(db):
    noticia = _noticia(db)
    db.session.add(fabricas.tema(cod_tema=47, nome="Outro"))
    db.session.commit()
    outra = _noticia(db, slug="outra", cod_tema=47)
    assert buscar_noticias("saude", cod_tema=46) == [noticia]
    assert buscar_noticias("saude", cod_tema=47) == [outra]


def test_busca_ordena_por_relevancia_e_depois_data(db):
    fraca = _noticia(db, slug="fraca", titulo="Geral", resumo="Sobre vários assuntos e saúde", corpo="x " * 200)
    forte = _noticia(db, slug="forte", titulo="Saúde", resumo="Saúde", corpo="saúde saúde saúde")
    assert buscar_noticias("saude") == [forte, fraca]

    antiga = _noticia(db, slug="igual-a", titulo="Empate", resumo="r", corpo="termoigual", publicado_em=PUBLICADA_EM)
    nova = _noticia(
        db,
        slug="igual-b",
        titulo="Empate",
        resumo="r",
        corpo="termoigual",
        publicado_em=PUBLICADA_EM + timedelta(days=1),
    )
    assert buscar_noticias("termoigual") == [nova, antiga]
