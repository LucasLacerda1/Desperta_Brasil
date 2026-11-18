import json
from datetime import datetime

import pytest

import fabricas
from desperta.auth import services as auth_services
from desperta.ext.erros import DadosInvalidos
from desperta.ia.models import GeracaoIA
from desperta.noticias import prioridade
from desperta.noticias.models import NoticiaFonte
from desperta.noticias.services import listar_para_revisao

SENHA = "senha-de-teste"
STATUS = datetime(2024, 5, 14, 15, 30)


@pytest.fixture
def base(db):
    db.session.add_all([fabricas.legislatura(), fabricas.orgao(), fabricas.tema()])
    db.session.flush()
    db.session.add_all(
        [
            fabricas.deputado(),
            fabricas.deputado(id=2),
            fabricas.proposicao(cod_situacao=915, situacao="Aguardando Parecer", data_status=STATUS),
        ]
    )
    db.session.commit()
    return db


_contador = iter(range(1, 1000))


def _noticia(db, caso, fontes, criado_em=datetime(2026, 11, 10), **campos):
    numero = next(_contador)
    noticia = fabricas.noticia(slug=f"noticia-{numero}", criado_em=criado_em, **campos)
    db.session.add(noticia)
    db.session.flush()
    if caso:
        entrada = {"caso": caso, "proposicao_id": 2310837, "data_status": STATUS.isoformat()}
        db.session.add(
            GeracaoIA(
                noticia_id=noticia.id,
                modelo_geracao="frases-v2",
                modelo_embedding="x",
                consulta="x",
                versao_prompt="frases-v2",
                entrada=json.dumps(entrada),
                status="ok",
            )
        )
    for ordem, (tipo, ref) in enumerate(fontes, start=1):
        db.session.add(NoticiaFonte(noticia_id=noticia.id, tipo=tipo, ref_id=ref, ordem=ordem))
    db.session.commit()
    return noticia


def _nivel(db, noticia):
    return prioridade.calcular([noticia])[noticia.id]


def _votacao(db, **campos):
    db.session.add(fabricas.votacao(proposicao_id=2310837, aprovacao=True, **campos))
    db.session.commit()
    return [("votacao", campos.get("id", "2310837-8")), ("proposicao", "2310837")]


# ======================================================
# REGRAS (25.15)
# ======================================================
@pytest.mark.parametrize(
    "orgao,descricao,nivel",
    [
        ("PLEN", "Aprovado o Projeto de Lei nº 1.234, de 2024.", prioridade.ALTA),
        ("PLEN", "Aprovado o Requerimento de Urgência (Art. 155 do RICD).", prioridade.MEDIA),
        ("CCJC", "Aprovado o Projeto de Lei nº 1.234, de 2024.", prioridade.MEDIA),
        ("CCJC", "Aprovado o Requerimento n. 10/2024.", prioridade.BAIXA),
    ],
)
def test_votacao(base, orgao, descricao, nivel):
    fontes = _votacao(base, sigla_orgao=orgao, descricao=descricao)
    assert _nivel(base, _noticia(base, "votacao", fontes)).nivel == nivel


@pytest.mark.parametrize(
    "codigo,nome,nivel",
    [
        (926, "Aguardando Apreciação pelo Senado Federal", prioridade.ALTA),
        (915, "Aguardando Parecer", prioridade.MEDIA),
        (None, None, prioridade.BAIXA),
    ],
)
def test_situacao(base, codigo, nome, nivel):
    proposicao = base.session.get(fabricas.Proposicao, 2310837)
    proposicao.cod_situacao, proposicao.situacao = codigo, nome
    base.session.commit()
    calculada = _nivel(base, _noticia(base, "situacao", [("proposicao", "2310837")]))
    assert calculada.nivel == nivel
    if codigo == 926:
        assert calculada.motivos == ['marco: "Aguardando Apreciação pelo Senado Federal"']


def test_situacao_que_mudou_de_novo_depois_do_rascunho_avisa_a_equipe(base):
    noticia = _noticia(base, "situacao", [("proposicao", "2310837")])
    base.session.get(fabricas.Proposicao, 2310837).data_status = datetime(2024, 6, 1)
    base.session.commit()
    assert "a situação mudou de novo depois deste rascunho" in _nivel(base, noticia).motivos


