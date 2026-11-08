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


def notas_esparsas(documentos, rotulos, tamanho_vocabulario):
    """O mesmo para palavras: documentos = lista de (indices, pesos), cada um ja normalizado."""
    rotulos = numpy.asarray(rotulos, dtype=numpy.float64)
    somas = numpy.zeros((rotulos.shape[1], tamanho_vocabulario))
    for (indices, pesos), linha in zip(documentos, rotulos):
        for tema in numpy.flatnonzero(linha):
            somas[tema, indices] += pesos
    produtos = numpy.array([somas[:, indices] @ pesos for indices, pesos in documentos]).reshape(len(documentos), -1)
    quadrados = numpy.array([float(pesos @ pesos) for _, pesos in documentos])[:, None]
    normas_somas = (somas**2).sum(axis=1)[None, :]
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


def tfidf(textos, vazias, minimo=2):
    """(documentos, tamanho do vocabulario): cada documento = (indices, pesos) com norma 1."""
    vazias = {_sem_acento(p) for p in vazias}
    palavras = [[p for p in PALAVRA.findall(_sem_acento(t)) if len(p) >= 3 and p not in vazias] for t in textos]
    frequencia = Counter(p for lista in palavras for p in set(lista))
    vocabulario = {p: i for i, p in enumerate(sorted(p for p, n in frequencia.items() if n >= minimo))}
    total = len(textos)
    documentos = []
    for lista in palavras:
        contagem = Counter(p for p in lista if p in vocabulario)
        indices = numpy.array([vocabulario[p] for p in contagem], dtype=numpy.int64)
        pesos = numpy.array([n * math.log(total / frequencia[p]) for p, n in contagem.items()])
        norma = numpy.linalg.norm(pesos)
        documentos.append((indices, pesos / norma if norma else pesos))
    return documentos, len(vocabulario)


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
