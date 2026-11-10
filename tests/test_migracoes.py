import shutil
from pathlib import Path

import flask_migrate
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

import fabricas
from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.db import db
from desperta.noticias.services import buscar_noticias

MIGRACOES = Path(__file__).parent.parent / "migrations"
GATILHOS = {"noticia_fts_ai", "noticia_fts_ad", "noticia_fts_au"}

MIGRACAO_NULLABLE = """
from alembic import op
import sqlalchemy as sa

revision = "{revisao}"
down_revision = "{anterior}"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("{tabela}") as batch_op:
        batch_op.alter_column("{coluna}", existing_type=sa.Text(), nullable=True)


def downgrade():
    pass
"""


@pytest.fixture
def app_arquivo(tmp_path):
    class ConfigArquivo(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'teste.db'}"

    app = create_app(ConfigArquivo)
    with app.app_context():
        yield app
        db.session.remove()
        db.engine.dispose()


def _revisao_inicial():
    return ScriptDirectory(str(MIGRACOES)).get_current_head()


def _gatilhos():
    with db.engine.connect() as conexao:
        return set(conexao.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'")).scalars())


def _upgrade():
    flask_migrate.upgrade(directory=str(MIGRACOES))


def test_upgrade_cria_tudo(app_arquivo):
    _upgrade()
    tabelas = set(inspect(db.engine).get_table_names())
    assert set(db.metadata.tables) <= tabelas
    assert len(db.metadata.tables) == 32
    assert "noticia_fts" in tabelas
    assert _gatilhos() == GATILHOS
    with db.engine.connect() as conexao:
        assert conexao.execute(text("SELECT version_num FROM alembic_version")).scalar() == _revisao_inicial()


def test_autogenerate_nao_encontra_diferencas(app_arquivo):
    _upgrade()

    def ignorar_busca_texto(object, name, type_, reflected, compare_to):
        return not (type_ == "table" and name.startswith("noticia_fts"))

    with db.engine.connect() as conexao:
        contexto = MigrationContext.configure(
            conexao, opts={"include_object": ignorar_busca_texto, "compare_type": True}
        )
        assert compare_metadata(contexto, db.metadata) == []


def test_check_ignora_os_indices_do_rag(app_arquivo):
    """Decisao 16.4: sem a extensao, ler as colunas de vec_trecho daria erro no flask db check."""
    sqlite_vec = pytest.importorskip("sqlite_vec")
    _upgrade()
    with db.engine.begin() as conexao:
        sqlite = conexao.connection.driver_connection
        sqlite.enable_load_extension(True)
        sqlite_vec.load(sqlite)
        conexao.execute(text("CREATE VIRTUAL TABLE vec_trecho USING vec0(trecho_id INTEGER PRIMARY KEY, v float[2])"))
        conexao.execute(text("CREATE VIRTUAL TABLE trecho_fts USING fts5(texto)"))
    db.engine.dispose()
    flask_migrate.check(directory=str(MIGRACOES))


def test_downgrade_base_apaga_tudo(app_arquivo):
    _upgrade()
    flask_migrate.downgrade(directory=str(MIGRACOES), revision="base")
    assert set(inspect(db.engine).get_table_names()) <= {"alembic_version"}
    assert _gatilhos() == set()


def test_upgrade_de_novo_depois_do_downgrade(app_arquivo):
    _upgrade()
    flask_migrate.downgrade(directory=str(MIGRACOES), revision="base")
    _upgrade()
    assert _gatilhos() == GATILHOS


def test_foreign_keys_continua_ligada_depois_da_migracao(app_arquivo):
    _upgrade()
    with db.engine.connect() as conexao:
        assert conexao.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_busca_funciona_no_banco_migrado(app_arquivo):
    _upgrade()
    fabricas.popular(db)
    noticia = fabricas.noticia(slug="migrada", titulo="Saúde", status="publicada")
    db.session.add(noticia)
    db.session.commit()
    assert buscar_noticias("saude") == [noticia]


def test_batch_em_tabelas_com_dados_e_filhas(app_arquivo, tmp_path):
    """Fase 2b: ajustar nullable recria a tabela, que ja tem dados e filhas."""
    pasta = tmp_path / "migrations"
    shutil.copytree(MIGRACOES, pasta, ignore=shutil.ignore_patterns("__pycache__"))
    flask_migrate.upgrade(directory=str(pasta))

    dados = fabricas.popular(db)
    noticia_id = dados.noticia.id
    dados.noticia.status = "publicada"
    db.session.commit()
    db.session.remove()

    (pasta / "versions" / "aaa_proposicao.py").write_text(
        MIGRACAO_NULLABLE.format(
            revisao="aaa", anterior=_revisao_inicial(), tabela="proposicao", coluna="url_inteiro_teor"
        )
    )
    (pasta / "versions" / "bbb_noticia.py").write_text(
        MIGRACAO_NULLABLE.format(revisao="bbb", anterior="aaa", tabela="noticia", coluna="corpo")
    )
    flask_migrate.upgrade(directory=str(pasta))

    colunas = {c["name"]: c for c in inspect(db.engine).get_columns("proposicao")}
    assert colunas["url_inteiro_teor"]["nullable"] is True
    with db.engine.connect() as conexao:
        assert conexao.execute(text("SELECT count(*) FROM proposicao_autor")).scalar() == 1
        assert conexao.execute(text("SELECT count(*) FROM noticia_fonte")).scalar() == 1
        assert conexao.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conexao.execute(text("PRAGMA foreign_key_check")).all() == []

    # Os gatilhos da busca voltam, e o indice continua valendo para quem ja existia
    assert _gatilhos() == GATILHOS
    noticia = db.session.get(type(dados.noticia), noticia_id)
    assert buscar_noticias("camara") == [noticia]
    noticia.titulo = "Titulo com palavranova"
    db.session.commit()
    assert buscar_noticias("palavranova") == [noticia]
