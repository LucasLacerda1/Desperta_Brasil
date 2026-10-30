import click

from desperta.ext.db import db


def init_app(app):
    @app.cli.command("init-db")
    def init_db():
        """Cria as tabelas do banco de dados."""
        db.create_all()
        click.echo(f"Banco criado com {len(db.metadata.tables)} tabelas.")

    @app.cli.command("drop-db")
    def drop_db():
        """Apaga todas as tabelas do banco de dados."""
        db.drop_all()
        click.echo("Tabelas apagadas.")
