import os
import sqlite3
from datetime import datetime

import click
from flask import current_app
from flask.cli import AppGroup

from desperta.ext.db import db
from desperta.ext.db.busca import criar_busca_texto, remover_busca_texto

banco = AppGroup("banco", help="Verificacao e testes de persistencia do banco.")

SIMBOLOS = {"ok": "PASSOU", "falha": "FALHOU", "aviso": "AVISO", "info": "INFO"}
ARQUIVO_DA_COPIA = "persistencia-copia.db"


def _mostrar(resultados, titulo, relatorio, banco_usado=None):
    """Mostra no terminal e, se pedido, grava um relatorio em Markdown; devolve quantas falharam."""
    for resultado in resultados:
        click.echo(f"[{SIMBOLOS[resultado.situacao]:6}] {resultado.grupo} | {resultado.nome}: {resultado.detalhe}")
    contagem = {situacao: sum(1 for r in resultados if r.situacao == situacao) for situacao in SIMBOLOS}
    resumo = (
        f"{contagem['ok']} passaram, {contagem['falha']} falharam, "
        f"{contagem['aviso']} avisos e {contagem['info']} informacoes"
    )
    click.echo(resumo)
    if relatorio:
        linhas = [
            f"# {titulo}",
            "",
            f"*{datetime.now():%d/%m/%Y %H:%M}, banco `{banco_usado or db.engine.url.database}`.*",
            "",
            f"**{resumo}.**",
            "",
            "| Situação | Grupo | Verificação | Detalhe |",
            "|---|---|---|---|",
        ]
        linhas += [
            f"| {SIMBOLOS[r.situacao]} | {r.grupo} | {r.nome} | {r.detalhe.replace('|', '/')} |" for r in resultados
        ]
        with open(relatorio, "w", encoding="utf-8") as saida:
            saida.write("\n".join(linhas) + "\n")
        click.echo(f"Relatorio em {relatorio}")
    return contagem["falha"]


@banco.command("verificar")
@click.option("--relatorio", type=click.Path(dir_okay=False), help="Grava tambem um relatorio em Markdown.")
def verificar(relatorio):
    """Confere estrutura, integridade e coerencia dos dados, sem gravar nada."""
    from desperta.ext.db.verificacao import verificar_banco

    if _mostrar(verificar_banco(), "Verificação do banco", relatorio):
        raise SystemExit(1)


def _copiar(origem, destino):
    """Copia pelo backup do SQLite: inclui o que ainda esta no arquivo WAL."""
    for sufixo in ("", "-wal", "-shm"):
        if os.path.exists(destino + sufixo):
            os.remove(destino + sufixo)
    with sqlite3.connect(f"file:{origem}?mode=ro", uri=True) as fonte, sqlite3.connect(destino) as copia:
        fonte.backup(copia)


@banco.command("testar-persistencia")
@click.option("--relatorio", type=click.Path(dir_okay=False), help="Grava tambem um relatorio em Markdown.")
@click.option("--manter-copia", is_flag=True, help="Nao apaga a copia usada nos testes.")
def testar_persistencia(relatorio, manter_copia):
    """Grava, rele, atualiza e apaga dados de teste numa COPIA do banco; o banco original nao muda."""
    from desperta import create_app
    from desperta.coletor.persistencia import testar_persistencia as testar

    origem = db.engine.url.database
    if not origem or origem == ":memory:":
        raise click.ClickException("O teste de persistencia precisa de um banco em arquivo.")
    os.makedirs(current_app.instance_path, exist_ok=True)
    copia = os.path.join(current_app.instance_path, ARQUIVO_DA_COPIA)
    _copiar(origem, copia)
    classe = type(
        "ConfigDaCopia",
        (current_app.config["CLASSE_DE_CONFIGURACAO"],),
        {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{copia}"},
    )
    app_da_copia = create_app(classe)
    with app_da_copia.app_context():
        resultados = testar(copia)
        db.session.remove()
        db.engine.dispose()
    click.echo(f"Copia usada: {copia}")
    if not manter_copia:
        for sufixo in ("", "-wal", "-shm"):
            if os.path.exists(copia + sufixo):
                os.remove(copia + sufixo)
    if _mostrar(resultados, "Testes de persistência", relatorio, f"copia de {origem}"):
        raise SystemExit(1)


def init_app(app):
    app.cli.add_command(banco)

    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas do banco de dados."""
        db.create_all()
        with db.engine.begin() as conexao:
            criar_busca_texto(conexao)
        click.echo(f"Banco criado com {len(db.metadata.tables)} tabelas.")

    @app.cli.command("drop-db")
    def drop_db():
        """Apaga todas as tabelas do banco de dados."""
        with db.engine.begin() as conexao:
            remover_busca_texto(conexao)
        db.drop_all()
        click.echo("Tabelas apagadas.")
