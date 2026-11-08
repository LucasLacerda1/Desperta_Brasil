"""
Tema pelo prototipo: o vetor medio das ementas de cada tema. Contas sem modelo (so numpy), testadas
em tests/test_temas_prototipo.py.

Deixar uma de fora: o prototipo de um tema e a soma dos vetores das suas proposicoes (o cosseno nao muda
com a escala, entao soma e media dao a mesma ordem). Tirar a proposicao avaliada e subtrair o vetor dela
da soma; com isso, as notas de todas as proposicoes saem de uma multiplicacao de matrizes:

    nota(i, t) = (s_t . x_i - [i em t] |x_i|^2) / |s_t - [i em t] x_i|
"""

import math
import re
import unicodedata
from collections import Counter

import numpy

PALAVRA = re.compile(r"\w+")


# ======================================================
# NOTAS DOS TEMAS (deixando a proposicao avaliada de fora)
# ======================================================
def notas_densas(vetores, rotulos):
    """
    vetores: N x D; rotulos: N x T (1 se a proposicao tem o tema). Devolve N x T com o cosseno de cada
    proposicao com o prototipo de cada tema sem ela; tema que ficaria vazio sem ela = -inf.
    """
    vetores = numpy.asarray(vetores, dtype=numpy.float64)
    rotulos = numpy.asarray(rotulos, dtype=numpy.float64)
    somas = rotulos.T @ vetores  # T x D
    produtos = vetores @ somas.T  # N x T
    quadrados = (vetores**2).sum(axis=1)[:, None]  # N x 1
    normas_somas = (somas**2).sum(axis=1)[None, :]  # 1 x T
    return _cossenos(produtos, quadrados, normas_somas, rotulos)


def _cossenos(produtos, quadrados, normas_somas, rotulos):
    contagens = rotulos.sum(axis=0)[None, :] - rotulos
    numerador = produtos - rotulos * quadrados
    norma2 = normas_somas - rotulos * (2 * produtos - quadrados)
    validos = (contagens > 0) & (norma2 > 1e-12)
    notas = numpy.full(produtos.shape, -numpy.inf)
    notas[validos] = numerador[validos] / numpy.sqrt(norma2[validos])
    return notas


# ======================================================
# AJUSTES DOS VETORES (sem treino)
# ======================================================
def normalizar_linhas(matriz):
    normas = numpy.linalg.norm(matriz, axis=1, keepdims=True)
    return matriz / numpy.where(normas == 0, 1, normas)


def centralizar(vetores):
    return normalizar_linhas(vetores - vetores.mean(axis=0))


def whitening(vetores, dimensoes=None):
    """
    Su et al. (2021): tira a media, gira e reescala para que todas as direcoes tenham o mesmo peso;
    com dimensoes, fica so com as direcoes de maior variacao. Calculado sobre os proprios vetores, sem rotulos.
    """
    media = vetores.mean(axis=0)
    covariancia = numpy.cov((vetores - media).T)
    direcoes, variancias, _ = numpy.linalg.svd(covariancia)
    matriz = direcoes / numpy.sqrt(numpy.maximum(variancias, 1e-12))
    if dimensoes:
        matriz = matriz[:, :dimensoes]
    return normalizar_linhas((vetores - media) @ matriz)


# ======================================================
# PALAVRAS (adversario: TF-IDF, sem a Roberta)
# ======================================================
def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def tfidf(textos, vazias, minimo=3, pares=False):
    """
    Matriz textos x palavras (float32, cada linha com norma 1): peso (1 + log n) x log(N / df), sem acento,
    so palavras de 3+ letras fora das vazias e presentes em pelo menos `minimo` textos; com pares, tambem
    os pares de palavras seguidas ("codigo_penal").
    """
    vazias = {_sem_acento(p) for p in vazias}
    listas = []
    for texto in textos:
        palavras = [p for p in PALAVRA.findall(_sem_acento(texto)) if len(p) >= 3 and p not in vazias]
        if pares:
            palavras += [f"{a}_{b}" for a, b in zip(palavras, palavras[1:])]
        listas.append(palavras)
    frequencia = Counter(p for lista in listas for p in set(lista))
    vocabulario = {p: i for i, p in enumerate(sorted(p for p, n in frequencia.items() if n >= minimo))}
    matriz = numpy.zeros((len(textos), len(vocabulario)), dtype=numpy.float32)
    total = len(textos)
    for linha, lista in enumerate(listas):
        for palavra, n in Counter(p for p in lista if p in vocabulario).items():
            matriz[linha, vocabulario[palavra]] = (1 + math.log(n)) * math.log(total / frequencia[palavra])
    return normalizar_linhas(matriz)