@pytest.mark.parametrize(
    "sigla,nivel",
    [("PEC", prioridade.ALTA), ("MPV", prioridade.ALTA), ("PL", prioridade.MEDIA), ("PDL", prioridade.BAIXA)],
)
def test_proposicao_nova(base, sigla, nivel):
    base.session.get(fabricas.Proposicao, 2310837).sigla_tipo = sigla
    base.session.commit()
    assert _nivel(base, _noticia(base, "nova", [("proposicao", "2310837")])).nivel == nivel


def test_relatorio_equipe_e_caso_desconhecido(base):
    assert _nivel(base, _noticia(base, "relatorio_semanal", [], tipo="relatorio")).nivel == prioridade.ALTA
    assert _nivel(base, _noticia(base, None, [], origem="equipe")).nivel == prioridade.MEDIA
    # Seguro na duvida: sem regra, fica no meio
    sem_regra = _nivel(base, _noticia(base, None, []))
    assert (sem_regra.nivel, sem_regra.motivos) == (prioridade.MEDIA, ["sem regra para este caso"])


def test_falha_grave_da_camara_sobe_para_alta(base):
    fontes = _votacao(
        base,
        sigla_orgao="CCJC",
        descricao="Aprovado o Requerimento. Sim: 2; Não: 0; Total: 2.",
        filhos_sincronizados_em=datetime(2024, 5, 15),
    )
    base.session.add_all([fabricas.voto(tipo_voto=None), fabricas.voto(deputado_id=2, tipo_voto=None)])
    base.session.commit()
    calculada = _nivel(base, _noticia(base, "votacao", fontes))
    assert calculada.nivel == prioridade.ALTA
    assert calculada.motivos == [
        "votação de procedimento em comissão",
        "falha grave nos dados da Câmara: so_placar",
    ]


# ======================================================
# FILA
# ======================================================
@pytest.fixture
def fila(base):
    """Uma de cada nivel, criadas na ordem baixa (mais antiga), alta, media, alta (mais nova)."""
    proposicao = base.session.get(fabricas.Proposicao, 2310837)
    proposicao.sigla_tipo = "PDL"
    base.session.commit()
    baixa = _noticia(base, "nova", [("proposicao", "2310837")], criado_em=datetime(2026, 11, 1))
    alta_antiga = _noticia(base, "relatorio_semanal", [], criado_em=datetime(2026, 11, 2), tipo="relatorio")
    media = _noticia(base, None, [], criado_em=datetime(2026, 11, 3))
    alta_nova = _noticia(base, "relatorio_semanal", [], criado_em=datetime(2026, 11, 4), tipo="relatorio")
    return [baixa.id, alta_antiga.id, media.id, alta_nova.id]


def test_fila_poe_alta_primeiro_e_as_antigas_antes_dentro_do_nivel(fila):
    baixa, alta_antiga, media, alta_nova = fila
    itens, total = listar_para_revisao()
    assert total == 4 and [n.id for n in itens] == [alta_antiga, alta_nova, media, baixa]
    itens, _ = listar_para_revisao(pagina=2, por_pagina=3)
    assert [n.id for n in itens] == [baixa]


def test_fila_filtra_por_prioridade_e_ainda_ordena_so_por_data(fila):
    baixa, alta_antiga, media, alta_nova = fila
    itens, total = listar_para_revisao(prioridade="alta")
    assert total == 2 and [n.id for n in itens] == [alta_antiga, alta_nova]
    itens, total = listar_para_revisao(ordem="antigas")
    assert [n.id for n in itens] == fila
    with pytest.raises(DadosInvalidos):
        listar_para_revisao(prioridade="urgente")
    with pytest.raises(DadosInvalidos):
        listar_para_revisao(ordem="novas")


def test_rota_da_fila_mostra_a_prioridade_so_para_a_equipe(app, fila):
    auth_services.criar_administrador("Caio", "caio@desperta.org", SENHA, "editor")
    cliente = app.test_client()
    assert cliente.post("/api/auth/login", json={"email": "caio@desperta.org", "senha": SENHA}).status_code == 200
    resposta = cliente.get("/api/noticias/admin?prioridade=alta").get_json()
    assert resposta["total"] == 2
    assert resposta["itens"][0]["prioridade"] == {"nivel": "alta", "motivos": ["relatório"]}
    assert cliente.get("/api/noticias/admin?ordem=xyz").status_code == 400
    detalhe = cliente.get(f"/api/noticias/admin/{fila[0]}").get_json()
    assert detalhe["prioridade"] == {"nivel": "baixa", "motivos": ["PDL novo"]}
