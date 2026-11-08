"""
Tema pelo prototipo, em escala: cada proposicao com tema oficial e avaliada contra os prototipos dos
temas montados sem ela (deixar uma de fora), com a RoBERTaLexPT original (como o portal gera os vetores),
com ajustes sem treino (centralizacao e whitening) e contra adversarios (acaso, temas mais comuns e TF-IDF).

    python scripts/temas_prototipo/avaliar.py

Nao treina nada e nao grava no banco. Resultado em instance/analise_temas/<data>/ (relatorio.md e resultado.json),
com as sugestoes de tema para as proposicoes acompanhadas que a Camara ainda nao classificou.
"""

import json
import os
import sys
import time
from datetime import datetime

import numpy

import prototipos

PALAVRAS_VAZIAS = set(
    """a o as os um uma uns umas de da do das dos e em no na nos nas que por para com sem se ao aos ou como mais
    seu sua seus suas pelo pela pelos pelas este esta esse essa nº art arts lei dispoe sobre altera providencias
    outras institui dispõe dá dá redação nova acrescenta""".split()
)
SUGESTOES_NO_RELATORIO = 15
# Tema com menos proposicoes que isso no banco nao entra nas formas "com minimo" (prototipo de poucas ementas e ruido)
MINIMO_POR_TEMA = 20


def carregar(app):
    from desperta.ext.db import db
    from desperta.proposicoes.models import Proposicao, ProposicaoTema, Tema

    temas = list(db.session.scalars(db.select(Tema.nome).order_by(Tema.cod_tema)))
    indice = {nome: i for i, nome in enumerate(temas)}
    linhas = db.session.execute(
        db.select(Proposicao.id, Proposicao.sigla_tipo, Proposicao.numero, Proposicao.ano, Proposicao.ementa, Tema.nome)
        .join(ProposicaoTema, ProposicaoTema.proposicao_id == Proposicao.id)
        .join(Tema, Tema.cod_tema == ProposicaoTema.cod_tema)
        .order_by(Proposicao.id)
    ).all()
    proposicoes = {}
    for linha in linhas:
        item = proposicoes.setdefault(linha.id, {"id": linha.id, "tipo": linha.sigla_tipo, "ementa": linha.ementa})
        item["sigla"] = f"{linha.sigla_tipo} {linha.numero}/{linha.ano}"
        item.setdefault("temas", []).append(linha.nome)
    com_tema = list(proposicoes.values())
    tem_tema = db.select(ProposicaoTema.proposicao_id)
    sem_tema = [
        {"id": p.id, "tipo": p.sigla_tipo, "ementa": p.ementa, "sigla": f"{p.sigla_tipo} {p.numero}/{p.ano}"}
        for p in db.session.execute(
            db.select(Proposicao.id, Proposicao.sigla_tipo, Proposicao.numero, Proposicao.ano, Proposicao.ementa)
            .where(
                Proposicao.sigla_tipo.in_(app.config["TIPOS_ACOMPANHADOS"]),
                Proposicao.filhos_sincronizados_em.is_not(None),
                Proposicao.id.not_in(tem_tema),
            )
            .order_by(Proposicao.data_apresentacao.desc())
        ).all()
    ]
    rotulos = numpy.zeros((len(com_tema) + len(sem_tema), len(temas)))
    for i, item in enumerate(com_tema):
        for nome in item["temas"]:
            rotulos[i, indice[nome]] = 1
    return temas, com_tema, sem_tema, rotulos


def _pct(valor):
    return f"{100 * valor:.1f}%"


def resumo(medida, linhas):
    return {
        "top1": float(medida["top1"][linhas].mean()),
        "top3": float(medida["top3"][linhas].mean()),
        "posicao_media": float(medida["posicao"][linhas].mean()),
        "posicao_mediana": float(numpy.median(medida["posicao"][linhas])),
    }


