import pytest
import requests

from api_falsa import URL_BASE, carregar, envelope
from desperta.coletor.cliente import ClienteCamara, ErroAPI, TempoEsgotado


def test_obter_devolve_dados(api, cliente):
    api.responder("temas", envelope([{"cod": "1"}]))
    assert cliente.obter("temas") == [{"cod": "1"}]
    assert (cliente.requisicoes, cliente.erros_http) == (1, 0)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_repete_em_429_e_5xx_e_conta_o_erro(api, cliente, esperas, status):
    api.responder("temas", [status, envelope(["ok"])])
    assert cliente.obter("temas") == ["ok"]
    assert (cliente.requisicoes, cliente.erros_http) == (2, 1)
    assert esperas == [2]


def test_espera_exponencial_ate_5_tentativas(api, cliente, esperas):
    api.responder("temas", [504] * 5)
    with pytest.raises(ErroAPI) as erro:
        cliente.obter("temas")
    assert esperas == [2, 4, 8, 16]
    assert (cliente.requisicoes, cliente.erros_http) == (5, 5)
    assert erro.value.status == 504


def test_ultima_tentativa_pode_dar_certo(api, cliente, esperas):
    api.responder("temas", [504, 504, 504, 504, envelope(["ok"])])
    assert cliente.obter("temas") == ["ok"]
    assert cliente.erros_http == 4


@pytest.mark.parametrize("excecao", [requests.Timeout("lenta"), requests.ConnectionError("caiu")])
def test_repete_em_timeout_e_queda_de_conexao(api, cliente, excecao):
    api.responder("temas", [excecao, envelope(["ok"])])
    assert cliente.obter("temas") == ["ok"]
    assert (cliente.requisicoes, cliente.erros_http) == (2, 1)


@pytest.mark.parametrize("status", [400, 404])
def test_erro_do_pedido_nao_repete(api, cliente, esperas, status):
    api.responder("temas", [status])
    with pytest.raises(ErroAPI) as erro:
        cliente.obter("temas")
    assert erro.value.status == status
    assert esperas == []
    assert cliente.erros_http == 0


def test_resposta_que_nao_e_json_vira_erro_de_api(api, cliente):
    from api_falsa import RespostaFalsa

    api.get = lambda *a, **k: RespostaFalsa(200)
    with pytest.raises(ErroAPI):
        cliente.obter("temas")


def test_paginar_segue_o_link_next(api, cliente):
    api.responder("itens", envelope([1, 2], proxima=f"{URL_BASE}/itens-pagina-2"))
    api.responder("itens-pagina-2", envelope([3]))
    assert list(cliente.paginar("itens", {"itens": 2})) == [1, 2, 3]
    # O link next ja traz os parametros: nao manda de novo
    assert api.chamadas == [("itens", {"itens": 2}), ("itens-pagina-2", None)]


def test_paginar_com_erro_no_meio(api, cliente):
    api.responder("itens", envelope([1], proxima=f"{URL_BASE}/itens-pagina-2"))
    api.responder("itens-pagina-2", [404])
    lista = cliente.paginar("itens")
    assert next(lista) == 1
    with pytest.raises(ErroAPI):
        next(lista)


def test_url_base_com_barra_e_caminho_com_barra(api, esperas):
    cliente = ClienteCamara(f"{URL_BASE}/", sessao=api)
    api.responder("legislaturas", carregar("legislaturas"))
    assert cliente.obter("/legislaturas")[0]["id"] == 57


def test_sem_orcamento_o_relogio_nao_limita(api, cliente):
    api.responder("a", envelope([1]))
    cliente.relogio = lambda: pytest.fail("sem orcamento, o relogio nao e lido")
    assert cliente.obter("a") == [1]


def test_orcamento_esgotado_nao_faz_a_chamada(api, cliente):
    agora = [0]
    cliente.relogio = lambda: agora[0]
    cliente.definir_orcamento(10)
    api.responder("a", envelope([1]))
    assert cliente.obter("a") == [1]

    agora[0] = 10
    with pytest.raises(TempoEsgotado):
        cliente.obter("a")
    assert cliente.requisicoes == 1


def test_orcamento_interrompe_as_novas_tentativas(api, cliente, esperas):
    agora = [0]
    cliente.relogio = lambda: agora[0]
    cliente.definir_orcamento(10)
    # A espera de 2 s depois do primeiro 504 acaba com o orcamento
    cliente.dormir = lambda segundos: agora.__setitem__(0, 10)
    api.responder("a", [504, envelope([1])])
    with pytest.raises(TempoEsgotado):
        cliente.obter("a")
    assert cliente.requisicoes == 1
