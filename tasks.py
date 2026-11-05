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


# Decisao 12.2: amostra de tipos, epocas e recursos, com limite de tempo em cada passo
AMOSTRA_VALIDACAO = [
    (900, "base"),
    *(
        (600, f"proposicoes --inicio {inicio} --fim {fim} --sigla-tipo {tipo} --limite-pendentes 0")
        for inicio, fim in (("2005-03-15", "2005-03-16"), ("2015-03-17", "2015-03-18"), ("2025-03-18", "2025-03-19"))
        for tipo in ("PL", "PLP", "PEC", "MPV", "PDL")
    ),
    (900, "eventos --inicio 2025-03-11 --fim 2025-03-13"),
    (1200, "votacoes --inicio 2025-03-11 --fim 2025-03-13"),
    (300, "eventos-pendentes --limite 50"),
    (600, "membros --limite 30"),
    (120, "mesa"),
    (600, "liderancas"),
    (300, "blocos"),
    (600, "frentes"),
]


@task
def carga_validacao(c):
    """Roda a amostra da decisao 12.2. Use com nohup para nao morrer se a sessao fechar."""
    for limite, comando in AMOSTRA_VALIDACAO:
        c.run(f"timeout {limite} flask --app app.py coletar {comando}", echo=True, warn=True)
    c.run("flask --app app.py coletar relatorio", echo=True)


@task(name="baixar-modelo")
def baixar_modelo(c):
    """Baixa a RoBERTaLexPT uma vez para ROBERTA_DIR (cerca de 500 MB)."""
    c.run("flask --app app.py ia baixar-modelo", echo=True)


@task
def indexar(c):
    """Cria os trechos e os embeddings do RAG (precisa de pip install -e ".[ia]")."""
    c.run("flask --app app.py ia indexar", echo=True)


@task(name="verificar-banco")
def verificar_banco(c):
    """Confere estrutura, integridade e coerencia do banco, sem gravar nada."""
    c.run("flask --app app.py banco verificar --relatorio instance/verificacao-banco.md", echo=True)


@task(name="testar-persistencia")
def testar_persistencia(c):
    """Grava, rele, atualiza e apaga dados de teste numa copia do banco."""
    c.run("flask --app app.py banco testar-persistencia --relatorio instance/persistencia.md", echo=True)


@task(name="ver-banco")
def ver_banco(c, banco="instance/desperta.db", porta=8001):
    """Abre o banco no navegador (Datasette, so leitura), em http://127.0.0.1:8001. So para desenvolvimento."""
    try:
        import sqlite_vec

        extensao = f'--load-extension="{sqlite_vec.loadable_path()}"'
    except ImportError:
        extensao = ""
    c.run(
        f"datasette {banco} -m scripts/ver_banco/metadata.json {extensao} -h 127.0.0.1 -p {porta} "
        "--setting sql_time_limit_ms 5000 --open",
        pty=True,
    )


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