def main():
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, raiz)
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
        temas, com_tema, sem_tema, rotulos = carregar(app)
        todas = com_tema + sem_tema
        n = len(com_tema)
        avaliadas = numpy.arange(n)
        rotulos_avaliados = rotulos[:n]

        inicio = time.monotonic()
        modelo = embeddings.ModeloEmbedding(config["EMBEDDING_MODEL"], pasta=pasta_modelo, dispositivo=dispositivo)
        vetores = numpy.array(
            [numpy.frombuffer(b, dtype=numpy.float32) for b in modelo.embutir([p["ementa"] for p in todas])],
            dtype=numpy.float64,
        )
        tempo_vetores = time.monotonic() - inicio

        formas = {
            "Roberta original": vetores,
            "Roberta centralizada": prototipos.centralizar(vetores),
            "Roberta com whitening": prototipos.whitening(vetores),
            "Roberta com whitening (256 dimensões)": prototipos.whitening(vetores, dimensoes=256),
        }
        notas = {nome: prototipos.notas_densas(v, rotulos) for nome, v in formas.items()}
        documentos, tamanho = prototipos.tfidf([p["ementa"] for p in todas], PALAVRAS_VAZIAS)
        notas["Só palavras (TF-IDF)"] = prototipos.notas_esparsas(documentos, rotulos, tamanho)
        minimo = lambda x: prototipos.com_minimo(x, rotulos, MINIMO_POR_TEMA)  # noqa: E731
        notas[f"Whitening, temas com {MINIMO_POR_TEMA}+ exemplos"] = minimo(notas["Roberta com whitening"])
        notas[f"Palavras, temas com {MINIMO_POR_TEMA}+ exemplos"] = minimo(notas["Só palavras (TF-IDF)"])
        notas[f"Whitening + palavras, temas com {MINIMO_POR_TEMA}+ exemplos"] = prototipos.fundir(
            minimo(notas["Roberta com whitening"]), minimo(notas["Só palavras (TF-IDF)"])
        )

        medidas = {nome: prototipos.medir(x[:n], rotulos_avaliados) for nome, x in notas.items()}
        resultados = {nome: resumo(m, avaliadas) for nome, m in medidas.items()}
        acaso1, acaso3 = prototipos.acaso(rotulos_avaliados)
        maioria1, maioria3 = prototipos.maioria(rotulos_avaliados)
        melhor = max(resultados, key=lambda nome: (resultados[nome]["top3"], resultados[nome]["top1"]))
        duracao = time.monotonic() - inicio

        tipos = sorted({p["tipo"] for p in com_tema}, key=lambda t: -sum(p["tipo"] == t for p in com_tema))
        por_tipo = {}
        for tipo in tipos:
            linhas = numpy.array([i for i, p in enumerate(com_tema) if p["tipo"] == tipo])
            por_tipo[tipo] = {"quantas": len(linhas)} | {nome: resumo(m, linhas) for nome, m in medidas.items()}

        ordem_melhor = numpy.argsort(-notas[melhor], axis=1, kind="stable")
        por_tema = []
        for t, nome in enumerate(temas):
            linhas = numpy.flatnonzero(rotulos_avaliados[:, t])
            if len(linhas) == 0:
                continue
            no_top3 = (ordem_melhor[linhas, :3] == t).any(axis=1)
            no_top1 = ordem_melhor[linhas, 0] == t
            por_tema.append((nome, len(linhas), float(no_top1.mean()), float(no_top3.mean())))
        por_tema.sort(key=lambda item: -item[3])

        sugestoes = []
        for j, p in enumerate(sem_tema):
            linha = ordem_melhor[n + j, :3]
            sugestoes.append(
                {"sigla": p["sigla"], "id": p["id"], "ementa": p["ementa"], "temas": [temas[t] for t in linha]}
            )

        destino = os.path.join(app.instance_path, "analise_temas", f"{datetime.now():%Y-%m-%d_%H%M}")
        os.makedirs(destino, exist_ok=True)
        dados = {
            "quando": datetime.now().isoformat(timespec="minutes"),
            "dispositivo": embeddings.nome_do_dispositivo(dispositivo),
            "proposicoes_avaliadas": n,
            "temas": len(temas),
            "tempo_vetores_s": round(tempo_vetores, 1),
            "duracao_s": round(duracao, 1),
            "acaso": {"top1": acaso1, "top3": acaso3},
            "temas_mais_comuns": {"top1": maioria1, "top3": maioria3},
            "resultados": resultados,
            "melhor": melhor,
            "por_tipo": por_tipo,
            "por_tema": por_tema,
            "sugestoes": sugestoes,
        }
        with open(os.path.join(destino, "resultado.json"), "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)

        texto = [
            "# Tema pelo protótipo, em escala",
            "",
            f"{datetime.now():%d/%m/%Y %H:%M} · {dados['dispositivo']} · {n} proposições com tema oficial · "
            f"{len(temas)} temas · vetores em {tempo_vetores:.0f} s, tudo em {duracao:.0f} s",
            "",
            "Cada proposição é comparada com o protótipo de cada tema (a média das ementas do tema) "
            "montado **sem ela**. "
            "Acerto = o tema que vem em 1º (ou um dos 3 primeiros) é um dos temas oficiais dela. Só a ementa é lida.",
            "",
            "| Forma | Acerto no 1º lugar | Entre os 3 primeiros | Posição média do tema certo |",
            "|---|---|---|---|",
            f"| Acaso | {_pct(acaso1)} | {_pct(acaso3)} | |",
            f"| Sempre os temas mais comuns | {_pct(maioria1)} | {_pct(maioria3)} | |",
        ]
        for nome, r in resultados.items():
            destaque = "**" if nome == melhor else ""
            texto.append(
                f"| {destaque}{nome}{destaque} | {_pct(r['top1'])} | {_pct(r['top3'])} | {r['posicao_media']:.1f}º |"
            )
        texto += ["", "## Por tipo de proposição", "", "| Tipo | Quantas | " + " | ".join(resultados) + " |"]
        texto.append("|---|---|" + "---|" * len(resultados))
        for tipo, valores in por_tipo.items():
            celulas = [f"{_pct(valores[nome]['top1'])} / {_pct(valores[nome]['top3'])}" for nome in resultados]
            texto.append(f"| {tipo} | {valores['quantas']} | " + " | ".join(celulas) + " |")
        texto += ["", "Em cada célula: acerto no 1º lugar / entre os 3 primeiros.", ""]
        texto += [f"## Por tema ({melhor})", "", "| Tema | Proposições | No 1º lugar | Entre os 3 primeiros |"]
        texto.append("|---|---|---|---|")
        for nome, quantas, top1, top3 in por_tema:
            texto.append(f"| {nome} | {quantas} | {_pct(top1)} | {_pct(top3)} |")
        texto += [
            "",
            f"## Sugestões para as proposições acompanhadas sem tema ({len(sem_tema)}; "
            f"as {SUGESTOES_NO_RELATORIO} mais "
            f"recentes; todas em resultado.json)",
            "",
            "Só sugestão, para a equipe conferir: nada foi gravado no banco.",
            "",
            "| Proposição | Ementa | Temas sugeridos |",
            "|---|---|---|",
        ]
        for s in sugestoes[:SUGESTOES_NO_RELATORIO]:
            ementa = s["ementa"].replace("|", "/")
            ementa = ementa if len(ementa) <= 160 else ementa[:157] + "..."
            texto.append(f"| {s['sigla']} | {ementa} | {'; '.join(s['temas'])} |")
        with open(os.path.join(destino, "relatorio.md"), "w", encoding="utf-8") as arquivo:
            arquivo.write("\n".join(texto) + "\n")
        print("\n".join(texto[: 14 + len(resultados)]))
        print(f"Salvo em {destino}")


if __name__ == "__main__":
    main()
