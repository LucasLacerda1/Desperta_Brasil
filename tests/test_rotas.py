from datetime import datetime, timezone

import pytest

import fabricas
from desperta.auth import services as auth_services
from desperta.ext.api import periodo_em_utc
from desperta.ext.erros import DadosInvalidos
from desperta.ia.models import GeracaoIA
from desperta.noticias.models import Noticia, NoticiaRevisao
from desperta.proposicoes.models import Tema
from desperta.sistema.models import Coleta
from desperta.votacoes.models import Orientacao, Voto

SENHA = "senha-de-teste"


@pytest.fixture
def dados(db):
    auth_services.limpar_tentativas()
    d = fabricas.popular(db)
    d.admin.papel = "admin"
    db.session.commit()
    yield d
    auth_services.limpar_tentativas()


@pytest.fixture
def cliente(app):
    return app.test_client()


def entrar(cliente, email="lucas@desperta.org", senha=SENHA):
    return cliente.post("/api/auth/login", json={"email": email, "senha": senha})


@pytest.fixture
def admin(cliente, dados):
    assert entrar(cliente).status_code == 200
    return cliente


@pytest.fixture
def editor(db, cliente, dados):
    auth_services.criar_administrador("Caio", "caio@desperta.org", SENHA, "editor")
    assert entrar(cliente, "caio@desperta.org").status_code == 200
    return cliente


def publicar(db, noticia, quando=datetime(2026, 11, 10, 15, 0)):
    noticia.status = "publicada"
    noticia.publicado_em = quando
    db.session.commit()


# ======================================================
# LOGIN E EQUIPE
# ======================================================
def test_login_abre_a_sessao_e_logout_fecha(cliente, dados):
    assert cliente.get("/api/auth/eu").status_code == 401
    resposta = entrar(cliente)
    assert resposta.status_code == 200
    assert "senha_hash" not in resposta.get_json()["administrador"]
    assert cliente.get("/api/auth/eu").get_json()["administrador"]["email"] == "lucas@desperta.org"
    assert cliente.post("/api/auth/logout").status_code == 204
    assert cliente.get("/api/auth/eu").status_code == 401


def test_login_errado_e_sem_json(cliente, dados):
    resposta = entrar(cliente, senha="errada-123")
    assert resposta.status_code == 401
    assert resposta.get_json() == {"erro": auth_services.MENSAGEM_LOGIN}
    assert cliente.post("/api/auth/login", data="email=x").status_code == 400


def test_login_bloqueia_depois_de_muitas_falhas(app, cliente, dados):
    for _ in range(app.config["LOGIN_TENTATIVAS"]):
        entrar(cliente, senha="errada-123")
    assert entrar(cliente).status_code == 429


def test_cookie_de_sessao_e_httponly(cliente, dados):
    cabecalho = entrar(cliente).headers["Set-Cookie"]
    assert "HttpOnly" in cabecalho and "SameSite=Lax" in cabecalho


def test_desativado_perde_a_sessao_na_hora(db, admin, dados):
    auth_services.criar_administrador("Rhuan", "rhuan@desperta.org", SENHA, "admin")
    dados.admin.ativo = False
    db.session.commit()
    assert admin.get("/api/auth/eu").status_code == 401


def test_trocar_a_propria_senha_mantem_a_sessao(admin):
    resposta = admin.post("/api/auth/eu/senha", json={"senha_atual": SENHA, "senha_nova": "outra-senha-1"})
    assert resposta.status_code == 204
    assert admin.get("/api/auth/eu").status_code == 200


def test_trocar_senha_sem_a_nova_da_400(admin):
    assert admin.post("/api/auth/eu/senha", json={"senha_atual": SENHA}).status_code == 400


def test_admin_cria_lista_e_edita_a_equipe(admin):
    criado = admin.post(
        "/api/auth/equipe", json={"nome": "Rhuan", "email": "rhuan@desperta.org", "senha": SENHA}
    )
    assert criado.status_code == 201
    novo = criado.get_json()["administrador"]
    assert novo["papel"] == "editor"
    assert len(admin.get("/api/auth/equipe").get_json()["itens"]) == 2
    editado = admin.patch(f"/api/auth/equipe/{novo['id']}", json={"ativo": False})
    assert editado.get_json()["administrador"]["ativo"] is False
    assert admin.patch("/api/auth/equipe/9999", json={"nome": "X"}).status_code == 404


def test_editor_nao_gerencia_a_equipe(editor):
    assert editor.get("/api/auth/equipe").status_code == 403
    assert editor.post("/api/auth/equipe", json={}).status_code == 403


