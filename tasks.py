from invoke import task


@task
def install(c):
    """Instala o projeto em modo editavel com dependencias de desenvolvimento e teste."""
    c.run('pip install -e ".[dev,test]"', echo=True)


@task
def initdb(c):
    """Cria as 32 tabelas no SQLite (instance/desperta.db)."""
    c.run("flask --app app.py init-db", echo=True)


@task
def migrate(c):
    """Aplica as migracoes no banco (flask db upgrade)."""
    c.run("flask --app app.py db upgrade", echo=True)


@task
def coletar(c, rotina="horaria"):
    """Roda uma rotina de coleta: base, horaria, diaria, semanal ou mensal."""
    c.run(f"flask --app app.py coletar {rotina}", echo=True)


@task
def run(c):
    """Executa a aplicacao Flask."""
    c.run("flask --app app.py run --debug", pty=True)


@task
def test(c):
    """Executa os testes automatizados."""
    c.run("pytest tests -v --cov=desperta", echo=True)


@task
def lint(c):
    """Verificacao de estilo com flake8."""
    c.run("flake8 desperta tests", echo=True)


@task
def format(c):
    """Formata o codigo com o Black."""
    c.run("black desperta tests", echo=True)
