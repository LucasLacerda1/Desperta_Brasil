import click
from flask.cli import AppGroup

from desperta.ext.erros import ErroDoPortal

from . import services

equipe = AppGroup("equipe", help="Cadastro da equipe (o primeiro admin nasce aqui).")


@equipe.command("criar-admin")
@click.option("--nome", prompt=True)
@click.option("--email", prompt="E-mail")
@click.option("--papel", type=click.Choice(["admin", "editor"]), default="admin", show_default=True)
@click.password_option("--senha", prompt="Senha", confirmation_prompt="Repita a senha")
def criar_admin(nome, email, papel, senha):
    """Cria alguem da equipe pelo terminal; a API so deixa um admin criar outros."""
    try:
        admin = services.criar_administrador(nome, email, senha, papel)
    except ErroDoPortal as erro:
        raise click.ClickException(erro.mensagem)
    click.echo(f"Criado: {admin.nome} <{admin.email}>, papel {admin.papel}.")


@equipe.command("listar")
def listar():
    for admin in services.listar_equipe():
        situacao = "ativo" if admin.ativo else "desativado"
        click.echo(f"{admin.id:4} {admin.papel:6} {situacao:10} {admin.nome} <{admin.email}>")


def init_app(app):
    app.cli.add_command(equipe)
