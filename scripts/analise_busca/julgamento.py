"""
Gabarito da busca por julgamento dos resultados (pooling), no lugar das "esperadas" (decisao 16.2).

As "esperadas" das 20 consultas foram escritas quando o banco tinha 3.500 proposicoes; hoje sao
mais de 11 mil, e muitas respostas certas ficavam de fora. Aqui, os 8 primeiros de cada modo
de busca sao juntados por consulta, sem dizer de qual modo vieram, e cada pessoa marca a nota:
    2 = responde a consulta; 1 = relacionado, mas nao e o que se pediu; 0 = fora do assunto.

Uso:
    python scripts/analise_busca/julgamento.py montar           # formulario em branco
    python scripts/analise_busca/julgamento.py medir            # nota de cada modo, com todos os julgamentos
    python scripts/analise_busca/julgamento.py montar --modos hibrida palavras_raiz  # completa o formulario

Arquivos em instance/analise_busca/: julgamento.json (formulario) e julgamento_<nome>.json (de cada pessoa).
"""

import argparse
import glob
import json
import os
import sys

PASTA = os.path.join("instance", "analise_busca")
FORMULARIO = os.path.join(PASTA, "julgamento.json")
CONSULTAS = os.path.join("tests", "dados", "consultas_busca.json")
K = 8


def chave_do_trecho(trecho):
    """Tramitacao conta como a propria proposicao; votacao, evento e pauta valem por si."""
    if trecho.tipo == "proposicao":
        return f"proposicao/{trecho.ref_id}"
    if trecho.tipo == "tramitacao":
        return f"proposicao/{trecho.ref_id.split('/')[0]}"
    return f"{trecho.tipo}/{trecho.ref_id}"


def _descrever(chave, trecho):
    from desperta.ext.db import db
    from desperta.proposicoes.models import Proposicao

    tipo, ref = chave.split("/", 1)
    if tipo == "proposicao":
        p = db.session.get(Proposicao, int(ref))
        if p is not None:
            return f"{p.sigla_tipo} {p.numero}/{p.ano}", p.ementa
    return chave, trecho.texto[:400]


def _resultados(modelo, consulta, modos):
    from desperta.ia import services

    por_modo = {}
    for modo in modos:
        chaves = []
        for achado in services.buscar(modelo, consulta, K, modo=modo):
            chave = chave_do_trecho(achado.trecho)
            if chave not in chaves:
                chaves.append(chave)
            por_modo.setdefault("_trechos", {})[chave] = achado.trecho
        por_modo[modo] = chaves
    return por_modo


def montar(modelo, modos):
    consultas = json.load(open(CONSULTAS, encoding="utf-8"))["consultas"]
    antigo = json.load(open(FORMULARIO, encoding="utf-8")) if os.path.exists(FORMULARIO) else None
    itens_antigos = {c["consulta"]: {i["chave"]: i for i in c["itens"]} for c in (antigo or {}).get("consultas", [])}
    saida = []
    novos = 0
    for item in consultas:
        resultado = _resultados(modelo, item["consulta"], modos)
        trechos = resultado.pop("_trechos", {})
        itens = dict(itens_antigos.get(item["consulta"], {}))
        for chave, trecho in trechos.items():
            if chave not in itens:
                titulo, texto = _descrever(chave, trecho)
                itens[chave] = {"chave": chave, "titulo": titulo, "texto": texto, "nota": None}
                novos += 1
        # Ordem pela chave, para ninguem saber de qual modo cada item veio
        saida.append({"consulta": item["consulta"], "itens": [itens[c] for c in sorted(itens)]})
    os.makedirs(PASTA, exist_ok=True)
    with open(FORMULARIO, "w", encoding="utf-8") as arq:
        json.dump(
            {
                "_como_preencher": [
                    "Copie este arquivo como julgamento_<seu nome>.json e preencha 'nota' em cada item, sem ver as notas dos outros.",
                    "2 = responde a consulta; 1 = relacionado, mas nao e o que se pediu; 0 = fora do assunto.",
                    "Pense em quem digitou a consulta no portal: este resultado ajuda essa pessoa?",
                    "Os itens estao em ordem de id, e nao dizem de qual modo de busca vieram.",
                ],
                "consultas": saida,
            },
            arq,
            ensure_ascii=False,
            indent=2,
        )
    total = sum(len(c["itens"]) for c in saida)
    print(f"{FORMULARIO}: {len(saida)} consultas, {total} itens ({novos} novos).")


def _julgamentos():
    notas = {}
    for caminho in sorted(glob.glob(os.path.join(PASTA, "julgamento_*.json"))):
        nome = os.path.basename(caminho).removeprefix("julgamento_").removesuffix(".json")
        dados = json.load(open(caminho, encoding="utf-8"))
        notas[nome] = {
            (c["consulta"], i["chave"]): i["nota"] for c in dados["consultas"] for i in c["itens"] if i["nota"] is not None
        }
    return notas


def medir(modelo, modos):
    consultas = json.load(open(CONSULTAS, encoding="utf-8"))["consultas"]
    julgamentos = _julgamentos()
    if not julgamentos:
        sys.exit("Nenhum julgamento_<nome>.json em " + PASTA)
    print(f"Julgamentos: {', '.join(julgamentos)}; nota 2 = responde, 1 = relacionado, 0 = fora.")
    for modo in modos:
        linha = [modo.ljust(16)]
        for nome, notas in julgamentos.items():
            respondem = relacionados = fora = sem_nota = 0
            for item in consultas:
                for chave in _resultados(modelo, item["consulta"], [modo])[modo]:
                    nota = notas.get((item["consulta"], chave))
                    if nota is None:
                        sem_nota += 1
                    elif nota == 2:
                        respondem += 1
                    elif nota == 1:
                        relacionados += 1
                    else:
                        fora += 1
            julgados = respondem + relacionados + fora
            linha.append(
                f"{nome}: responde {respondem}, relacionado {relacionados}, fora {fora}"
                + (f", sem nota {sem_nota}" if sem_nota else "")
                + (f" (util {round(100 * (respondem + relacionados) / julgados)}%)" if julgados else "")
            )
        print(" | ".join(linha))


def main():
    sys.path.insert(0, os.getcwd())
    from app import app
    from desperta.ia import services

    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=["montar", "medir"])
    parser.add_argument("--modos", nargs="+", default=list(services.MODOS_BUSCA))
    argumentos = parser.parse_args()
    with app.app_context():
        modelo = services.carregar_modelo()
        if argumentos.acao == "montar":
            montar(modelo, argumentos.modos)
        else:
            medir(modelo, argumentos.modos)


if __name__ == "__main__":
    main()
