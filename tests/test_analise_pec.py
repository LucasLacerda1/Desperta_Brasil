"""Analise da PEC (scripts/analise_pec): notas dos testes e memoria da leitura encadeada, com um leitor falso."""

import os
import random
import sys
import zlib

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "analise_pec"))

import avaliacao  # noqa: E402
import leitura  # noqa: E402


# === LeitorFalso (um token por palavra, vetor fixo por token) ===
class LeitorFalso(leitura.Leitor):
    def __init__(self):
        self.leituras = 0
        self.transformar = None
        self.tokenizador = type("Tok", (), {"decode": staticmethod(lambda ids: " ".join(map(str, ids)))})()

    def ids(self, texto, espaco_antes=False):
        return [zlib.crc32(p.encode()) % 1000 + 10 for p in texto.split()]

    def modo_dropout(self, ligado):
        self.dropout = ligado

    def ler(self, entradas):
        self.leituras += len(entradas)
        saida = []
        for contexto, texto in entradas:
            assert len(contexto) <= leitura.METADE and len(texto) <= leitura.METADE * 2
            deslocamento = sum(contexto) % 7
            saida.append(numpy.array([numpy.random.default_rng(t + deslocamento).normal(size=8) for t in texto]))
        return saida


def _vetor(*valores):
    return leitura.normalizar(numpy.array(valores, dtype=float))


# ======================================================
# NOTAS
# ======================================================
def test_teste_a_conta_acertos_e_acaso():
    nota = avaliacao.teste_a(["F1", "F2", "F3", "F4", "F5", "F6"], ["F5", "F6", "F9", "F1", "F2"], 22)
    assert (nota["acertos"], nota["top5"], nota["acaso"]) == (3, ["F1", "F2", "F3", "F4", "F5"], 1.14)


def test_resumo_so_conta_frases_ligadas_ao_texto():
    resumo = [
        {"frase": "a", "de_qual_frase_da_pec": "F7"},
        {"frase": "b", "de_qual_frase_da_pec": ["F9", "F12"]},
        {"frase": "c", "de_qual_frase_da_pec": avaliacao.FORA_DO_TEXTO},
        {"frase": "d", "de_qual_frase_da_pec": "<codigo>"},
    ]
    certas = avaliacao.certas_do_resumo(resumo)
    assert certas == [("a", {"F7"}), ("b", {"F9", "F12"})]
    nota = avaliacao.teste_b(["F7", "F1"], certas, 22)
    assert (nota["acertos"], nota["de"], nota["acaso"]) == (1, 2, 0.14)


def test_teste_d_tem_nota_exata_e_ampla():
    nota = avaliacao.teste_d(["X", "Y", "Z"], ["X"], ["Y"], ["Z", "W"])
    assert (nota["exata"], nota["ampla"], nota["oficiais"]) == (1, 2, 1)


def test_bloco_da_primeira_frase_vale_os_dois():
    certos = {"F1": "1. Epígrafe e 2. Autoria", "F2": "3. Ementa", "F3": "Justificação: problemas"}
    escolhidos = {"F1": "2. Autoria", "F2": "4. Preâmbulo", "F3": "Justificação: problemas"}
    nota = avaliacao.teste_blocos(escolhidos, certos)
    assert (nota["acertos"], nota["sempre_o_maior_bloco"], nota["erradas"]) == (2, 1, {"F2": "4. Preâmbulo"})


def test_palavras_ignoram_acento_e_maiuscula():
    nota = avaliacao.teste_e_pesos({"demarcação": 0.3, "terras": 0.2}, ["Demarcacao", "índios"])
    assert nota["em_comum"] == ["demarcacao"]
    lacunas = avaliacao.teste_e_lacunas([("a", True), ("b", False), ("c", None)])
    assert (lacunas["acertos"], lacunas["testadas"], lacunas["nao_testadas"]) == (1, 2, ["c"])


