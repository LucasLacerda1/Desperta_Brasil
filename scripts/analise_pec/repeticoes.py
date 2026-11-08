"""
As rodadas da analise da PEC repetidas N vezes com o dropout ligado, para saber se as diferencas entre
elas sao reais ou ruido. Sem dropout a RoBERTaLexPT e deterministica; com ele, cada repeticao le a PEC
de um jeito um pouco diferente. Nao treina nada e nao grava no banco.

    python scripts/analise_pec/repeticoes.py --vezes 1000

- Uma leitura serve a duas rodadas: o whitening e aplicado depois da leitura (com e sem).
- So a leitura da PEC varia; temas, ementas e resumo sao lidos uma vez, sem dropout.
- O teste C (resumo contra ementas) nao usa a leitura da PEC: e constante e sai uma vez.
- Votacao: um conjunto de leituras com dropout e lido uma vez, e cada repeticao e a media de 1.000
  leituras sorteadas dele (bootstrap).

Cada repeticao e gravada assim que termina em instance/analise_pec/rodadas/<data>_repeticoes/repeticoes.jsonl;
o resumo (media e intervalo de 95%) vai para resumo.json. Com --continuar, retoma de onde parou.
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

import numpy

import avaliacao
import leitura
import rodar

LEITURAS_DA_VOTACAO = 1000
CONJUNTO_DA_VOTACAO = 5000
RODADAS = ("base", "encadeada", "contexto", "planta", "controle", "rag", "votacao")


def vetores_das_frases(leitor, frases):
    """Leitura de cada frase sozinha, so os vetores (sem o peso das palavras, que o teste E usa)."""
    estados = leitor.ler([([], leitor.ids(texto)[: 2 * leitura.METADE]) for _, texto in frases])
    return {codigo: leitura.media(e) for (codigo, _), e in zip(frases, estados)}


def medir(vetor_frase, ajuste, fixos):
    """Notas de uma leitura: AUC das 5 frases por leitor, resumo -> frase e posicao do tema oficial."""
    vetores = {k: ajuste(v) for k, v in vetor_frase.items()} if ajuste else vetor_frase
    pec = leitura.media(list(vetores.values()))
    sufixo = "whitening" if ajuste else "normal"
    temas = fixos["temas"][sufixo]
    ordem_temas = sorted(temas, key=lambda t: -leitura.cosseno(temas[t], pec))
    notas = {"tema_oficial": min(ordem_temas.index(t) + 1 for t in fixos["oficiais"] if t in ordem_temas)}
    contra_pec = {k: leitura.cosseno(v, pec) for k, v in vetores.items()}
    for nome, (escolhidas, resumo) in fixos["leitores"].items():
        notas[f"A_{nome}"] = avaliacao.auc(contra_pec, escolhidas)
        acertos = 0
        for vetor, conjunto in resumo[sufixo]:
            achada = max(vetores, key=lambda k: leitura.cosseno(vetores[k], vetor))
            acertos += achada in conjunto
        notas[f"B_{nome}"] = acertos
    return notas


def resumir(valores):
    v = numpy.array([x for x in valores if x is not None], dtype=float)
    return {
        "media": float(v.mean()),
        "ic95": [float(numpy.percentile(v, 2.5)), float(numpy.percentile(v, 97.5))],
        "minimo": float(v.min()),
        "maximo": float(v.max()),
        "n": int(v.size),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vezes", type=int, default=1000)
    parser.add_argument("--rodadas", nargs="*", default=list(RODADAS), choices=RODADAS)
    parser.add_argument("--continuar", help="Pasta de uma execucao anterior para retomar.")
    parser.add_argument("--pec", default="PEC_319_2004")
    argumentos = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from desperta import create_app
    from desperta.ia import embeddings

    app = create_app()
    with app.app_context():
        config = app.config
        pasta_modelo = embeddings.caminho_no_projeto(app, config["ROBERTA_DIR"])
        if embeddings.arquivos_faltando(pasta_modelo):
            sys.exit(f"RoBERTaLexPT não encontrada em {pasta_modelo}. O pendrive está conectado?")
        embeddings.preparar_ambiente(app)
        dispositivo = embeddings.escolher_dispositivo(config["IA_DISPOSITIVO"])
        pasta = os.path.join(app.instance_path, "analise_pec")
        frases_json, pec_id, leitores, modelos = rodar.carregar_pec(pasta, argumentos.pec)
        sigla, autor, ementa, oficiais, temas_todos, ementas, _ = rodar.carregar_do_banco(pec_id)
        leitura.TAMANHO_LOTE = 64
        leitor = leitura.Leitor(pasta_modelo, dispositivo)
        branco = rodar.whitening_dos_trechos(config["EMBEDDING_MODEL"])

        frases = [(f["codigo"], f["texto"]) for f in frases_json]
        certos = {f["codigo"]: f["bloco_certo"] for f in frases_json}
        numeros = sorted({f["pedaco"] for f in frases_json})
        pedacos = [[(f["codigo"], f["texto"]) for f in frases_json if f["pedaco"] == n] for n in numeros]
        contexto_inicial = rodar.CONTEXTO_INICIAL.format(sigla=sigla, autor=autor, ementa=ementa)

        # Fixos: lidos uma vez, sem dropout
        leitor.modo_dropout(False)
        temas_normais = dict(zip(temas_todos, leitor.vetores(temas_todos)))
        fixos = {
            "oficiais": oficiais,
            "temas": {"normal": temas_normais, "whitening": {t: branco(v) for t, v in temas_normais.items()}},
            "leitores": {},
        }
        for nome, interpretacao in leitores.items():
            certas = avaliacao.certas_do_resumo(interpretacao.get("resumo", []))
            normais = leitor.vetores([f for f, _ in certas])
            fixos["leitores"][nome] = (
                set(rodar._codigos(interpretacao.get("frases_importantes", []))),
                {
                    "normal": [(v, c) for v, (_, c) in zip(normais, certas)],
                    "whitening": [(branco(v), c) for v, (_, c) in zip(normais, certas)],
                },
            )
        constantes = {}
        for sufixo, ajuste in (("normal", None), ("whitening", branco)):
            leitor.transformar = ajuste
            vet_ementas = dict(zip(ementas, leitor.vetores(list(ementas.values()))))
            for nome, interpretacao in leitores.items():
                todo = " ".join(i["frase"] for i in interpretacao.get("resumo", []) if not i["frase"].startswith("<"))
                vetor = leitor.vetores([todo])[0]
                ordem = sorted(vet_ementas, key=lambda k: -leitura.cosseno(vet_ementas[k], vetor))
                constantes[f"C_{nome}_{sufixo}"] = ordem.index(pec_id) + 1
        leitor.transformar = None
        contextos_rag, _ = rodar.contextos_do_rag(app, pasta_modelo, dispositivo, pedacos, pec_id, 8)
        vetor_bloco = {}
        blocos = [(n, f"{n}: {t}") for n, t in modelos["planta_padrao"]["blocos"].items()]
        ids, intervalos = leitor.tokenizar_frases(blocos)
        estados = leitor.ler([([], ids[: 2 * leitura.METADE])])[0]
        vetor_bloco = {n: leitura.media(estados[a:b]) for n, a, b in intervalos}

        if argumentos.continuar:
            destino = argumentos.continuar
        else:
            destino = os.path.join(pasta, "rodadas", f"{datetime.now():%Y-%m-%d_%H%M}_repeticoes")
        os.makedirs(destino, exist_ok=True)
        arquivo = os.path.join(destino, "repeticoes.jsonl")
        feitas = {}
        if os.path.exists(arquivo):
            for linha in open(arquivo, encoding="utf-8"):
                item = json.loads(linha)
                feitas[(item["rodada"], item["vez"])] = item
        with open(os.path.join(destino, "constantes.json"), "w", encoding="utf-8") as saida:
            json.dump(constantes, saida, ensure_ascii=False, indent=2)

        def blocos_da_leitura(soltas):
            escolhidos = {
                c: max(vetor_bloco, key=lambda n: leitura.cosseno(vetor_bloco[n], v)) for c, v in soltas.items()
            }
            acertos = sum(avaliacao.bloco_bate(escolhidos[c], certos[c]) for c in certos)
            return escolhidos, acertos

        def prefixo(nome, escolhidos):
            def montar(numero):
                if nome in ("encadeada", "controle"):
                    return ""
                if nome == "contexto":
                    return contexto_inicial
                if nome == "rag":
                    return contextos_rag[numero]
                partes = []
                for codigo, _ in pedacos[numero]:
                    if escolhidos[codigo] not in partes:
                        partes.append(escolhidos[codigo])
                return f"Partes da planta: {'; '.join(partes)}. {contexto_inicial}"

            return montar

        leitor.modo_dropout(True)
        inicio = time.monotonic()
        with open(arquivo, "a", encoding="utf-8") as saida:
            conjunto = None
            for nome in argumentos.rodadas:
                for vez in range(argumentos.vezes):
                    if (nome, vez) in feitas:
                        continue
                    comeco = time.monotonic()
                    if nome == "votacao":
                        if conjunto is None:
                            ids_frases = [leitor.ids(t)[: 2 * leitura.METADE] for _, t in frases]
                            conjunto = numpy.zeros((CONJUNTO_DA_VOTACAO, len(frases), 768), dtype=numpy.float32)
                            for r in range(0, CONJUNTO_DA_VOTACAO, 50):
                                estados = leitor.ler([([], i) for _ in range(50) for i in ids_frases])
                                v = numpy.array([leitura.media(e) for e in estados], dtype=numpy.float32)
                                fim = r + 50
                                conjunto[r:fim] = v.reshape(50, len(frases), -1)
                        sorteio = numpy.random.default_rng(vez).integers(0, CONJUNTO_DA_VOTACAO, LEITURAS_DA_VOTACAO)
                        media = conjunto[sorteio].astype(numpy.float64).mean(axis=0)
                        vetor_frase = {c: leitura.normalizar(media[i]) for i, (c, _) in enumerate(frases)}
                        _, acertos_blocos = blocos_da_leitura(vetor_frase)
                    else:
                        soltas = vetores_das_frases(leitor, frases)
                        escolhidos, acertos_blocos = blocos_da_leitura(soltas)
                        if nome == "base":
                            vetor_frase = soltas
                        else:
                            sorteio = random.Random(vez) if nome == "controle" else None
                            lida = leitura.ler_encadeada(leitor, pedacos, prefixo(nome, escolhidos), sorteio)
                            vetor_frase = lida.vetor_frase
                    item = {
                        "rodada": nome,
                        "vez": vez,
                        "blocos": acertos_blocos,
                        "segundos": round(time.monotonic() - comeco, 2),
                    }
                    for sufixo, ajuste in (("normal", None), ("whitening", branco)):
                        for chave, valor in medir(vetor_frase, ajuste, fixos).items():
                            item[f"{chave}_{sufixo}"] = valor
                    saida.write(json.dumps(item, ensure_ascii=False) + "\n")
                    saida.flush()
                    feitas[(nome, vez)] = item
                    if vez % 50 == 0:
                        print(
                            f"{datetime.now():%H:%M} {nome} {vez + 1}/{argumentos.vezes} ({item['segundos']} s)",
                            flush=True,
                        )
        leitor.modo_dropout(False)

        resumo = {"vezes": argumentos.vezes, "constantes": constantes, "rodadas": {}}
        for nome in argumentos.rodadas:
            itens = [i for (r, _), i in feitas.items() if r == nome]
            if not itens:
                continue
            chaves = [k for k in itens[0] if k not in ("rodada", "vez", "segundos")]
            resumo["rodadas"][nome] = {k: resumir([i[k] for i in itens]) for k in chaves}
        resumo["duracao_s"] = round(time.monotonic() - inicio, 1)
        with open(os.path.join(destino, "resumo.json"), "w", encoding="utf-8") as saida:
            json.dump(resumo, saida, ensure_ascii=False, indent=2)
        print(f"Salvo em {destino}")


if __name__ == "__main__":
    main()
