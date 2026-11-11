import json
import os
import tempfile
from datetime import date

import click
from flask import current_app
from flask.cli import AppGroup

from . import automatico, centralizacao, embeddings, geracao, services
from .gerador import CASOS
from .models import TRECHO_RAG_TIPOS

ia = AppGroup("ia", help="Trechos, embeddings e busca do RAG.")


def _modelo():
    try:
        return services.carregar_modelo()
    except (embeddings.RobertaAusente, embeddings.DispositivoIndisponivel) as erro:
        raise click.ClickException(str(erro))


def _conferir_arquivos(pasta, modelo):
    """Mostra a lista da decisao 21.2 e confere se o modelo carregou de verdade."""
    if len(modelo.embutir(["teste"])[0]) != 3072:
        raise click.ClickException("O modelo nao gerou um embedding de 768 dimensoes.")
    for nome in sorted(os.listdir(pasta)):
        click.echo(f"  {nome}")
    click.echo(f"Modelo pronto em {pasta} ({embeddings.tamanho_em_mb(pasta)} MB).")


def _carregar_da_pasta(pasta):
    embeddings.preparar_ambiente(current_app)
    return embeddings.ModeloEmbedding(current_app.config["EMBEDDING_MODEL"], pasta=pasta)


@ia.command("baixar-modelo")
def baixar_modelo():
    """Baixa a RoBERTaLexPT uma vez para ROBERTA_DIR e confere se ela carrega."""
    config = current_app.config
    pasta = embeddings.caminho_no_projeto(current_app, config["ROBERTA_DIR"])
    if embeddings.arquivos_faltando(pasta):
        # Decisao 21.3: pendrive desconectado nao vira um download para o disco do PC
        if config["ROBERTA_DIR"] != config["ROBERTA_DIR_PADRAO"] and not os.path.isdir(os.path.dirname(pasta)):
            raise click.ClickException(f"A pasta {os.path.dirname(pasta)} nao existe. O pendrive está conectado?")
        # O cache do Hugging Face so serve durante o download (21.2)
        modelos = embeddings.caminho_no_projeto(current_app, config["MODELOS_DIR"])
        os.makedirs(modelos, exist_ok=True)
        embeddings.preparar_ambiente(current_app, offline=False)
        with tempfile.TemporaryDirectory(dir=modelos) as cache:
            embeddings.salvar_modelo(config["EMBEDDING_MODEL"], pasta, cache)
    _conferir_arquivos(pasta, _carregar_da_pasta(pasta))
    click.echo("Agora pode usar HF_HUB_OFFLINE=1.")


@ia.command("mover-roberta")
@click.option("--para", "destino", required=True, help="Nova pasta da RoBERTaLexPT (o pendrive).")
def mover_roberta(destino):
    """Copia a RoBERTaLexPT para outra pasta e confere; a copia antiga nao e apagada."""
    origem = embeddings.caminho_no_projeto(current_app, current_app.config["ROBERTA_DIR"])
    destino = os.path.abspath(destino)
    if embeddings.arquivos_faltando(origem):
        raise click.ClickException(f"RoBERTaLexPT não encontrada em {origem}.")
    try:
        embeddings.copiar_modelo(origem, destino)
    except (OSError, ValueError) as erro:
        raise click.ClickException(str(erro))
    _conferir_arquivos(destino, _carregar_da_pasta(destino))
    click.echo(f"Atualize o .env com: ROBERTA_DIR={destino}")
    click.echo(f"A cópia antiga continua em {origem}; apagar é decisão sua, depois de conferir.")


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
    """Quantas das proposicoes esperadas aparecem nos 8 primeiros, em cada modo (decisoes 16.2 e 19.2)."""
    with open(arquivo, encoding="utf-8") as entrada:
        consultas = json.load(entrada)["consultas"]
    for modo, resultado in services.medir_busca(_modelo(), consultas).items():
        click.echo(
            f"{modo}: {resultado['acertos']} de {resultado['total']}; fora do assunto: {resultado['fora_do_assunto']}"
        )
        for consulta, certas, esperadas in resultado["consultas"]:
            click.echo(f"  {certas}/{esperadas} {consulta}")


def _modelo_ou_palavras():
    try:
        return services.carregar_modelo()
    except embeddings.RobertaAusente as erro:
        # Decisao 21.3: sem o pendrive, busca so por palavras; o aviso ja foi para o log
        click.echo(f"{erro} Usando só a busca por palavras.")
        return None
    except embeddings.DispositivoIndisponivel as erro:
        raise click.ClickException(str(erro))


@ia.command("gerar")
@click.argument("caso", type=click.Choice(CASOS))
@click.argument("ref")
def gerar(caso, ref):
    """Escreve um rascunho: nova ou situacao recebem o id da proposicao; votacao, o id da votacao."""
    registro, nova = geracao.gerar_noticia(_modelo_ou_palavras(), caso, ref)
    if registro.status == "erro":
        raise click.ClickException(f"Geracao {registro.id} com erro: {registro.erro}")
    if not nova:
        click.echo(f"Esse fato já tem o rascunho {registro.noticia.slug}; nada foi gerado.")
        return
    click.echo(f"Rascunho {registro.noticia.slug} (geracao {registro.id}, {registro.modelo_geracao})")
    click.echo(registro.noticia.titulo)
    click.echo(registro.noticia.resumo)
    click.echo(registro.noticia.corpo)


@ia.command("gerar-novos")
@click.option("--dias", type=int, help="Quantos dias para tras olhar (padrao: GERACAO_JANELA_DIAS).")
@click.option("--limite", type=int, help="No maximo este numero de rascunhos nesta execucao.")
@click.option("--simular", is_flag=True, help="So mostra o que seria gerado, sem gravar nada.")
@click.option("--refazer-erros", is_flag=True, help="Tenta de novo os fatos cuja geracao deu erro.")
def gerar_novos(dias, limite, simular, refazer_erros):
    """Rascunho de cada votacao, mudanca de situacao e proposicao nova dos ultimos dias."""
    modelo = None if simular else _modelo_ou_palavras()
    resumo = automatico.gerar_novos(modelo, dias, limite, simular, refazer_erros)
    if simular:
        for caso, ref in resumo.simulados:
            click.echo(f"  {caso} {ref}")
        click.echo("Simulação: nada foi gravado.")
    click.echo(resumo.em_texto())


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
