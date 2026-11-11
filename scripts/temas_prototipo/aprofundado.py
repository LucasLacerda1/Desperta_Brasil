"""
Bateria aprofundada do tema pelo prototipo e pelos vizinhos (sem treinar a RoBERTaLexPT):

1. todas as formas, com intervalo de confianca de 95% (bootstrap de 1.000 reamostragens);
2. comparacoes pareadas entre as formas principais;
3. validacao no tempo: as 20% proposicoes mais recentes avaliadas so com as 80% mais antigas como base;
4. robustez do numero de vizinhos e do minimo de exemplos por tema;
5. acerto por nivel de confianca (quantas das 5 leituras concordam com a resposta final);
6. por tipo e por tema; sugestoes para as proposicoes sem tema, com o nivel de confianca.

    python scripts/temas_prototipo/aprofundado.py

Nao grava nada no banco. Resultado em instance/analise_temas/<data>_aprofundado/resultado.json.
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime

import numpy

import avaliar
import prototipos

REAMOSTRAGENS = 1000
FRACAO_RECENTE = 0.2
VIZINHOS = avaliar.VIZINHOS
MINIMO = avaliar.MINIMO_POR_TEMA


# ======================================================
# TRECHOS DO RAG -> PROPOSICOES
# ======================================================
def trechos_do_rag(app, todas):
    """Vetores de todos os trechos do RAG e, para cada um, as proposicoes a que ele pertence."""
    from desperta.ext.db import db
    from desperta.ia.models import TrechoRAG
    from desperta.orgaos.models import PautaItem
    from desperta.votacoes.models import Votacao, VotacaoProposicao

    pauta = {
        (e, o): p
        for e, o, p in db.session.execute(db.select(PautaItem.evento_id, PautaItem.ordem, PautaItem.proposicao_id))
    }
    afetadas = defaultdict(set)
    for votacao, proposicao in db.session.execute(
        db.select(VotacaoProposicao.votacao_id, VotacaoProposicao.proposicao_id)
    ):
        afetadas[votacao].add(proposicao)
    for votacao, proposicao in db.session.execute(db.select(Votacao.id, Votacao.proposicao_id)):
        if proposicao:
            afetadas[votacao].add(proposicao)

    def proposicoes(tipo, ref):
        if tipo == "proposicao":
            return {int(ref)}
        if tipo == "tramitacao":
            return {int(ref.split("/")[0])}
        if tipo == "pauta_item":
            evento, ordem = ref.split("/")
            p = pauta.get((int(evento), int(ordem)))
            return {p} if p else set()
        if tipo == "votacao":
            return afetadas.get(ref, set())
        return set()

    vetores, donos, tipos = [], [], []
    consulta = db.select(TrechoRAG.tipo, TrechoRAG.ref_id, TrechoRAG.embedding).filter_by(
        modelo_embedding=app.config["EMBEDDING_MODEL"]
    )
    for tipo, ref, embedding in db.session.execute(consulta):
        vetores.append(numpy.frombuffer(embedding, dtype=numpy.float32))
        donos.append(proposicoes(tipo, ref))
        tipos.append(tipo)
    return numpy.array(vetores, dtype=numpy.float64), donos, tipos


def leitura_rag(consultas_brancas, trechos_brancos, donos, linha_da_prop, rotulos, ids_consulta):
    """Quinta leitura: os 25 trechos do RAG mais parecidos votam com os temas das suas proposicoes."""
    rotulos_trecho = numpy.zeros((len(donos), rotulos.shape[1]), dtype=numpy.float32)
    for j, props in enumerate(donos):
        for p in props:
            linha = linha_da_prop.get(p)
            if linha is not None:
                rotulos_trecho[j] = numpy.maximum(rotulos_trecho[j], rotulos[linha])
    votam = numpy.flatnonzero(rotulos_trecho.any(axis=1))
    posicao = {int(j): i for i, j in enumerate(votam)}
    trechos_da_prop = defaultdict(list)
    for j in votam:
        for p in donos[j]:
            trechos_da_prop[p].append(posicao[int(j)])
    excluir = [trechos_da_prop.get(i, []) for i in ids_consulta]
    return prototipos.notas_vizinhos_externos(
        consultas_brancas, trechos_brancos[votam], rotulos_trecho[votam], VIZINHOS, excluir
    )


# ======================================================
# AS LEITURAS
# ======================================================
def leituras(vetores_brancos, palavras, rotulos, rag, k=VIZINHOS, minimo=MINIMO):
    m = lambda notas: prototipos.com_minimo(notas, rotulos, minimo)  # noqa: E731
    return {
        "vizinhos_roberta": m(prototipos.notas_vizinhos(vetores_brancos, rotulos, k)),
        "vizinhos_palavras": m(prototipos.notas_vizinhos(palavras, rotulos, k)),
        "prototipo_roberta": m(prototipos.notas_densas(vetores_brancos, rotulos)),
        "prototipo_palavras": m(prototipos.notas_densas(palavras, rotulos)),
        "vizinhos_rag": m(rag),
    }


def combinacoes(lidas):
    quatro = [lidas[k] for k in ("vizinhos_roberta", "vizinhos_palavras", "prototipo_roberta", "prototipo_palavras")]
    return {
        "Protótipos: Roberta com whitening + palavras": prototipos.fundir(
            lidas["prototipo_roberta"], lidas["prototipo_palavras"]
        ),
        "Vizinhos: Roberta com whitening + palavras": prototipos.fundir(
            lidas["vizinhos_roberta"], lidas["vizinhos_palavras"]
        ),
        "Vizinhos no RAG (com whitening)": lidas["vizinhos_rag"],
        "4 leituras (vizinhos + protótipos)": prototipos.fundir(*quatro),
        "5 leituras (4 + vizinhos no RAG)": prototipos.fundir(*quatro, lidas["vizinhos_rag"]),
    }


# ======================================================
# ESTATISTICA
# ======================================================
def intervalo(acertos, sorteios):
    medias = acertos[sorteios].mean(axis=1)
    return float(acertos.mean()), float(numpy.percentile(medias, 2.5)), float(numpy.percentile(medias, 97.5))


def diferenca(acertos_a, acertos_b, sorteios):
    medias = (acertos_a.astype(float) - acertos_b)[sorteios].mean(axis=1)
    return {
        "diferenca": float((acertos_a.astype(float) - acertos_b).mean()),
        "ic95": [float(numpy.percentile(medias, 2.5)), float(numpy.percentile(medias, 97.5))],
        "chance_de_ser_zero_ou_menos": float((medias <= 0).mean()),
    }


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, raiz)
    from desperta import create_app
    from desperta.ext.db import db
    from desperta.ia import embeddings
    from desperta.proposicoes.models import Proposicao

    app = create_app()
    with app.app_context():
        config = app.config
        pasta_modelo = embeddings.caminho_no_projeto(app, config["ROBERTA_DIR"])
        if embeddings.arquivos_faltando(pasta_modelo):
            sys.exit(f"RoBERTaLexPT não encontrada em {pasta_modelo}. O pendrive está conectado?")
        embeddings.preparar_ambiente(app)
        dispositivo = embeddings.escolher_dispositivo(config["IA_DISPOSITIVO"])
        inicio = time.monotonic()

        temas, com_tema, sem_tema, rotulos = avaliar.carregar(app)
        todas = com_tema + sem_tema
        n = len(com_tema)
        datas = dict(db.session.execute(db.select(Proposicao.id, Proposicao.data_apresentacao)).all())
        linha_da_prop = {p["id"]: i for i, p in enumerate(todas)}
        ids = [p["id"] for p in todas]

        modelo = embeddings.ModeloEmbedding(config["EMBEDDING_MODEL"], pasta=pasta_modelo, dispositivo=dispositivo)
        vetores = numpy.array(
            [numpy.frombuffer(b, dtype=numpy.float32) for b in modelo.embutir([p["ementa"] for p in todas])],
            dtype=numpy.float64,
        )
        brancos = prototipos.whitening(vetores)
        palavras = prototipos.tfidf([p["ementa"] for p in todas], avaliar.PALAVRAS_VAZIAS, pares=True)
        trechos, donos, tipos_trecho = trechos_do_rag(app, todas)
        media_trechos = trechos.mean(axis=0)
        direcoes, variancias, _ = numpy.linalg.svd(numpy.cov((trechos - media_trechos).T))
        matriz = direcoes / numpy.sqrt(numpy.maximum(variancias, 1e-12))
        trechos_brancos = prototipos.normalizar_linhas((trechos - media_trechos) @ matriz).astype(numpy.float32)
        consultas_brancas = prototipos.normalizar_linhas((vetores - media_trechos) @ matriz).astype(numpy.float32)

        def rag_com(rotulos_usados):
            return leitura_rag(consultas_brancas, trechos_brancos, donos, linha_da_prop, rotulos_usados, ids)

        # 1. Todas as formas
        notas = {
            "Roberta original (protótipo)": prototipos.notas_densas(vetores, rotulos),
            "Roberta centralizada (protótipo)": prototipos.notas_densas(prototipos.centralizar(vetores), rotulos),
            "Roberta com whitening (protótipo)": prototipos.notas_densas(brancos, rotulos),
            "Só palavras, TF-IDF (protótipo)": prototipos.notas_densas(palavras, rotulos),
        }
        lidas = leituras(brancos, palavras, rotulos, rag_com(rotulos))
        notas |= combinacoes(lidas)
        verdade = rotulos[:n]
        acertos = {nome: prototipos.medir(x[:n], verdade) for nome, x in notas.items()}
        sorteios = numpy.random.default_rng(2026).integers(0, n, size=(REAMOSTRAGENS, n))
        formas = {}
        for nome, m in acertos.items():
            formas[nome] = {"top1": intervalo(m["top1"], sorteios), "top3": intervalo(m["top3"], sorteios)}
        acaso1, acaso3 = prototipos.acaso(verdade)
        maioria1, maioria3 = prototipos.maioria(verdade)

        # 2. Comparacoes pareadas
        pares = [
            ("5 leituras (4 + vizinhos no RAG)", "4 leituras (vizinhos + protótipos)"),
            ("4 leituras (vizinhos + protótipos)", "Protótipos: Roberta com whitening + palavras"),
            ("Roberta com whitening (protótipo)", "Só palavras, TF-IDF (protótipo)"),
            ("Roberta com whitening (protótipo)", "Roberta original (protótipo)"),
        ]
        pareadas = {f"{a} − {b}": diferenca(acertos[a]["top1"], acertos[b]["top1"], sorteios) for a, b in pares}

        # 3. Validacao no tempo
        ordem_tempo = sorted(range(n), key=lambda i: (datas[com_tema[i]["id"]], com_tema[i]["id"]))
        corte = int(n * (1 - FRACAO_RECENTE))
        recentes = numpy.array(ordem_tempo[corte:])
        rotulos_antigos = rotulos.copy()
        rotulos_antigos[recentes] = 0
        lidas_tempo = leituras(brancos, palavras, rotulos_antigos, rag_com(rotulos_antigos))
        tempo = {}
        for nome, x in combinacoes(lidas_tempo).items():
            m = prototipos.medir(x[recentes], rotulos[recentes])
            tempo[nome] = {"top1": float(m["top1"].mean()), "top3": float(m["top3"].mean())}
        datas_corte = [
            str(datas[com_tema[ordem_tempo[0]]["id"]].date()),
            str(datas[com_tema[ordem_tempo[corte]]["id"]].date()),
            str(datas[com_tema[ordem_tempo[-1]]["id"]].date()),
        ]

        # 4. Robustez
        robustez_k, robustez_minimo = {}, {}
        for k in (5, 10, 25, 50, 100):
            x = combinacoes(leituras(brancos, palavras, rotulos, rag_com(rotulos), k=k))[
                "5 leituras (4 + vizinhos no RAG)"
            ]
            m = prototipos.medir(x[:n], verdade)
            robustez_k[k] = {"top1": float(m["top1"].mean()), "top3": float(m["top3"].mean())}
        for minimo in (1, 5, 20, 50):
            x = combinacoes(leituras(brancos, palavras, rotulos, rag_com(rotulos), minimo=minimo))[
                "5 leituras (4 + vizinhos no RAG)"
            ]
            m = prototipos.medir(x[:n], verdade)
            robustez_minimo[minimo] = {"top1": float(m["top1"].mean()), "top3": float(m["top3"].mean())}

        # 5. Confianca: quantas das 5 leituras dao o mesmo 1o lugar que a resposta final
        final = notas["5 leituras (4 + vizinhos no RAG)"]
        primeiro = final.argmax(axis=1)
        concordam = sum((lida.argmax(axis=1) == primeiro).astype(int) for lida in lidas.values())
        certo = verdade[numpy.arange(n), primeiro[:n]] == 1
        confianca = {}
        for faixa, filtro in (("5 de 5", concordam == 5), ("4 de 5", concordam == 4), ("3 de 5", concordam == 3)):
            confianca[faixa] = {
                "fracao": float(filtro[:n].mean()),
                "acerto": float(certo[filtro[:n]].mean()) if filtro[:n].any() else None,
                "sem_tema": int(filtro[n:].sum()),
            }
        baixa = concordam <= 2
        confianca["2 de 5 ou menos"] = {
            "fracao": float(baixa[:n].mean()),
            "acerto": float(certo[baixa[:n]].mean()) if baixa[:n].any() else None,
            "sem_tema": int(baixa[n:].sum()),
        }

        # 6. Por tipo, por tema e sugestoes
        m_final = acertos["5 leituras (4 + vizinhos no RAG)"]
        por_tipo = {}
        for tipo in sorted({p["tipo"] for p in com_tema}, key=lambda t: -sum(p["tipo"] == t for p in com_tema)):
            linhas = numpy.array([i for i, p in enumerate(com_tema) if p["tipo"] == tipo])
            por_tipo[tipo] = {
                "quantas": int(len(linhas)),
                "top1": float(m_final["top1"][linhas].mean()),
                "top3": float(m_final["top3"][linhas].mean()),
            }
        ordem = numpy.argsort(-final, axis=1, kind="stable")
        por_tema = []
        for t, nome in enumerate(temas):
            linhas = numpy.flatnonzero(verdade[:, t])
            if len(linhas):
                por_tema.append(
                    {
                        "tema": nome,
                        "quantas": int(len(linhas)),
                        "top1": float((ordem[linhas, 0] == t).mean()),
                        "top3": float((ordem[linhas, :3] == t).any(axis=1).mean()),
                    }
                )
        sugestoes = [
            {
                "sigla": p["sigla"],
                "id": p["id"],
                "ementa": p["ementa"],
                "temas": [temas[t] for t in ordem[n + j, :3]],
                "leituras_que_concordam": int(concordam[n + j]),
            }
            for j, p in enumerate(sem_tema)
        ]

        resultado = {
            "quando": datetime.now().isoformat(timespec="minutes"),
            "dispositivo": embeddings.nome_do_dispositivo(dispositivo),
            "proposicoes_avaliadas": n,
            "sem_tema": len(sem_tema),
            "temas": len(temas),
            "trechos_do_rag": {t: tipos_trecho.count(t) for t in sorted(set(tipos_trecho))},
            "reamostragens": REAMOSTRAGENS,
            "acaso": {"top1": acaso1, "top3": acaso3},
            "temas_mais_comuns": {"top1": maioria1, "top3": maioria3},
            "formas": formas,
            "pareadas": pareadas,
            "tempo": {"datas": datas_corte, "avaliadas": int(len(recentes)), "formas": tempo},
            "robustez_vizinhos": robustez_k,
            "robustez_minimo": robustez_minimo,
            "confianca": confianca,
            "por_tipo": por_tipo,
            "por_tema": sorted(por_tema, key=lambda item: -item["top3"]),
            "sugestoes": sugestoes,
            "duracao_s": round(time.monotonic() - inicio, 1),
        }
        destino = os.path.join(app.instance_path, "analise_temas", f"{datetime.now():%Y-%m-%d_%H%M}_aprofundado")
        os.makedirs(destino, exist_ok=True)
        with open(os.path.join(destino, "resultado.json"), "w", encoding="utf-8") as arquivo:
            json.dump(resultado, arquivo, ensure_ascii=False, indent=2)
        print(
            json.dumps(
                {k: v for k, v in resultado.items() if k not in ("sugestoes", "por_tema")}, ensure_ascii=False, indent=1
            )
        )
        print(f"Salvo em {destino}")


if __name__ == "__main__":
    main()
