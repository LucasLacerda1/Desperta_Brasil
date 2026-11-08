"""Tema pelo prototipo (scripts/temas_prototipo): as contas rapidas conferidas contra as lentas."""

import os
import sys

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "temas_prototipo"))

import prototipos  # noqa: E402


def _exemplo():
    gerador = numpy.random.default_rng(7)
    vetores = prototipos.normalizar_linhas(gerador.normal(size=(12, 5)))
    rotulos = numpy.zeros((12, 4))
    for i in range(12):
        rotulos[i, i % 4] = 1
        if i % 3 == 0:
            rotulos[i, (i + 1) % 4] = 1
    rotulos[11] = [0, 0, 0, 1]
    return vetores, rotulos


def _lenta(vetores, rotulos):
    """Recalcula o prototipo de cada tema sem a proposicao avaliada."""
    notas = numpy.full(rotulos.shape, -numpy.inf)
    for i in range(len(vetores)):
        for t in range(rotulos.shape[1]):
            membros = [j for j in range(len(vetores)) if rotulos[j, t] and j != i]
            if membros:
                media = vetores[membros].mean(axis=0)
                notas[i, t] = media @ vetores[i] / numpy.linalg.norm(media)
    return notas


def test_conta_rapida_igual_a_lenta():
    vetores, rotulos = _exemplo()
    assert prototipos.notas_densas(vetores, rotulos) == pytest.approx(_lenta(vetores, rotulos))


def test_tema_com_uma_so_proposicao_fica_vazio_sem_ela():
    vetores = prototipos.normalizar_linhas(numpy.array([[1.0, 0], [0, 1.0], [1.0, 1.0]]))
    rotulos = numpy.array([[1, 0], [0, 1], [0, 1]])
    notas = prototipos.notas_densas(vetores, rotulos)
    assert notas[0, 0] == -numpy.inf and numpy.isfinite(notas[0, 1])


def test_vizinhos_igual_a_conta_lenta():
    vetores, rotulos = _exemplo()
    rotulos = numpy.vstack([rotulos, numpy.zeros((2, 4))])  # duas sem tema: so recebem nota, nao votam
    vetores = numpy.vstack([vetores, prototipos.normalizar_linhas(numpy.ones((2, 5)))])
    k = 3
    lenta = numpy.zeros(rotulos.shape)
    votantes = [j for j in range(len(vetores)) if rotulos[j].any()]
    for i in range(len(vetores)):
        outras = sorted((j for j in votantes if j != i), key=lambda j: -(vetores[i] @ vetores[j]))[:k]
        for j in outras:
            lenta[i] += max(vetores[i] @ vetores[j], 0) * rotulos[j]
    assert prototipos.notas_vizinhos(vetores, rotulos, k, bloco=4) == pytest.approx(lenta, abs=1e-5)


def test_medidas_e_adversarios():
    rotulos = numpy.array([[1, 0, 0, 0], [0, 1, 0, 0], [1, 1, 0, 0]])
    notas = numpy.array([[0.9, 0.1, 0.2, 0.3], [0.9, 0.1, 0.8, 0.2], [0.1, 0.2, 0.9, 0.3]])
    medida = prototipos.medir(notas, rotulos)
    assert list(medida["posicao"]) == [1, 4, 3]
    assert list(medida["top1"]) == [True, False, False] and list(medida["top3"]) == [True, False, True]
    assert prototipos.maioria(rotulos) == pytest.approx((2 / 3, 1.0))
    top1, top3 = prototipos.acaso(rotulos)
    assert top1 == pytest.approx((1 / 4 + 1 / 4 + 2 / 4) / 3)
    assert top3 == pytest.approx((3 / 4 + 3 / 4 + 1) / 3)


def test_whitening_iguala_as_direcoes():
    gerador = numpy.random.default_rng(1)
    vetores = gerador.normal(size=(500, 4)) * numpy.array([10, 1, 0.1, 0.01]) + 5
    branco = (vetores - vetores.mean(axis=0)) @ numpy.linalg.svd(numpy.cov((vetores - vetores.mean(axis=0)).T))[0]
    assert numpy.std(branco, axis=0)[0] > 100 * numpy.std(branco, axis=0)[3]
    resultado = prototipos.whitening(vetores)
    assert resultado.shape == (500, 4) and numpy.linalg.norm(resultado, axis=1) == pytest.approx(numpy.ones(500))
    assert prototipos.whitening(vetores, dimensoes=2).shape == (500, 2)


def test_tfidf_ignora_acento_e_palavras_vazias_e_faz_pares():
    textos = ["Demarcação de terras indígenas", "demarcacao das terras", "saúde da mulher", "saude publica"]
    matriz = prototipos.tfidf(textos, {"de", "da", "das"}, minimo=2)
    assert matriz.shape == (4, 3)  # demarcacao, saude, terras: as que aparecem em pelo menos 2 textos
    assert numpy.linalg.norm(matriz, axis=1) == pytest.approx(numpy.ones(4), abs=1e-6)
    assert prototipos.tfidf(textos, {"de", "da", "das"}, minimo=2, pares=True).shape == (4, 4)  # + demarcacao_terras


def test_minimo_de_exemplos_e_fusao():
    rotulos = numpy.array([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 1, 1]])
    notas = numpy.array([[0.1, 0.5, 0.9], [0.3, 0.2, 0.1], [0.2, 0.4, 0.6], [0.5, 0.1, 0.3]])
    filtradas = prototipos.com_minimo(notas, rotulos, minimo=2)
    assert numpy.all(filtradas[:, 2] == -numpy.inf) and filtradas[0, 1] == 0.5
    padrao = prototipos.padronizar(filtradas)
    assert padrao[0, 1] > padrao[0, 0] and padrao[0, 2] == -numpy.inf
    juntas = prototipos.fundir(filtradas, filtradas)
    assert numpy.argmax(juntas[0]) == 1
