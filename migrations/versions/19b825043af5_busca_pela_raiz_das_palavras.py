"""busca pela raiz das palavras: indice FTS5 noticia_fts_raiz (decisao 25.3)

Revision ID: 19b825043af5
Revises: f8a2f7162512
Create Date: 2026-11-15 00:10:00.000000

"""
from alembic import op

from desperta.ext.db.busca import criar_busca_texto, preencher_busca_raiz, remover_busca_raiz


# revision identifiers, used by Alembic.
revision = '19b825043af5'
down_revision = 'f8a2f7162512'
branch_labels = None
depends_on = None


def upgrade():
    # Tabela virtual fora das 32: guarda as raizes das palavras das noticias, mantida por gatilhos.
    # O que ja existe (noticia_fts) fica como esta; as noticias ja gravadas entram no indice novo.
    conexao = op.get_bind()
    criar_busca_texto(conexao)
    preencher_busca_raiz(conexao)


def downgrade():
    remover_busca_raiz(op.get_bind())
