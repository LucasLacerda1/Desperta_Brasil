import click

from desperta.ext.db import db
from desperta.ext.db.busca import criar_busca_texto, remover_busca_texto
from desperta.ia import vetores


def init_app(app):
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
        vetores.remover_indice()
        db.session.commit()
        with db.engine.begin() as conexao:
            remover_busca_texto(conexao)
        db.drop_all()
        click.echo("Tabelas apagadas.")
