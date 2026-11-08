"""
Roda uma rodada da analise da PEC com a RoBERTaLexPT original (docs/LEITURA_ENCADEADA.md).

    python scripts/analise_pec/rodar.py --rodada base
    python scripts/analise_pec/rodar.py --rodada encadeada        # so as interpretacoes da Roberta
    python scripts/analise_pec/rodar.py --rodada contexto         # + contexto inicial
    python scripts/analise_pec/rodar.py --rodada planta           # + bloco da planta (leitura previa)
    python scripts/analise_pec/rodar.py --rodada controle --camadas planta --sementes 5

O resultado vai para instance/analise_pec/rodadas/<data>_<rodada>/ (resultado.json e relatorio.md).
Nao treina nada e nao grava nada no banco.
"""

import argparse
import glob
import json
import os
import random
import re
import statistics
import sys
import time
from datetime import datetime

import avaliacao
import leitura

RODADAS = ("base", "encadeada", "contexto", "planta", "controle")
CAMADAS = ("nada", "contexto", "planta")
CONTEXTO_INICIAL = "{sigla}, de {autor}. Ementa: {ementa}"
OUTRAS_PECS = 30
PEC_PARECIDA = ("PEC", 275, 2004)  # mesmo assunto da 319/2004 (estudo, secao "Qual PEC")


