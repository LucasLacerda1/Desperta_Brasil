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


def test_palavras_esparsas_iguais_a_densas():
    vetores, rotulos = _exemplo()
    documentos = [(numpy.arange(5), v) for v in vetores]
    assert prototipos.notas_esparsas(documentos, rotulos, 5) == pytest.approx(prototipos.notas_densas(vetores, rotulos))


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


def test_tfidf_ignora_acento_e_palavras_vazias():
    documentos, tamanho = prototipos.tfidf(
        ["Demarcação de terras indígenas", "demarcacao das terras", "saúde da mulher", "saude publica"], {"de", "da"}
    )
    assert tamanho == 3  # demarcacao, terras, saude: as que aparecem em pelo menos 2 textos
    assert all(abs(numpy.linalg.norm(p) - 1) < 1e-9 for _, p in documentos if len(p))


def test_minimo_de_exemplos_e_fusao():
    rotulos = numpy.array([[1, 0, 0], [1, 0, 0], [0, 1, 0], [0, 1, 1]])
    notas = numpy.array([[0.1, 0.5, 0.9], [0.3, 0.2, 0.1], [0.2, 0.4, 0.6], [0.5, 0.1, 0.3]])
    filtradas = prototipos.com_minimo(notas, rotulos, minimo=2)
    assert numpy.all(filtradas[:, 2] == -numpy.inf) and filtradas[0, 1] == 0.5
    padrao = prototipos.padronizar(filtradas)
    assert padrao[0, 1] > padrao[0, 0] and padrao[0, 2] == -numpy.inf
    juntas = prototipos.fundir(filtradas, filtradas)
    assert numpy.argmax(juntas[0]) == 1