def test_ultimo_admin_nao_se_rebaixa(admin, dados):
    resposta = admin.patch(f"/api/auth/equipe/{dados.admin.id}", json={"papel": "editor"})
    assert resposta.status_code == 409


# ======================================================
# NOTICIAS NO PORTAL
# ======================================================
def test_rascunho_nao_aparece_no_portal(cliente, dados):
    assert cliente.get("/api/noticias").get_json()["total"] == 0
    assert cliente.get(f"/api/noticias/{dados.noticia.slug}").status_code == 404


def test_lista_principal_e_detalhe_da_publicada(db, cliente, dados):
    publicar(db, dados.noticia)
    lista = cliente.get("/api/noticias?tema=46").get_json()
    assert lista["total"] == 1 and lista["itens"][0]["slug"] == "camara-aprova-projeto"
    assert lista["itens"][0]["publicado_em"] == "2026-11-10T15:00:00Z"
    principal = cliente.get("/api/noticias/principal").get_json()["secoes"]
    assert principal[0]["tema"]["nome"] == "Educacao"
    detalhe = cliente.get("/api/noticias/camara-aprova-projeto").get_json()
    assert detalhe["visualizacoes"] == 1
    assert detalhe["fontes"][0]["url_dados_abertos"].endswith("/votacoes/2310837-8")
    assert detalhe["como_foi_feita"]["gerador"] == "gerador-falso"
    assert cliente.get("/api/noticias/camara-aprova-projeto").get_json()["visualizacoes"] == 2
    assert db.session.get(Noticia, dados.noticia.id).alterado_em is None


def test_busca_com_periodo_em_horario_de_brasilia(db, cliente, dados):
    # 01h30 de 11/11 em UTC = 22h30 de 10/11 em Brasilia
    publicar(db, dados.noticia, datetime(2026, 11, 11, 1, 30))
    assert cliente.get("/api/noticias/busca?q=projeto&dia=10&mes=11&ano=2026").get_json()["total"] == 1
    assert cliente.get("/api/noticias/busca?q=projeto&dia=11&mes=11&ano=2026").get_json()["total"] == 0
    assert cliente.get("/api/noticias/busca?q=projeto&mes=11&ano=2026").get_json()["total"] == 1
    assert cliente.get("/api/noticias/busca?q=").status_code == 400
    assert cliente.get("/api/noticias/busca?q=projeto&dia=10").status_code == 400
    assert cliente.get("/api/noticias/busca?q=projeto&pagina=x").status_code == 400


def test_periodo_em_utc():
    assert periodo_em_utc(10, 11, 2026) == (datetime(2026, 11, 10, 3, 0), datetime(2026, 11, 11, 3, 0))
    assert periodo_em_utc(None, 12, 2026) == (datetime(2026, 12, 1, 3, 0), datetime(2027, 1, 1, 3, 0))
    assert periodo_em_utc() == (None, None)
    with pytest.raises(DadosInvalidos):
        periodo_em_utc(31, 2, 2026)


# ======================================================
# NOTICIAS NA AREA ADMINISTRATIVA
# ======================================================
def test_area_administrativa_exige_login(cliente, dados):
    assert cliente.get("/api/noticias/admin").status_code == 401
    assert cliente.post(f"/api/noticias/admin/{dados.noticia.id}/publicar").status_code == 401


def test_fila_e_detalhe_de_revisao(db, editor, dados):
    db.session.add(
        GeracaoIA(
            noticia_id=dados.noticia.id, modelo_geracao="frases", modelo_embedding="m", consulta="c",
            versao_prompt="v1", entrada='{"caso": "votacao", "votacao_id": "2310837-8"}', status="ok",
        )
    )
    db.session.commit()
    fila = editor.get("/api/noticias/admin?status=rascunho").get_json()
    assert fila["total"] == 1 and fila["itens"][0]["status"] == "rascunho"
    assert editor.get("/api/noticias/admin?caso=votacao").get_json()["total"] == 1
    assert editor.get("/api/noticias/admin?caso=nova").get_json()["total"] == 0
    assert editor.get("/api/noticias/admin?status=xyz").status_code == 400
    detalhe = editor.get(f"/api/noticias/admin/{dados.noticia.id}").get_json()
    assert detalhe["geracoes"][0]["trechos"][0]["nota"] == 0.91
    assert detalhe["revisoes"][0]["acao"] == "aprovou"


