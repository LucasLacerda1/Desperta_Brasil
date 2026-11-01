from datetime import date, datetime, timedelta, timezone

import pytest

from desperta.coletor.janelas import DIAS_POR_JANELA, dividir_janela
from desperta.coletor import normalizacao as n

URI = "https://dadosabertos.camara.leg.br/api/v2"


@pytest.mark.parametrize(
    "uri, recurso, esperado",
    [
        (f"{URI}/deputados/73434", "deputados", 73434),
        (f"{URI}/deputados/73434/", "deputados", 73434),
        (f"{URI}/orgaos/180", "deputados", None),
        (f"{URI}/orgaos/180", None, 180),
        (None, "deputados", None),
        ("", "deputados", None),
        (f"{URI}/deputados/", "deputados", None),
    ],
)
def test_id_da_uri(uri, recurso, esperado):
    assert n.id_da_uri(uri, recurso) == esperado


@pytest.mark.parametrize(
    "uri, esperado",
    [
        (f"{URI}/votacoes/2422697-51/", "2422697-51"),
        (f"{URI}/votacoes/2422697-51", "2422697-51"),
        (None, None),
    ],
)
def test_id_texto_da_uri(uri, esperado):
    assert n.id_texto_da_uri(uri) == esperado


def test_opcional_transforma_vazio_em_none():
    assert n.opcional("") is None
    assert n.opcional("   ") is None
    assert n.opcional("texto") == "texto"
    assert n.opcional(None) is None
    assert n.opcional(0) == 0


def test_conversoes_de_numero_e_texto():
    assert n.para_int("34") == 34
    assert n.para_int(34) == 34
    assert n.para_int("") is None
    assert n.para_int(None) is None
    assert n.para_texto(101) == "101"
    assert n.para_texto(None) is None


@pytest.mark.parametrize(
    "valor, esperado",
    [
        (1, True),
        (0, False),
        (True, True),
        (False, False),
        ("1", True),
        ("0", False),
        (None, None),
        ("", None),
    ],
)
def test_para_bool(valor, esperado):
    assert n.para_bool(valor) is esperado


def test_datas_ficam_sem_fuso():
    assert n.para_data_hora("2008-11-04T18:36") == datetime(2008, 11, 4, 18, 36)
    assert n.para_data_hora("2024-05-28T23:03:13") == datetime(2024, 5, 28, 23, 3, 13)
    assert n.para_data_hora("2024-05-28T23:03:13-03:00").tzinfo is None
    assert n.para_data_hora(None) is None
    assert n.para_data("2023-02-01") == date(2023, 2, 1)
    assert n.para_data("2023-02-01T10:00") == date(2023, 2, 1)
    assert n.para_data(None) is None


def test_data_invalida_gera_erro():
    with pytest.raises(ValueError):
        n.para_data_hora("ontem")


def test_agora_utc_nao_tem_fuso():
    agora = n.agora_utc()
    assert agora.tzinfo is None
    assert abs((datetime.now(timezone.utc).replace(tzinfo=None) - agora).total_seconds()) < 5


def test_hash_nao_depende_da_ordem_das_chaves():
    assert n.calcular_hash({"a": 1, "b": 2}) == n.calcular_hash({"b": 2, "a": 1})
    assert n.calcular_hash({"a": 1}) != n.calcular_hash({"a": 2})
    assert len(n.calcular_hash({"data": date(2024, 1, 1)})) == 64


def test_janela_curta_nao_e_dividida():
    assert dividir_janela(date(2024, 5, 1), date(2024, 5, 2)) == [(date(2024, 5, 1), date(2024, 5, 2))]


def test_janela_nao_atravessa_o_ano():
    assert dividir_janela(date(2023, 12, 1), date(2024, 1, 15)) == [
        (date(2023, 12, 1), date(2023, 12, 31)),
        (date(2024, 1, 1), date(2024, 1, 15)),
    ]


def test_janela_nunca_passa_de_3_meses_e_cobre_todos_os_dias():
    janelas = dividir_janela(date(2023, 1, 1), date(2025, 12, 31))
    dia = date(2023, 1, 1)
    for inicio, fim in janelas:
        assert inicio == dia
        assert inicio.year == fim.year
        # Mesmo no pior caso (fevereiro), o fim fica dentro de 3 meses
        limite_mes = inicio.month + 3
        limite = date(inicio.year + (limite_mes - 1) // 12, (limite_mes - 1) % 12 + 1, 1)
        assert (fim - inicio).days < DIAS_POR_JANELA and fim < limite.replace(day=min(inicio.day, 28)) + timedelta(
            days=4
        )
        dia = fim + timedelta(days=1)
    assert dia == date(2026, 1, 1)