def _ler_json(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


# ======================================================
# DADOS
# ======================================================
def carregar_pec(pasta, nome):
    frases = _ler_json(os.path.join(pasta, f"{nome}_frases.json"))["frases"]
    formulario = _ler_json(os.path.join(pasta, f"interpretacao_{nome}.json"))
    leitores = {}
    for caminho in sorted(glob.glob(os.path.join(pasta, f"interpretacao_{nome}_*.json"))):
        leitor = os.path.basename(caminho).removeprefix(f"interpretacao_{nome}_").removesuffix(".json")
        leitores[leitor] = _ler_json(caminho)
    modelos = _ler_json(os.path.join(pasta, "modelos_contexto.json"))
    return frases, formulario["pec"]["id"], leitores, modelos


def carregar_do_banco(pec_id):
    from desperta.ext.db import db
    from desperta.proposicoes.models import Proposicao, ProposicaoAutor, ProposicaoTema, Tema

    pec = db.session.get(Proposicao, pec_id)
    autores = db.session.scalars(db.select(ProposicaoAutor).filter_by(proposicao_id=pec_id).order_by("ordem")).all()
    autor = autores[0].nome + (" e outros" if len(autores) > 1 else "") if autores else "autor não informado"
    oficiais = list(
        db.session.scalars(
            db.select(Tema.nome)
            .join(ProposicaoTema, ProposicaoTema.cod_tema == Tema.cod_tema)
            .filter_by(proposicao_id=pec_id)
        )
    )
    todos_os_temas = list(db.session.scalars(db.select(Tema.nome).order_by(Tema.nome)))
    outras = db.session.execute(
        db.select(Proposicao.id, Proposicao.sigla_tipo, Proposicao.numero, Proposicao.ano, Proposicao.ementa)
        .where(Proposicao.sigla_tipo == "PEC", Proposicao.id != pec_id)
        .order_by(Proposicao.id)
    ).all()
    parecida = [linha for linha in outras if (linha.sigla_tipo, linha.numero, linha.ano) == PEC_PARECIDA]
    resto = [linha for linha in outras if linha not in parecida]
    # Sorteio fixo: as mesmas PECs em todas as rodadas
    escolhidas = parecida + random.Random(pec_id).sample(resto, min(OUTRAS_PECS - len(parecida), len(resto)))
    ementas = {pec.id: pec.ementa} | {linha.id: linha.ementa for linha in escolhidas}
    sigla = f"{pec.sigla_tipo} {pec.numero}/{pec.ano}"
    return (
        sigla,
        autor,
        pec.ementa,
        oficiais,
        todos_os_temas,
        ementas,
        [f"{p.sigla_tipo} {p.numero}/{p.ano}" for p in parecida],
    )


# ======================================================
# PLANTA (leitura previa, decisao 5)
# ======================================================
def blocos_das_frases(leitor, modelos, vetores_soltos):
    """A Roberta le a planta sozinha uma vez; cada frase vai para o bloco de vetor mais parecido."""
    blocos = [(nome, f"{nome}: {texto}") for nome, texto in modelos["planta_padrao"]["blocos"].items()]
    ids, intervalos = leitor.tokenizar_frases(blocos)
    estados = leitor.ler([([], ids[: 2 * leitura.METADE])])[0]
    vetor_bloco = {nome: leitura.media(estados[inicio:fim]) for nome, inicio, fim in intervalos}
    return {
        codigo: max(vetor_bloco, key=lambda nome: leitura.cosseno(vetor_bloco[nome], vetor))
        for codigo, vetor in vetores_soltos.items()
    }


# ======================================================
# TESTES
# ======================================================
def _codigos(lista):
    return [str(item).split(":")[0].strip() for item in lista if not str(item).startswith("<")]


def _lacunas(leitor, leitura_pec, unidade_da_frase, frases, palavras):
    resultados = []
    for palavra in palavras:
        achou = None
        for codigo, texto in frases:
            unidade = unidade_da_frase[codigo]
            busca = re.search(rf"(?<!\w){re.escape(palavra)}(?!\w)", unidade, re.IGNORECASE)
            if busca and re.search(rf"(?<!\w){re.escape(palavra)}(?!\w)", texto, re.IGNORECASE):
                achou = (codigo, unidade, busca)
                break
        if achou is None:
            resultados.append((palavra, None))
            continue
        codigo, unidade, busca = achou
        comeco, fim = busca.span()
        antes, original, depois = unidade[:comeco].rstrip(), busca.group(0), unidade[fim:]
        alvo = leitor.ids(original, espaco_antes=bool(antes))
        if len(alvo) != 1:
            resultados.append((palavra, None))  # palavra de varios tokens: nao da para esconder numa lacuna so
            continue
        ids = leitor.ids(antes) + [leitor.tokenizador.mask_token_id] + leitor.ids(depois)
        posicao = len(leitor.ids(antes))
        palpites = leitor.palpites(leitura_pec.contexto_da_frase[codigo], ids[: leitura.METADE], posicao)
        resultados.append((palavra, alvo[0] in palpites))
    return resultados


def avaliar(leitor, leitura_pec, dados, unidade_da_frase):
    frases, leitores, ementas, pec_id, temas_todos, oficiais, escolhidos_blocos, certos_blocos = dados
    total = len(frases)
    ordem = avaliacao.ordenar(leitura_pec.vetor_pec, leitura_pec.vetor_frase, leitura.cosseno)
    ordem_palavras = avaliacao.centralidade_por_palavras(frases, leitura.PALAVRAS_VAZIAS)
    vetores_tema = dict(zip(temas_todos, leitor.vetores(temas_todos)))
    top3 = avaliacao.ordenar(leitura_pec.vetor_pec, vetores_tema, leitura.cosseno)[:3]
    vetores_ementa = dict(zip(ementas, leitor.vetores(list(ementas.values()))))

    notas = {"blocos": avaliacao.teste_blocos(escolhidos_blocos, certos_blocos), "leitores": {}}
    for nome, interpretacao in leitores.items():
        escolhidas = _codigos(interpretacao.get("frases_importantes", []))
        certas = avaliacao.certas_do_resumo(interpretacao.get("resumo", []))
        vetores_resumo = leitor.vetores([frase for frase, _ in certas]) if certas else []
        achadas = [avaliacao.ordenar(v, leitura_pec.vetor_frase, leitura.cosseno)[0] for v in vetores_resumo]
        achadas_palavras = [
            avaliacao.mais_parecida_por_palavras(frase, frases, leitura.PALAVRAS_VAZIAS) for frase, _ in certas
        ]
        resumo = " ".join(
            item["frase"] for item in interpretacao.get("resumo", []) if not item["frase"].startswith("<")
        )
        ordem_c = avaliacao.ordenar(leitor.vetores([resumo])[0], vetores_ementa, leitura.cosseno) if resumo else None
        palavras = [p for p in interpretacao.get("palavras_chave", []) if not p.startswith("<")]
        notas["leitores"][nome] = {
            "A": avaliacao.teste_a(ordem, escolhidas, total) if escolhidas else None,
            "A_palavras": avaliacao.teste_a(ordem_palavras, escolhidas, total) if escolhidas else None,
            "B": avaliacao.teste_b(achadas, certas, total),
            "B_palavras": avaliacao.teste_b(achadas_palavras, certas, total),
            "C": avaliacao.teste_c(ordem_c, pec_id) if ordem_c else None,
            "D": avaliacao.teste_d(
                top3,
                [t for t in interpretacao.get("temas", []) if not t.startswith("<")],
                [t for t in interpretacao.get("temas_tambem_aceitos", []) if not t.startswith("<")],
                oficiais,
            ),
            "E_pesos": avaliacao.teste_e_pesos(leitura_pec.pesos_palavras, palavras),
            "E_lacunas": avaliacao.teste_e_lacunas(_lacunas(leitor, leitura_pec, unidade_da_frase, frases, palavras)),
        }
    return notas


# ======================================================
# RELATORIO
# ======================================================
def _linha(nome, nota, chave, campo="acertos", de="de"):
    teste = nota.get(chave)
    if not teste:
        return "-"
    return f"{teste[campo]} de {teste[de]}"


def relatorio(resultado):
    linhas = [
        f"# Rodada {resultado['rodada']} — {resultado['pec']}",
        "",
        f"{resultado['quando']} · {resultado['dispositivo']} · "
        f"{resultado['leituras']} leituras · {resultado['duracao_s']} s",
        "",
        f"Configuração: {json.dumps(resultado['configuracao'], ensure_ascii=False)}",
        "",
        "Comparar posições, não o valor da similaridade. Acaso = o que se acertaria sorteando.",
        "",
    ]
    notas = resultado["notas"] if "notas" in resultado else resultado["notas_por_semente"][0]
    blocos = notas["blocos"]
    linhas += [
        "## Blocos da planta (leitura prévia)",
        "",
        f"{blocos['acertos']} de {blocos['de']} frases no bloco certo; responder sempre o maior bloco daria "
        f"{blocos['sempre_o_maior_bloco']} de {blocos['de']}. Erradas: "
        + (", ".join(f"{c} → {b}" for c, b in blocos["erradas"].items()) or "nenhuma"),
        "",
        "## Testes por leitor",
        "",
        "| Teste | " + " | ".join(notas["leitores"]) + " |",
        "|---|" + "---|" * len(notas["leitores"]),
    ]
    leitores = notas["leitores"]

    def linha(rotulo, funcao):
        linhas.append(f"| {rotulo} | " + " | ".join(funcao(n) for n in leitores.values()) + " |")

    linha(
        "A. 5 frases centrais (Roberta)",
        lambda n: _linha("", n, "A") + (f" (acaso {n['A']['acaso']})" if n["A"] else ""),
    )
    linha("A. adversário: palavras repetidas", lambda n: _linha("", n, "A_palavras"))
    linha("B. resumo → frase certa (Roberta)", lambda n: _linha("", n, "B") + f" (acaso {n['B']['acaso']})")
    linha("B. adversário: palavras em comum", lambda n: _linha("", n, "B_palavras"))
    linha("C. posição da PEC certa", lambda n: f"{n['C']['posicao']}º de {n['C']['de']}" if n["C"] else "-")
    linha("D. temas, nota exata", lambda n: f"{n['D']['exata']} de 3")
    linha("D. temas, nota ampla", lambda n: f"{n['D']['ampla']} de 3")
    linha("E. palavras de maior peso em comum", lambda n: f"{len(n['E_pesos']['em_comum'])} de {n['E_pesos']['de']}")
    linha("E. lacunas acertadas (5 palpites)", lambda n: f"{n['E_lacunas']['acertos']} de {n['E_lacunas']['testadas']}")
    primeiro = next(iter(leitores.values()))
    linhas += [
        "",
        f"- **Top 5 da Roberta (A):** {', '.join(primeiro['A']['top5']) if primeiro['A'] else '-'}",
        f"- **Temas da Roberta (D):** {', '.join(primeiro['D']['top3'])}; "
        f"oficiais em comum: {primeiro['D']['oficiais']}",
        f"- **Palavras de maior peso (E):** {', '.join(primeiro['E_pesos']['top10'])}",
    ]
    for nome, n in leitores.items():
        linhas.append(
            f"- **{nome}:** B achou {', '.join(n['B']['achadas']) or '-'}; lacunas acertadas: "
            f"{', '.join(n['E_lacunas']['acertadas']) or 'nenhuma'}; não testáveis (vários tokens): "
            f"{', '.join(n['E_lacunas']['nao_testadas']) or 'nenhuma'}"
        )
    if resultado.get("resumo_das_sementes"):
        linhas += ["", "## Controle: média (mínimo a máximo) nas sementes", ""]
        for nome, valores in resultado["resumo_das_sementes"].items():
            linhas.append(f"- **{nome}:** " + "; ".join(f"{teste} {v}" for teste, v in valores.items()))
    if resultado.get("por_pedaco"):
        linhas += [
            "",
            "## Pedaço a pedaço",
            "",
            "| Pedaço | Tokens (contexto + pedaço) | Frase escolhida | Palavras | Saiu da memória |",
            "|---|---|---|---|---|",
        ]
        for p in resultado["por_pedaco"]:
            linhas.append(
                f"| {p['pedaco']} | {p['tokens_contexto']} + {p['tokens_pedaco']} | {p['frase_escolhida']} | "
                f"{', '.join(p['palavras'])} | {', '.join(p['saiu_da_memoria']) or '-'} |"
            )
        linhas += ["", "### Contexto que entrou em cada pedaço", ""]
        for p in resultado["por_pedaco"]:
            linhas.append(f"{p['pedaco']}. {p['contexto'] or '(vazio)'}")
            linhas.append("")
    return "\n".join(linhas) + "\n"


def _resumo_das_sementes(lista):
    def numeros(n):
        return {
            "A": n["A"]["acertos"] if n["A"] else None,
            "B": n["B"]["acertos"],
            "D exata": n["D"]["exata"],
            "D ampla": n["D"]["ampla"],
            "E pesos": len(n["E_pesos"]["em_comum"]),
            "E lacunas": n["E_lacunas"]["acertos"],
        }

    resumo = {}
    for nome in lista[0]["leitores"]:
        por_teste = {}
        for teste in numeros(lista[0]["leitores"][nome]):
            valores = [numeros(n["leitores"][nome])[teste] for n in lista]
            if None in valores:
                continue
            por_teste[teste] = f"{statistics.mean(valores):.1f} ({min(valores)} a {max(valores)})"
        resumo[nome] = por_teste
    return resumo


# ======================================================
# EXECUCAO
# ======================================================
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rodada", choices=RODADAS, required=True)
    parser.add_argument(
        "--camadas", choices=CAMADAS, default="planta", help="Para o controle: o que vai antes da memória."
    )
    parser.add_argument("--sementes", type=int, default=5, help="Para o controle: quantos sorteios.")
    parser.add_argument("--inversa", action="store_true", help="Lê os pedaços de trás para frente.")
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
        frases_json, pec_id, leitores, modelos = carregar_pec(pasta, argumentos.pec)
        if not leitores:
            sys.exit(f"Nenhuma interpretação interpretacao_{argumentos.pec}_<nome>.json em {pasta}.")
        sigla, autor, ementa, oficiais, temas_todos, ementas, parecidas = carregar_do_banco(pec_id)

        inicio = time.monotonic()
        leitor = leitura.Leitor(pasta_modelo, dispositivo)
        frases = [(f["codigo"], f["texto"]) for f in frases_json]
        certos_blocos = {f["codigo"]: f["bloco_certo"] for f in frases_json}
        numeros_pedaco = sorted({f["pedaco"] for f in frases_json})
        pedacos = [[(f["codigo"], f["texto"]) for f in frases_json if f["pedaco"] == n] for n in numeros_pedaco]
        if argumentos.inversa:
            pedacos = pedacos[::-1]
        texto_do_pedaco = {codigo: " ".join(t for _, t in p) for p in pedacos for codigo, _ in p}

        soltas = leitura.ler_frases_soltas(leitor, frases)
        escolhidos_blocos = blocos_das_frases(leitor, modelos, soltas.vetor_frase)
        contexto_inicial = CONTEXTO_INICIAL.format(sigla=sigla, autor=autor, ementa=ementa)

        def prefixo(camadas):
            def montar(numero):
                if camadas == "nada":
                    return ""
                if camadas == "contexto":
                    return contexto_inicial
                partes = []
                for codigo, _ in pedacos[numero]:
                    if escolhidos_blocos[codigo] not in partes:
                        partes.append(escolhidos_blocos[codigo])
                return f"Partes da planta: {'; '.join(partes)}. {contexto_inicial}"

            return montar

        dados = (frases, leitores, ementas, pec_id, temas_todos, oficiais, escolhidos_blocos, certos_blocos)
        resultado = {
            "rodada": argumentos.rodada + ("_inversa" if argumentos.inversa else ""),
            "pec": sigla,
            "quando": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "dispositivo": embeddings.nome_do_dispositivo(dispositivo),
            "configuracao": {
                "metade": leitura.METADE,
                "contexto_inicial": contexto_inicial if argumentos.rodada in ("contexto", "planta") else None,
                "camadas": argumentos.camadas if argumentos.rodada == "controle" else None,
                "inversa": argumentos.inversa,
                "outras_pecs_no_teste_c": len(ementas) - 1,
                "pec_parecida_no_teste_c": parecidas,
                "temas_oficiais": oficiais,
                "leitores": list(leitores),
            },
        }
        if argumentos.rodada == "base":
            resultado["notas"] = avaliar(leitor, soltas, dados, {c: t for c, t in frases})
        elif argumentos.rodada == "controle":
            lista = []
            for semente in range(argumentos.sementes):
                lida = leitura.ler_encadeada(leitor, pedacos, prefixo(argumentos.camadas), random.Random(semente))
                lista.append(avaliar(leitor, lida, dados, texto_do_pedaco))
            resultado["notas_por_semente"] = lista
            resultado["resumo_das_sementes"] = _resumo_das_sementes(lista)
            resultado["por_pedaco"] = lida.por_pedaco
        else:
            camadas = {"encadeada": "nada", "contexto": "contexto", "planta": "planta"}[argumentos.rodada]
            lida = leitura.ler_encadeada(leitor, pedacos, prefixo(camadas))
            resultado["notas"] = avaliar(leitor, lida, dados, texto_do_pedaco)
            resultado["por_pedaco"] = lida.por_pedaco
        resultado["leituras"] = leitor.leituras
        resultado["duracao_s"] = round(time.monotonic() - inicio, 1)

        destino = os.path.join(pasta, "rodadas", f"{datetime.now():%Y-%m-%d_%H%M}_{resultado['rodada']}")
        os.makedirs(destino, exist_ok=True)
        with open(os.path.join(destino, "resultado.json"), "w", encoding="utf-8") as arquivo:
            json.dump(resultado, arquivo, ensure_ascii=False, indent=2, default=str)
        texto = relatorio(resultado)
        with open(os.path.join(destino, "relatorio.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)
        print(texto)
        print(f"Salvo em {destino}")


if __name__ == "__main__":
    main()
