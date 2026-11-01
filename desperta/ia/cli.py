import json
import os
from datetime import date

import click
from flask import current_app
from flask.cli import AppGroup

from . import centralizacao, services
from .embeddings import ModeloEmbedding, preparar_ambiente
from .models import TRECHO_RAG_TIPOS

ia = AppGroup("ia", help="Trechos, embeddings e busca do RAG.")


def _modelo(offline=None):
    preparar_ambiente(current_app, offline)
    return ModeloEmbedding(current_app.config["EMBEDDING_MODEL"])


def _tamanho_em_mb(pasta):
    total = 0
    for raiz, _, arquivos in os.walk(pasta):
        # O Hugging Face liga os arquivos por atalhos: so os arquivos de verdade contam
        caminhos = (os.path.join(raiz, nome) for nome in arquivos)
        total += sum(os.path.getsize(caminho) for caminho in caminhos if not os.path.islink(caminho))
    return total // 1_000_000


@ia.command("baixar-modelo")
def baixar_modelo():
    """Baixa o modelo uma vez para instance/modelos e confere se ele carrega."""
    modelo = _modelo(offline=False)
    if len(modelo.embutir(["teste"])[0]) != 3072:
        raise click.ClickException("O modelo nao gerou um embedding de 768 dimensoes.")
    pasta = os.environ["HF_HOME"]
    click.echo(f"Modelo pronto em {pasta} ({_tamanho_em_mb(pasta)} MB). Agora pode usar HF_HUB_OFFLINE=1.")


def _data(ctx, param, valor):
    return date.fromisoformat(valor) if valor else None


_opcao_tipo = click.option("--tipo", "tipos", multiple=True, type=click.Choice(TRECHO_RAG_TIPOS), help="Pode repetir.")


@ia.command("indexar")
@_opcao_tipo
@click.option("--limite", type=int, help="Maximo de trechos com embedding novo nesta execucao.")
def indexar(tipos, limite):
    """Cria os trechos e os embeddings do que e novo ou mudou."""
    resumo = services.indexar(_modelo(), tipos or None, limite)
    click.echo(
        f"indexados={resumo['indexados']} iguais={resumo['iguais']} "
        f"removidos={resumo['removidos']} mantidos={resumo['mantidos']}"
    )


@ia.command("buscar")
@click.argument("consulta")
@_opcao_tipo
@click.option("--k", type=int, help="Quantos trechos (padrao: RAG_TOP_K).")
@click.option("--inicio", callback=_data, help="Inicio do periodo (AAAA-MM-DD).")
@click.option("--fim", callback=_data, help="Fim do periodo (AAAA-MM-DD).")
@click.option("--modo", type=click.Choice(services.MODOS_BUSCA), default="hibrida", show_default=True)
def buscar(consulta, tipos, k, inicio, fim, modo):
    """Mostra os trechos mais parecidos com a consulta."""
    for achado in services.buscar(_modelo(), consulta, k, tipos or None, inicio, fim, modo):
        trecho = achado.trecho
        click.echo(f"{achado.posicao}. {achado.similaridade:.3f} {trecho.tipo} {trecho.ref_id}: {trecho.texto[:150]}")


@ia.command("medir-busca")
@click.argument("arquivo", default="tests/dados/consultas_busca.json")
def medir_busca(arquivo):
    """Quantas das proposicoes esperadas aparecem nos 8 primeiros, em cada modo (decisao 16.2)."""
    with open(arquivo, encoding="utf-8") as entrada:
        consultas = json.load(entrada)["consultas"]
    for modo, resultado in services.medir_busca(_modelo(), consultas).items():
        click.echo(f"{modo}: {resultado['acertos']} de {resultado['total']}")
        for consulta, certas, esperadas in resultado["consultas"]:
            click.echo(f"  {certas}/{esperadas} {consulta}")


@ia.command("centralizar")
def centralizar():
    """Calcula o vetor medio dos trechos; depois, use RAG_CENTRALIZAR=1 e flask ia reconstruir."""
    total = centralizacao.calcular(current_app.config["EMBEDDING_MODEL"])
    click.echo(f"Vetor medio de {total} trechos gravado em instance/{centralizacao.ARQUIVO}")


@ia.command("reconstruir")
def reconstruir():
    """Refaz os indices vetorial e de palavras a partir de trecho_rag, sem gerar embeddings."""
    click.echo(f"{services.reconstruir_indice(current_app.config['EMBEDDING_MODEL'])} trechos no indice")


def init_app(app):
    app.cli.add_command(ia)