# ======================================================
# VIZINHOS MAIS PARECIDOS (kNN)
# ======================================================
def notas_vizinhos(vetores, rotulos, k, bloco=2000):
    """
    Para cada proposicao, as k mais parecidas entre as que tem tema (sem ela mesma) votam: a nota de um
    tema e a soma das semelhancas das vizinhas que tem esse tema. Diferente do prototipo, um tema com
    assuntos muito diferentes ("guarda-chuva") e bem representado pelas vizinhas certas.
    """
    vetores = numpy.asarray(vetores, dtype=numpy.float32)
    rotulos = numpy.asarray(rotulos, dtype=numpy.float32)
    votantes = numpy.flatnonzero(rotulos.sum(axis=1) > 0)
    posicao_votante = {int(v): i for i, v in enumerate(votantes)}
    base, rotulos_votantes = vetores[votantes], rotulos[votantes]
    notas = numpy.zeros((len(vetores), rotulos.shape[1]))
    for inicio in range(0, len(vetores), bloco):
        fim = min(inicio + bloco, len(vetores))
        semelhancas = vetores[inicio:fim] @ base.T
        for linha in range(inicio, fim):
            if linha in posicao_votante:
                semelhancas[linha - inicio, posicao_votante[linha]] = -numpy.inf  # sem ela mesma
        vizinhas = numpy.argpartition(-semelhancas, k, axis=1)[:, :k]
        pesos = numpy.take_along_axis(semelhancas, vizinhas, axis=1).clip(min=0)
        notas[inicio:fim] = numpy.einsum("ik,ikt->it", pesos, rotulos_votantes[vizinhas])
    return notas


# ======================================================
# MEDIDAS
# ======================================================
def medir(notas, rotulos):
    """Por proposicao: posicao do melhor tema oficial, e se acertou no 1o lugar e entre os 3 primeiros."""
    rotulos = numpy.asarray(rotulos, dtype=bool)
    ordem = numpy.argsort(-notas, axis=1, kind="stable")
    posicoes = numpy.argmax(numpy.take_along_axis(rotulos, ordem, axis=1), axis=1) + 1
    return {"posicao": posicoes, "top1": posicoes == 1, "top3": posicoes <= 3}


def acaso(rotulos):
    """Acerto esperado sorteando a ordem dos temas: no 1o lugar e entre os 3 primeiros."""
    rotulos = numpy.asarray(rotulos, dtype=bool)
    total = rotulos.shape[1]
    k = rotulos.sum(axis=1)
    top1 = (k / total).mean()
    top3 = (1 - numpy.array([math.comb(total - n, 3) / math.comb(total, 3) for n in k])).mean()
    return float(top1), float(top3)


def maioria(rotulos):
    """Adversario: dar sempre os temas mais frequentes, na mesma ordem para todas."""
    rotulos = numpy.asarray(rotulos, dtype=bool)
    frequentes = numpy.argsort(-rotulos.sum(axis=0), kind="stable")
    return float(rotulos[:, frequentes[0]].mean()), float(rotulos[:, frequentes[:3]].any(axis=1).mean())


# ======================================================
# AJUSTES DAS NOTAS
# ======================================================
def com_minimo(notas, rotulos, minimo):
    """Tema com menos de `minimo` proposicoes no banco nao entra: um prototipo de poucas ementas e ruido."""
    poucos = numpy.asarray(rotulos).sum(axis=0) < minimo
    resultado = notas.copy()
    resultado[:, poucos] = -numpy.inf
    return resultado


def padronizar(notas):
    """Em cada linha: (nota - media) / desvio, so entre os temas validos; os invalidos continuam -inf."""
    validos = numpy.isfinite(notas)
    resultado = numpy.full(notas.shape, -numpy.inf)
    for i, linha in enumerate(notas):
        v = linha[validos[i]]
        if v.size == 0:
            continue
        desvio = v.std() or 1.0
        resultado[i, validos[i]] = (v - v.mean()) / desvio
    return resultado


def fundir(*listas_de_notas):
    """Soma das notas padronizadas (como a busca hibrida junta vetores e palavras)."""
    return sum(padronizar(n) for n in listas_de_notas)