def test_adversarios_por_palavras():
    frases = [("F1", "demarcação de terras indígenas"), ("F2", "apoio dos nobres pares")]
    assert avaliacao.mais_parecida_por_palavras("terras indígenas demarcadas", frases, set()) == "F1"
    assert avaliacao.centralidade_por_palavras(frases + [("F3", "terras e mais terras")], set())[0] in ("F1", "F3")


# ======================================================
# LEITURA
# ======================================================
def test_tirar_palavra_arruma_os_espacos():
    assert leitura.sem_a_palavra("a terra , indígena.", 2, 7) == "a, indígena."
    assert [p for p, _, _ in leitura.palavras_de("A demarcação de terras é da União")] == [
        "demarcação",
        "terras",
        "união",
    ]


def test_frases_juntas_dao_os_tokens_do_pedaco():
    leitor = LeitorFalso()
    frases = [("F1", "uma frase curta."), ("F2", "outra frase.")]
    ids, intervalos = leitor.tokenizar_frases(frases)
    assert ids == leitor.ids("uma frase curta. outra frase.")
    assert intervalos == [("F1", 0, 3), ("F2", 3, 5)]


def test_contexto_guarda_o_prefixo_e_tira_a_frase_mais_longe():
    leitor = LeitorFalso()
    memoria = leitura.Memoria(
        frases=[
            ("F1", "perto " * 120, _vetor(1, 0)),
            ("F2", "longe " * 120, _vetor(0, 1)),
            ("F3", "novo " * 30, _vetor(1, 0)),
        ]
    )
    contexto, saiu = leitura.montar_contexto(leitor, "prefixo fixo " * 10, memoria, _vetor(1, 0))
    assert saiu == ["F2"]
    assert len(contexto) <= leitura.METADE
    assert contexto[:20] == leitor.ids("prefixo fixo " * 10)


def test_frase_sozinha_maior_que_o_espaco_e_cortada():
    leitor = LeitorFalso()
    memoria = leitura.Memoria(frases=[("F1", "palavra " * 400, _vetor(1, 0))])
    contexto, saiu = leitura.montar_contexto(leitor, "", memoria, _vetor(1, 0))
    assert saiu == [] and len(contexto) == leitura.METADE


def _pedacos():
    return [
        [("F1", "Altera a Constituição para submeter a demarcação de terras."), ("F2", "Artigo único da emenda.")],
        [("F3", "Vastas extensões de terra foram entregues."), ("F4", "Os municípios foram prejudicados.")],
        [("F5", "Contamos com o apoio dos nobres pares.")],
    ]


def test_leitura_encadeada_leva_a_propria_escolha_adiante():
    leitor = LeitorFalso()
    lida = leitura.ler_encadeada(leitor, _pedacos(), lambda numero: "Contexto inicial da PEC.")
    assert [p["pedaco"] for p in lida.por_pedaco] == [1, 2, 3]
    assert set(lida.vetor_frase) == {"F1", "F2", "F3", "F4", "F5"}
    assert all(p["tokens_contexto"] <= leitura.METADE for p in lida.por_pedaco)
    # A frase escolhida no pedaco 1 entra no contexto do pedaco 2
    escolhida = dict(sum(_pedacos(), []))[lida.por_pedaco[0]["frase_escolhida"]]
    assert leitor.tokenizador.decode(leitor.ids(escolhida)) in lida.por_pedaco[1]["contexto"]
    assert len(lida.por_pedaco[0]["palavras"]) <= leitura.PALAVRAS_POR_PEDACO


def test_controle_sorteado_repete_com_a_mesma_semente():
    def rodar(semente):
        return [
            p["frase_escolhida"]
            for p in leitura.ler_encadeada(LeitorFalso(), _pedacos(), lambda n: "", random.Random(semente)).por_pedaco
        ]

    assert rodar(3) == rodar(3)


def test_pedaco_maior_que_a_metade_e_lido_em_partes():
    leitor = LeitorFalso()
    longo = [[("F1", "palavra " * 300)]]
    lida = leitura.ler_encadeada(leitor, longo, lambda n: "")
    assert lida.por_pedaco[0]["tokens_pedaco"] == 300
    assert "F1" in lida.vetor_frase