def test_fluxo_aprovar_publicar_arquivar(db, editor, dados):
    url = f"/api/noticias/admin/{dados.noticia.id}"
    assert editor.post(f"{url}/aprovar").get_json()["status"] == "em_revisao"
    publicada = editor.post(f"{url}/publicar").get_json()
    assert publicada["status"] == "publicada" and publicada["publicado_em"]
    assert editor.post(f"{url}/aprovar").status_code == 409
    assert editor.post(f"{url}/arquivar").get_json()["status"] == "arquivada"
    acoes = [r.acao for r in db.session.scalars(db.select(NoticiaRevisao).order_by(NoticiaRevisao.id))]
    assert acoes[-3:] == ["aprovou", "publicou", "arquivou"]


def test_rejeitar_exige_comentario(editor, dados):
    url = f"/api/noticias/admin/{dados.noticia.id}/rejeitar"
    assert editor.post(url).status_code == 400
    resposta = editor.post(url, json={"comentario": "Numero errado no titulo."})
    assert resposta.get_json()["status"] == "rejeitada"
    assert editor.post(f"/api/noticias/admin/{dados.noticia.id}/voar").status_code == 400


def test_editar_muda_texto_slug_e_alterado_em(db, editor, dados):
    url = f"/api/noticias/admin/{dados.noticia.id}"
    resposta = editor.patch(url, json={"titulo": "Câmara aprova o projeto da escola"})
    assert resposta.get_json()["slug"] == "camara-aprova-o-projeto-da-escola"
    assert resposta.get_json()["alterado_em"]
    assert editor.patch(url, json={"resumo": "x" * 501}).status_code == 400
    assert editor.patch(url, json={"cod_tema": 999}).status_code == 400
    editor.post(f"{url}/publicar")
    publicada = editor.patch(url, json={"titulo": "Outro titulo"}).get_json()
    assert publicada["slug"] == "camara-aprova-o-projeto-da-escola"


def test_lote_separa_feitas_e_falhas(db, editor, dados):
    outra = fabricas.noticia(slug="outra", status="publicada", publicado_em=datetime(2026, 1, 1))
    db.session.add(outra)
    db.session.commit()
    resposta = editor.post(
        "/api/noticias/admin/lote", json={"ids": [dados.noticia.id, outra.id, 9999], "acao": "aprovar"}
    ).get_json()
    assert resposta["feitas"] == [dados.noticia.id]
    assert {f["id"] for f in resposta["falhas"]} == {outra.id, 9999}
    assert editor.post("/api/noticias/admin/lote", json={"ids": "1", "acao": "aprovar"}).status_code == 400


def test_equipe_escreve_noticia_com_fonte_conferida(editor):
    corpo = {"titulo": "Plenário vota PL", "resumo": "Resumo.", "corpo": "Texto.", "cod_tema": 46}
    criada = editor.post("/api/noticias/admin", json={**corpo, "fontes": [{"tipo": "proposicao", "ref_id": 2310837}]})
    assert criada.status_code == 201
    assert criada.get_json()["origem"] == "equipe" and criada.get_json()["status"] == "rascunho"
    sem_fonte = editor.post("/api/noticias/admin", json={**corpo, "fontes": [{"tipo": "proposicao", "ref_id": "1"}]})
    assert sem_fonte.status_code == 400


def test_so_admin_apaga_rascunho(db, admin, dados, app):
    url = f"/api/noticias/admin/{dados.noticia.id}"
    outro = app.test_client()
    auth_services.criar_administrador("Caio", "caio@desperta.org", SENHA, "editor")
    entrar(outro, "caio@desperta.org")
    assert outro.delete(url).status_code == 403
    assert admin.delete(url).status_code == 204
    assert admin.delete(url).status_code == 404


def test_slug_reservado_nao_sombreia_rota(db):
    from desperta.noticias.services import gerar_slug

    assert gerar_slug("Busca") == "busca-noticia"


# ======================================================
# PROPOSICAO, VOTACAO E TEMAS
# ======================================================
def test_detalhe_da_proposicao(db, cliente, dados):
    publicar(db, dados.noticia)
    dados.proposicao.regime = "."
    db.session.commit()
    p = cliente.get("/api/proposicoes/2310837").get_json()
    assert p["sigla"] == "PL 1234/2024"
    # Datas da Camara saem no horario de Brasilia; as do portal, em UTC
    assert p["data_apresentacao"].endswith("-03:00")
    assert p["regime"] == "não informado pela Câmara"
    assert p["tramitacoes"]["total"] == 1 and p["tramitacoes"]["itens"][0]["despacho"] == "Publique-se."
    assert p["votacoes"][0]["id"] == "2310837-8"
    assert p["temas"][0]["nome"] == "Educacao"
    assert cliente.get("/api/proposicoes/1").status_code == 404
    assert cliente.get("/api/proposicoes/2310837/tramitacoes?por_pagina=1").get_json()["paginas"] == 1


