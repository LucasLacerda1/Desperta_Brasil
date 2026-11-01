from datetime import date

import click
from flask import current_app
from flask.cli import AppGroup

from . import services
from .embeddings import ModeloEmbedding
from .models import TRECHO_RAG_TIPOS

ia = AppGroup("ia", help="Trechos, embeddings e busca do RAG.")


def _modelo():
    return ModeloEmbedding(current_app.config["EMBEDDING_MODEL"])


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
def buscar(consulta, tipos, k, inicio, fim):
    """Mostra os trechos mais parecidos com a consulta."""
    for achado in services.buscar(_modelo(), consulta, k, tipos or None, inicio, fim):
        trecho = achado.trecho
        click.echo(f"{achado.posicao}. {achado.similaridade:.3f} {trecho.tipo} {trecho.ref_id}: {trecho.texto[:150]}")


@ia.command("reconstruir")
def reconstruir():
    """Refaz o indice vetorial a partir de trecho_rag, sem gerar embeddings."""
    click.echo(f"{services.reconstruir_indice(current_app.config['EMBEDDING_MODEL'])} trechos no indice")


def init_app(app):
    app.cli.add_command(ia)
