"""
Experimento da busca, fora do portal: compara variacoes contra os julgamentos (julgamento.py).

Variacoes:
- palavras: o indice trecho_fts de hoje (OR das palavras, bm25).
- raiz: o mesmo, mas com a raiz das palavras (snowballstemmer, portugues; BSD-3): "professores" acha "professor".
- vetor: cosseno com os embeddings guardados em trecho_rag.
- vetor_w: o mesmo depois do whitening (media e covariancia de todos os trechos), que no estudo da
  PEC foi o unico ajuste que ajudou (23.9).
- combinacoes por RRF (k=60), com peso no vetor.
Em todas, os trechos sao juntados pela "chave" (a proposicao, para proposicao e tramitacao) antes de
cortar nos 8 primeiros: sem isso, as tramitacoes de uma mesma proposicao ocupam varios lugares.

Uso: python scripts/analise_busca/experimento.py [--sem-juntar] [--pendentes arquivo.json]
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata

import numpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import julgamento  # noqa: E402

K = 8
CANDIDATOS = 200
RRF_K = 60


def sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


class Raiz:
    def __init__(self):
        import snowballstemmer

        self.stemmer = snowballstemmer.stemmer("portuguese")

    def __call__(self, texto):
        palavras = re.findall(r"\w+", texto.lower())
        return " ".join(sem_acento(p) for p in self.stemmer.stemWords(palavras))


def carregar_trechos():
    from desperta.ext.db import db
    from desperta.ia.models import TrechoRAG

    linhas = db.session.execute(db.select(TrechoRAG.id, TrechoRAG.tipo, TrechoRAG.ref_id, TrechoRAG.texto, TrechoRAG.embedding)).all()
    ids = numpy.array([linha.id for linha in linhas])
    chaves = {}
    for linha in linhas:
        trecho = type("T", (), {"tipo": linha.tipo, "ref_id": linha.ref_id})
        chaves[linha.id] = julgamento.chave_do_trecho(trecho)
    textos = {linha.id: linha.texto for linha in linhas}
    matriz = numpy.frombuffer(b"".join(linha.embedding for linha in linhas), dtype=numpy.float32).reshape(len(linhas), -1)
    return ids, chaves, textos, matriz.astype(numpy.float64)


def indice_de_raizes(ids, textos, raiz):
    conexao = sqlite3.connect(":memory:")
    conexao.execute("CREATE VIRTUAL TABLE r USING fts5(texto, tokenize='unicode61 remove_diacritics 2')")
    conexao.executemany("INSERT INTO r(rowid, texto) VALUES (?, ?)", ((int(i), raiz(textos[int(i)])) for i in ids))
    return conexao


def buscar_raiz(conexao, raiz, consulta, limite):
    termos = raiz(consulta).split()
    if not termos:
        return []
    match = " OR ".join(f'"{t}"' for t in termos)
    return [linha[0] for linha in conexao.execute("SELECT rowid FROM r WHERE r MATCH ? ORDER BY bm25(r) LIMIT ?", (match, limite))]


def whitening(matriz):
    media = matriz.mean(axis=0)
    covariancia = numpy.cov((matriz - media).T)
    u, s, _ = numpy.linalg.svd(covariancia)
    w = u @ numpy.diag(1 / numpy.sqrt(s + 1e-6))
    return media, w


def normalizar(m):
    return m / numpy.linalg.norm(m, axis=-1, keepdims=True)


def rrf(listas):
    notas = {}
    for lista, peso in listas:
        for posicao, item in enumerate(lista, start=1):
            notas[item] = notas.get(item, 0) + peso / (RRF_K + posicao)
    return sorted(notas, key=notas.get, reverse=True)


def topo(ordem_trechos, chaves, juntar):
    saida = []
    for trecho_id in ordem_trechos:
        chave = chaves[int(trecho_id)]
        if juntar:
            if chave not in saida:
                saida.append(chave)
            if len(saida) == K:
                break
        else:
            if len(saida) == K:
                break
            saida.append(chave)
    return list(dict.fromkeys(saida))


def main():
    sys.path.insert(0, os.getcwd())
    parser = argparse.ArgumentParser()
    parser.add_argument("--sem-juntar", action="store_true")
    parser.add_argument("--pendentes", help="grava aqui os itens que ainda nao tem nota")
    argumentos = parser.parse_args()
    juntar = not argumentos.sem_juntar

    from app import app
    from desperta.ia import palavras, services

    with app.app_context():
        modelo = services.carregar_modelo()
        ids, chaves, textos, matriz = carregar_trechos()
        raiz = Raiz()
        conexao = indice_de_raizes(ids, textos, raiz)
        normal = normalizar(matriz)
        media, w = whitening(matriz)
        branco = normalizar((matriz - media) @ w)
        consultas = json.load(open(julgamento.CONSULTAS, encoding="utf-8"))["consultas"]
        julgados = julgamento._julgamentos()
        formulario = json.load(open(julgamento.FORMULARIO, encoding="utf-8"))
        conhecidos = {c["consulta"]: {i["chave"] for i in c["itens"]} for c in formulario["consultas"]}

        resultados = {}
        for item in consultas:
            consulta = item["consulta"]
            q = numpy.frombuffer(modelo.embutir([consulta])[0], dtype=numpy.float32).astype(numpy.float64)
            vetor = [int(i) for i in ids[numpy.argsort(-(normal @ normalizar(q)))[:CANDIDATOS]]]
            vetor_w = [int(i) for i in ids[numpy.argsort(-(branco @ normalizar((q - media) @ w)))[:CANDIDATOS]]]
            pal = palavras.buscar(consulta, CANDIDATOS)
            rai = buscar_raiz(conexao, raiz, consulta, CANDIDATOS)
            variacoes = {
                "palavras": pal,
                "raiz": rai,
                "vetor": vetor,
                "vetor_w": vetor_w,
                "hibrida_peso (hoje)": rrf([(pal, 1.0), (vetor, 0.5)]),
                "raiz+vetor_w 0,5": rrf([(rai, 1.0), (vetor_w, 0.5)]),
                "raiz+vetor_w 1,0": rrf([(rai, 1.0), (vetor_w, 1.0)]),
                "raiz+vetor 0,5": rrf([(rai, 1.0), (vetor, 0.5)]),
            }
            for nome, ordem in variacoes.items():
                resultados.setdefault(nome, {})[consulta] = topo(ordem, chaves, juntar)

        pendentes = {}
        print(f"Juntando por proposicao: {'sim' if juntar else 'nao'}. Itens por consulta: ate {K}.")
        for nome, por_consulta in resultados.items():
            linha = [nome.ljust(20)]
            for pessoa, notas in julgados.items():
                conta = {2: 0, 1: 0, 0: 0, None: 0}
                for consulta, chaves_achadas in por_consulta.items():
                    for chave in chaves_achadas:
                        nota = notas.get((consulta, chave))
                        conta[nota] += 1
                        if nota is None and chave not in conhecidos.get(consulta, set()):
                            pendentes.setdefault(consulta, set()).add(chave)
                julgados_n = conta[2] + conta[1] + conta[0]
                linha.append(
                    f"{pessoa}: responde {conta[2]}, relacionado {conta[1]}, fora {conta[0]}, sem nota {conta[None]}"
                    + (f" (responde {round(100 * conta[2] / julgados_n)}% dos julgados)" if julgados_n else "")
                )
            print(" | ".join(linha))
        if argumentos.pendentes:
            with open(argumentos.pendentes, "w", encoding="utf-8") as arq:
                json.dump({c: sorted(v) for c, v in pendentes.items()}, arq, ensure_ascii=False, indent=2)
            print(f"{sum(len(v) for v in pendentes.values())} itens sem nota em {argumentos.pendentes}")


if __name__ == "__main__":
    main()