def test_despacho_vazio_nao_aparece(db, cliente, dados):
    from desperta.proposicoes.models import Tramitacao

    db.session.get(Tramitacao, (2310837, 1)).despacho = ""
    db.session.commit()
    assert cliente.get("/api/proposicoes/2310837").get_json()["tramitacoes"]["itens"][0]["despacho"] is None


def test_temas_com_contagem(db, cliente, dados):
    db.session.add(Tema(cod_tema=40, nome="Agricultura", icone="eco", hash_origem=fabricas.HASH))
    publicar(db, dados.noticia)
    itens = {t["nome"]: t["noticias_publicadas"] for t in cliente.get("/api/proposicoes/temas").get_json()["itens"]}
    assert itens == {"Agricultura": 0, "Educacao": 1}


def test_detalhe_da_votacao(db, cliente, dados):
    dados.votacao.filhos_sincronizados_em = datetime(2026, 11, 10)
    db.session.add_all(
        [
            Orientacao(votacao_id="2310837-8", partido_bloco="Governo", tipo_lideranca="B", orientacao="Sim"),
            Orientacao(votacao_id="2310837-8", partido_bloco="Bl MdbPsd", tipo_lideranca="B", orientacao=""),
        ]
    )
    db.session.commit()
    v = cliente.get("/api/votacoes/2310837-8").get_json()
    assert v["resultado"] == "aprovada"
    assert v["data_hora_registro"].endswith("-03:00")
    assert v["situacao_dos_votos"]["codigo"] == "nominal"
    assert v["votos"][0] == {
        "deputado_id": 204554, "nome": "Fulana de Tal", "sigla_partido": "PL", "sigla_uf": "ES",
        "url_foto": "https://www.camara.leg.br/foto.jpg", "voto": "Sim",
    }
    grupos = v["orientacoes"]
    assert [o["nome"] for o in grupos["partidos"]] == ["PL"]
    assert [o["nome"] for o in grupos["liderancas"]] == ["Governo"]
    assert grupos["blocos"] == [{"nome": "Bl MdbPsd", "orientacao": "não informado pela Câmara"}]
    assert cliente.get("/api/votacoes/1-1").status_code == 404


def test_votacao_secreta_sem_tipo_de_voto(db, cliente, dados):
    dados.votacao.filhos_sincronizados_em = datetime(2026, 11, 10)
    db.session.get(Voto, ("2310837-8", 204554)).tipo_voto = None
    db.session.commit()
    v = cliente.get("/api/votacoes/2310837-8").get_json()
    assert v["situacao_dos_votos"]["codigo"] == "secreta"
    assert v["votos"][0]["voto"] == "não informado pela Câmara"


# ======================================================
# SISTEMA
# ======================================================
def test_situacao_dos_dados_avisa_quando_desatualizados(db, cliente, dados):
    situacao = cliente.get("/api/sistema/situacao").get_json()
    assert situacao["dados_desatualizados"] is True and situacao["aviso"]
    db.session.add(fabricas.coleta(finalizado_em=datetime.now(timezone.utc).replace(tzinfo=None)))
    db.session.commit()
    assert cliente.get("/api/sistema/situacao").get_json()["dados_desatualizados"] is False


def test_coletas_e_log_so_para_admin(db, admin, editor_separado):
    assert admin.get("/api/sistema/coletas").get_json()["total"] == 1
    assert admin.get("/api/sistema/coletas?status=ok").get_json()["itens"][0]["recurso"] == "proposicoes"
    assert admin.get("/api/sistema/coletas?status=xyz").status_code == 400
    log = admin.get("/api/sistema/log?modulo=coletor").get_json()
    assert log["itens"][0]["acao"] == "coletar"
    assert editor_separado.get("/api/sistema/log").status_code == 403


@pytest.fixture
def editor_separado(app, dados):
    auth_services.criar_administrador("Rhuan", "rhuan@desperta.org", SENHA, "editor")
    outro = app.test_client()
    entrar(outro, "rhuan@desperta.org")
    return outro


def test_coleta_da_fabrica_existe(db, dados):
    assert db.session.scalar(db.select(db.func.count()).select_from(Coleta)) == 1