def test_peso_da_palavra_e_ajustado_pelo_tamanho_do_texto():
    leitor = LeitorFalso()
    texto = "terras indígenas demarcadas pela União"
    original = leitura.media(leitor.ler([([], leitor.ids(texto))])[0])
    sem = leitura.media(leitor.ler([([], leitor.ids(leitura.sem_a_palavra(texto, 0, 6)))])[0])
    esperado = (1 - leitura.cosseno(sem, original)) * len(leitor.ids(texto))
    assert leitor.pesos_das_palavras([], texto, original)["terras"] == pytest.approx(esperado)


@pytest.mark.parametrize("modo", ["soltas"])
def test_frases_soltas_dao_um_vetor_por_frase(modo):
    lida = leitura.ler_frases_soltas(
        LeitorFalso(), [("F1", "uma frase de teste."), ("F2", "outra frase bem diferente.")]
    )
    assert set(lida.vetor_frase) == {"F1", "F2"} and lida.contexto_da_frase == {"F1": [], "F2": []}
    assert abs(numpy.linalg.norm(lida.vetor_pec) - 1) < 1e-9


def test_notas_continuas():
    assert avaliacao.auc({"F1": 3, "F2": 2, "F3": 1}, {"F1"}) == 1.0
    assert avaliacao.auc({"F1": 1, "F2": 2, "F3": 3}, {"F1"}) == 0.0
    assert avaliacao.auc({"F1": 2, "F2": 2}, {"F1"}) == 0.5
    assert avaliacao.auc({"F1": 1}, {"F1"}) is None
    assert (avaliacao.nota_da_posicao(1, 31), avaliacao.nota_da_posicao(31, 31)) == (1.0, 0.0)
    assert avaliacao.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert avaliacao.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)


def test_votacao_com_dropout_tira_a_media_e_desliga_no_fim():
    leitor = LeitorFalso()
    frases = [("F1", "uma frase de teste."), ("F2", "outra frase bem diferente."), ("F3", "e mais uma.")]
    normal = leitura.ler_frases_soltas(leitor, frases)
    votada = leitura.ler_frases_votacao(leitor, frases, leituras=7, por_vez=3)
    # O leitor falso e deterministico: a media de 7 leituras iguais e a propria leitura
    for codigo in normal.vetor_frase:
        assert votada.vetor_frase[codigo] == pytest.approx(normal.vetor_frase[codigo])
    assert leitor.dropout is False


def test_whitening_iguala_as_direcoes_e_ajusta_a_leitura():
    gerador = numpy.random.default_rng(3)
    amostra = gerador.normal(size=(400, 4)) * numpy.array([10, 1, 0.1, 0.01]) + 2
    branco = leitura.Whitening(amostra)
    ajustados = numpy.array([(v - branco.media) @ branco.matriz for v in amostra])
    assert numpy.std(ajustados, axis=0) == pytest.approx(numpy.ones(4), rel=0.01)
    assert numpy.linalg.norm(branco(amostra[0])) == pytest.approx(1.0)
    lida = leitura.ler_frases_soltas(LeitorFalso(), [("F1", "uma frase."), ("F2", "outra frase.")])
    ajustada = leitura.ajustar_leitura(lida, lambda v: leitura.normalizar(v[::-1].copy()))
    assert ajustada.vetor_frase["F1"] == pytest.approx(lida.vetor_frase["F1"][::-1])
    assert numpy.linalg.norm(ajustada.vetor_pec) == pytest.approx(1.0)


def test_consenso_fica_com_as_frases_de_pelo_menos_n_leitores():
    escolhas = {"a": {"F1", "F2", "F3"}, "b": {"F2", "F3", "F4"}, "c": {"F3", "F5"}}
    assert avaliacao.consenso(escolhas, 2) == {"F2", "F3"}
    assert avaliacao.consenso(escolhas, 3) == {"F3"}
    assert avaliacao.consenso(escolhas, 1) == {"F1", "F2", "F3", "F4", "F5"}
