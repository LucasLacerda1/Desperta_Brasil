"""
Grade de experimentos da analise da PEC: varias formas de ler e de comparar, medidas com notas
continuas (0,5 = acaso, 1 = perfeito) e correlacionadas entre si.

    python scripts/analise_pec/experimentos.py

Variacoes: camada do vetor x leitura (frase sozinha, encadeada, + contexto inicial) x centralizacao,
e, dentro de cada uma, os metodos de cada teste (A: contra a PEC, centralidade, escolha por pedaco;
D: nome do tema, prototipo do tema; E: remocao, surpresa; blocos: planta junta, blocos sozinhos).
Nao treina nada e nao grava no banco. Resultado em instance/analise_pec/rodadas/<data>_experimentos/.
"""

import json
import os
import random
import statistics
import sys
import time
import unicodedata
from datetime import datetime

import numpy

import avaliacao
import leitura
import rodar

CAMADAS = {"ultima": None, "4_ultimas": (9, 10, 11, 12), "camada_8": (8,), "todas": tuple(range(1, 13))}
LEITURAS = ("solta", "encadeada", "contexto")
EMENTAS_POR_TEMA = 60
EMENTAS_PARA_A_MEDIA = 1000


def _chave(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _centralizar(vetor, media_global):
    return leitura.normalizar(vetor - media_global) if media_global is not None else vetor


def ementas_do_banco(pec_id):
    """Ementas por tema (prototipos do teste D) e uma amostra para o vetor medio (centralizacao)."""
    from desperta.ext.db import db
    from desperta.proposicoes.models import Proposicao, ProposicaoTema, Tema

    linhas = db.session.execute(
        db.select(Tema.nome, Proposicao.ementa)
        .join(ProposicaoTema, ProposicaoTema.cod_tema == Tema.cod_tema)
        .join(Proposicao, Proposicao.id == ProposicaoTema.proposicao_id)
        .where(Proposicao.id != pec_id)
        .order_by(Proposicao.id)
    ).all()
    sorteio = random.Random(pec_id)
    por_tema = {}
    for tema, ementa in linhas:
        por_tema.setdefault(tema, []).append(ementa)
    por_tema = {t: sorteio.sample(e, min(EMENTAS_POR_TEMA, len(e))) for t, e in por_tema.items()}
    todas = sorted({e for _, e in linhas})
    return por_tema, sorteio.sample(todas, min(EMENTAS_PARA_A_MEDIA, len(todas)))


def vetores_dos_blocos(leitor, modelos):
    blocos = [(nome, f"{nome}: {texto}") for nome, texto in modelos["planta_padrao"]["blocos"].items()]
    ids, intervalos = leitor.tokenizar_frases(blocos)
    estados = leitor.ler([([], ids[: 2 * leitura.METADE])])[0]
    juntos = {nome: leitura.media(estados[inicio:fim]) for nome, inicio, fim in intervalos}
    sozinhos = dict(zip([n for n, _ in blocos], leitor.vetores([t for _, t in blocos])))
    return juntos, sozinhos


def medir(contexto_fixo, lida, surpresas, media_global, frases, pedacos, leitores):
    """Todas as notas de uma variacao (leitura + camada + centralizacao), para cada leitor."""
    vetores_soltos, blocos_juntos, blocos_sozinhos, temas, prototipos, ementas, pec_id, oficiais, resumos = (
        contexto_fixo
    )
    c = lambda v: _centralizar(v, media_global)  # noqa: E731
    frase = {k: c(v) for k, v in lida.vetor_frase.items()}
    pec = leitura.normalizar(numpy.mean(list(frase.values()), axis=0))
    cos = leitura.cosseno

    # A: tres formas de ordenar as frases
    contra_pec = {k: cos(v, pec) for k, v in frase.items()}
    centralidade = {k: statistics.mean(cos(v, w) for j, w in frase.items() if j != k) for k, v in frase.items()}
    por_pedaco = dict(contra_pec)
    for p in pedacos:
        codigos = [k for k, _ in p]
        vetor_pedaco = leitura.normalizar(numpy.mean([frase[k] for k in codigos], axis=0))
        vencedora = max(codigos, key=lambda k: cos(frase[k], vetor_pedaco))
        por_pedaco[vencedora] = 2 + cos(vetor_pedaco, pec)  # as vencedoras ficam acima de todas

    # Blocos, a partir das frases lidas sozinhas
    certos = {f["codigo"]: f["bloco_certo"] for f in frases}

    def blocos(vetores_bloco):
        vb = {n: c(v) for n, v in vetores_bloco.items()}
        escolhidos = {k: max(vb, key=lambda n: cos(vb[n], c(v))) for k, v in vetores_soltos.items()}
        return sum(avaliacao.bloco_bate(escolhidos[k], certos[k]) for k in certos) / len(certos)

    # D: nome do tema e prototipo do tema
    nota_tema_nome = {t: cos(c(v), pec) for t, v in temas.items()}
    nota_tema_proto = {t: cos(c(v), pec) for t, v in prototipos.items()}

    def posicao_oficial(notas):
        ordem = sorted(notas, key=lambda t: -notas[t])
        return statistics.mean(
            avaliacao.nota_da_posicao(ordem.index(t) + 1, len(ordem)) for t in oficiais if t in notas
        )

    linha = {
        "blocos_planta_junta": blocos(blocos_juntos),
        "blocos_sozinhos": blocos(blocos_sozinhos),
        "D_nome_oficial": posicao_oficial(nota_tema_nome),
        "D_prototipo_oficial": posicao_oficial(nota_tema_proto),
    }
    for nome, interpretacao in leitores.items():
        escolhidas = set(rodar._codigos(interpretacao.get("frases_importantes", [])))
        temas_leitor = {t for t in interpretacao.get("temas", []) if not t.startswith("<")}
        palavras = {_chave(p) for p in interpretacao.get("palavras_chave", []) if not p.startswith("<")}
        vetores_resumo, certas, vetor_resumo_todo = resumos[nome]
        notas_b = []
        for v, (_, conjunto) in zip(vetores_resumo, certas):
            ordem = sorted(frase, key=lambda k: -cos(frase[k], c(v)))
            melhor = min(ordem.index(k) + 1 for k in conjunto if k in frase)
            notas_b.append(avaliacao.nota_da_posicao(melhor, len(ordem)))
        ordem_c = sorted(ementas, key=lambda k: -cos(c(ementas[k]), c(vetor_resumo_todo)))
        pesos = {_chave(p): v for p, v in lida.pesos_palavras.items()}
        surpresa = {_chave(p): v for p, v in surpresas.items()}
        linha |= {
            f"A_contra_pec|{nome}": avaliacao.auc(contra_pec, escolhidas),
            f"A_centralidade|{nome}": avaliacao.auc(centralidade, escolhidas),
            f"A_por_pedaco|{nome}": avaliacao.auc(por_pedaco, escolhidas),
            f"B|{nome}": statistics.mean(notas_b) if notas_b else None,
            f"C|{nome}": avaliacao.nota_da_posicao(ordem_c.index(pec_id) + 1, len(ordem_c)),
            f"D_nome|{nome}": avaliacao.auc(nota_tema_nome, temas_leitor),
            f"D_prototipo|{nome}": avaliacao.auc(nota_tema_proto, temas_leitor),
            f"E_remocao|{nome}": avaliacao.auc(pesos, palavras),
            f"E_surpresa|{nome}": avaliacao.auc(surpresa, palavras),
        }
    return linha


def surpresas_da_leitura(leitor, lida, modo, frases, pedacos):
    resultado = {}
    unidades = (
        [(lida.contexto_da_frase[k], t) for k, t in frases]
        if modo == "solta"
        else [(lida.contexto_da_frase[p[0][0]], " ".join(t for _, t in p)) for p in pedacos]
    )
    for contexto, texto in unidades:
        for palavra, valor in leitor.surpresas(contexto, texto).items():
            resultado[palavra] = max(resultado.get(palavra, 0.0), valor)
    return resultado


# ======================================================
# RELATORIO
# ======================================================
def _f(valor):
    return "-" if valor is None else f"{valor:.2f}"


def relatorio(linhas, leitores, duracao, dispositivo):
    metricas = [k for k in linhas[0] if k not in ("camada", "leitura", "centralizar")]
    texto = [
        "# Grade de experimentos — PEC 319/2004",
        "",
        f"{datetime.now():%d/%m/%Y %H:%M} · {dispositivo} · {len(linhas)} variações · {duracao:.0f} s",
        "",
        "Notas de 0 a 1: **0,5 é o acaso** (A, D por leitor e E são AUC; B, C e D oficial são a posição da resposta "
        "certa; blocos é a fração certa, e responder sempre o maior bloco dá 0,36). Uma PEC só e 22 frases: "
        "diferenças pequenas podem ser sorte. Confirmar nas PECs de conferência antes de decidir.",
        "",
        "## Efeito de cada opção (média de cada nota sobre as outras opções)",
        "",
    ]
    for dimensao, opcoes in (("camada", list(CAMADAS)), ("leitura", list(LEITURAS)), ("centralizar", [False, True])):
        texto += [
            f"### {dimensao}",
            "",
            "| Nota | " + " | ".join(map(str, opcoes)) + " |",
            "|---|" + "---|" * len(opcoes),
        ]
        for m in metricas:
            valores = []
            for o in opcoes:
                xs = [r[m] for r in linhas if r[dimensao] == o and r[m] is not None]
                valores.append(_f(statistics.mean(xs)) if xs else "-")
            texto.append(f"| {m} | " + " | ".join(valores) + " |")
        texto.append("")
    texto += [
        "## Melhor variação em cada nota",
        "",
        "| Nota | Melhor | Variação | Pior | Mediana |",
        "|---|---|---|---|---|",
    ]
    for m in metricas:
        validas = [r for r in linhas if r[m] is not None]
        if not validas:
            continue
        melhor = max(validas, key=lambda r: r[m])
        texto.append(
            f"| {m} | {_f(melhor[m])} | {melhor['camada']}, {melhor['leitura']}, "
            f"{'centralizado' if melhor['centralizar'] else 'sem centralizar'} | "
            f"{_f(min(r[m] for r in validas))} | {_f(statistics.median(r[m] for r in validas))} |"
        )
    # Correlacoes entre as notas, ao longo das variacoes
    principais = [m for m in metricas if not m.startswith("blocos") and not m.startswith("D_") or "|" in m]
    texto += [
        "",
        "## Correlação entre as notas ao longo das variações (Spearman)",
        "",
        "Perto de 1: as duas notas sobem e descem juntas (a mesma variação melhora as duas). Perto de -1: o que "
        "melhora uma piora a outra. Perto de 0: independentes.",
        "",
    ]
    nomes = [m for m in principais if m.endswith("|" + list(leitores)[0])] + [
        "blocos_planta_junta",
        "blocos_sozinhos",
        "D_nome_oficial",
        "D_prototipo_oficial",
    ]
    curtos = [n.split("|")[0] for n in nomes]
    texto += ["| | " + " | ".join(curtos) + " |", "|---|" + "---|" * len(nomes)]
    for a, ca in zip(nomes, curtos):
        celulas = []
        for b in nomes:
            pares = [(r[a], r[b]) for r in linhas if r[a] is not None and r[b] is not None]
            rho = avaliacao.spearman([p[0] for p in pares], [p[1] for p in pares]) if pares else None
            celulas.append(_f(rho))
        texto.append(f"| {ca} | " + " | ".join(celulas) + " |")
    if len(leitores) >= 2:
        l1, l2 = list(leitores)[:2]
        texto += ["", f"## Os dois leitores ({l1} e {l2}) preferem as mesmas variações?", ""]
        for m in sorted({m.split("|")[0] for m in metricas if "|" in m}):
            pares = [
                (r[f"{m}|{l1}"], r[f"{m}|{l2}"])
                for r in linhas
                if r[f"{m}|{l1}"] is not None and r[f"{m}|{l2}"] is not None
            ]
            rho = avaliacao.spearman([p[0] for p in pares], [p[1] for p in pares]) if pares else None
            texto.append(f"- **{m}:** Spearman {_f(rho)}")
    texto += ["", "## Todas as variações", "", "| Camada | Leitura | Centralizar | " + " | ".join(metricas) + " |"]
    texto.append("|---|---|---|" + "---|" * len(metricas))
    for r in linhas:
        texto.append(
            f"| {r['camada']} | {r['leitura']} | {'sim' if r['centralizar'] else 'não'} | "
            + " | ".join(_f(r[m]) for m in metricas)
            + " |"
        )
    return "\n".join(texto) + "\n"


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from desperta import create_app
    from desperta.ia import embeddings

    app = create_app()
    with app.app_context():
        pasta_modelo = embeddings.caminho_no_projeto(app, app.config["ROBERTA_DIR"])
        if embeddings.arquivos_faltando(pasta_modelo):
            sys.exit(f"RoBERTaLexPT não encontrada em {pasta_modelo}. O pendrive está conectado?")
        embeddings.preparar_ambiente(app)
        dispositivo = embeddings.escolher_dispositivo(app.config["IA_DISPOSITIVO"])
        pasta = os.path.join(app.instance_path, "analise_pec")
        frases_json, pec_id, leitores, modelos = rodar.carregar_pec(pasta, "PEC_319_2004")
        sigla, autor, ementa, oficiais, temas_todos, ementas, _ = rodar.carregar_do_banco(pec_id)
        por_tema, amostra = ementas_do_banco(pec_id)

        inicio = time.monotonic()
        leitor = leitura.Leitor(pasta_modelo, dispositivo)
        frases = [(f["codigo"], f["texto"]) for f in frases_json]
        numeros = sorted({f["pedaco"] for f in frases_json})
        pedacos = [[(f["codigo"], f["texto"]) for f in frases_json if f["pedaco"] == n] for n in numeros]
        contexto_inicial = rodar.CONTEXTO_INICIAL.format(sigla=sigla, autor=autor, ementa=ementa)
        prefixos = {"encadeada": lambda n: "", "contexto": lambda n: contexto_inicial}

        linhas = []
        for nome_camada, camadas in CAMADAS.items():
            leitor.camadas = camadas
            media_global = leitura.normalizar(numpy.mean(leitor.vetores(amostra), axis=0))
            soltas = leitura.ler_frases_soltas(leitor, frases)
            juntos, sozinhos = vetores_dos_blocos(leitor, modelos)
            temas = dict(zip(temas_todos, leitor.vetores(temas_todos)))
            prototipos = {t: leitura.normalizar(numpy.mean(leitor.vetores(e), axis=0)) for t, e in por_tema.items()}
            vet_ementas = dict(zip(ementas, leitor.vetores(list(ementas.values()))))
            resumos = {}
            for nome, interpretacao in leitores.items():
                certas = avaliacao.certas_do_resumo(interpretacao.get("resumo", []))
                todo = " ".join(i["frase"] for i in interpretacao.get("resumo", []) if not i["frase"].startswith("<"))
                resumos[nome] = (leitor.vetores([f for f, _ in certas]), certas, leitor.vetores([todo])[0])
            for modo in LEITURAS:
                lida = soltas if modo == "solta" else leitura.ler_encadeada(leitor, pedacos, prefixos[modo])
                surpresas = surpresas_da_leitura(leitor, lida, modo, frases, pedacos)
                for centralizar in (False, True):
                    fixo_c = (
                        soltas.vetor_frase,
                        juntos,
                        sozinhos,
                        temas,
                        prototipos,
                        vet_ementas,
                        pec_id,
                        oficiais,
                        resumos,
                    )
                    linha = {"camada": nome_camada, "leitura": modo, "centralizar": centralizar}
                    linha |= medir(
                        fixo_c, lida, surpresas, media_global if centralizar else None, frases_json, pedacos, leitores
                    )
                    linhas.append(linha)
                    print(f"{nome_camada:10} {modo:9} centralizar={centralizar!s:5} pronto", flush=True)
        duracao = time.monotonic() - inicio

        destino = os.path.join(pasta, "rodadas", f"{datetime.now():%Y-%m-%d_%H%M}_experimentos")
        os.makedirs(destino, exist_ok=True)
        with open(os.path.join(destino, "resultado.json"), "w", encoding="utf-8") as arquivo:
            json.dump(
                {"linhas": linhas, "leituras": leitor.leituras, "duracao_s": round(duracao, 1)},
                arquivo,
                ensure_ascii=False,
                indent=2,
            )
        texto = relatorio(linhas, leitores, duracao, embeddings.nome_do_dispositivo(dispositivo))
        with open(os.path.join(destino, "relatorio.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        print(f"Salvo em {destino}")


if __name__ == "__main__":
    main()
