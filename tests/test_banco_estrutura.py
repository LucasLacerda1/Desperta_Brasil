import pytest
from sqlalchemy import inspect

from desperta.ext.db import db as _db

PKS = {
    "proposicao": {"id"},
    "proposicao_autor": {"proposicao_id", "ordem"},
    "proposicao_tema": {"proposicao_id", "cod_tema"},
    "tema": {"cod_tema"},
    "tramitacao": {"proposicao_id", "sequencia"},
    "votacao": {"id"},
    "voto": {"votacao_id", "deputado_id"},
    "orientacao": {"votacao_id", "partido_bloco"},
    "votacao_proposicao": {"votacao_id", "proposicao_id"},
    "deputado": {"id"},
    "partido": {"id"},
    "legislatura": {"id"},
    "lideranca": {"id"},
    "bloco": {"id"},
    "bloco_partido": {"bloco_id", "partido_id"},
    "frente": {"id"},
    "frente_membro": {"frente_id", "deputado_id"},
    "orgao": {"id"},
    "deputado_orgao": {"deputado_id", "orgao_id", "data_inicio"},
    "evento": {"id"},
    "pauta_item": {"evento_id", "ordem"},
    "administrador": {"id"},
    "noticia": {"id"},
    "noticia_fonte": {"noticia_id", "tipo", "ref_id"},
    "noticia_revisao": {"id"},
    "geracao_ia": {"id"},
    "trecho_rag": {"id"},
    "geracao_trecho": {"geracao_id", "trecho_id"},
    "log_sistema": {"id"},
    "coleta": {"id"},
    "visitante": {"id"},
    "visitante_tema": {"visitante_id", "cod_tema"},
}

# Secao 5.5: pai, atributo no pai, filho, atributo no filho, cascade
RELACIONAMENTOS = [
    ("Proposicao", "autores", "ProposicaoAutor", "proposicao", True),
    ("Proposicao", "tramitacoes", "Tramitacao", "proposicao", True),
    ("Proposicao", "temas", "ProposicaoTema", "proposicao", True),
    ("Proposicao", "votacoes", "Votacao", "proposicao", False),
    ("Tema", "proposicoes", "ProposicaoTema", "tema", False),
    ("Tema", "noticias", "Noticia", "tema", False),
    ("Tema", "visitantes", "VisitanteTema", "tema", False),
    ("Deputado", "autorias", "ProposicaoAutor", "deputado", False),
    ("Deputado", "votos", "Voto", "deputado", False),
    ("Partido", "deputados", "Deputado", "partido", False),
    ("Partido", "orientacoes", "Orientacao", "partido", False),
    ("Legislatura", "deputados", "Deputado", "legislatura", False),
    ("Votacao", "votos", "Voto", "votacao", True),
    ("Votacao", "orientacoes", "Orientacao", "votacao", True),
    ("Orgao", "tramitacoes", "Tramitacao", "orgao", False),
    ("Orgao", "eventos", "Evento", "orgao", False),
    ("Orgao", "votacoes", "Votacao", "orgao", False),
    ("Evento", "votacoes", "Votacao", "evento", False),
    ("Visitante", "temas", "VisitanteTema", "visitante", True),
    ("Administrador", "logs", "LogSistema", "administrador", False),
    ("Coleta", "logs", "LogSistema", "coleta", False),
    ("Noticia", "fontes", "NoticiaFonte", "noticia", True),
    ("Noticia", "revisoes", "NoticiaRevisao", "noticia", True),
    ("Administrador", "revisoes", "NoticiaRevisao", "administrador", False),
    ("Noticia", "geracoes", "GeracaoIA", "noticia", False),
    ("GeracaoIA", "trechos", "GeracaoTrecho", "geracao", True),
    ("TrechoRAG", "geracoes", "GeracaoTrecho", "trecho", False),
    ("Deputado", "liderancas", "Lideranca", "deputado", False),
    ("Deputado", "cargos", "DeputadoOrgao", "deputado", False),
    ("Orgao", "membros", "DeputadoOrgao", "orgao", False),
    ("Legislatura", "blocos", "Bloco", "legislatura", False),
    ("Bloco", "partidos", "BlocoPartido", "bloco", True),
    ("Partido", "blocos", "BlocoPartido", "partido", False),
    ("Legislatura", "frentes", "Frente", "legislatura", False),
    ("Frente", "membros", "FrenteMembro", "frente", True),
    ("Deputado", "frentes", "FrenteMembro", "deputado", False),
    ("Evento", "pauta", "PautaItem", "evento", True),
    ("Proposicao", "pautas", "PautaItem", "proposicao", False),
    ("Deputado", "relatorias", "PautaItem", "relator", False),
    ("Votacao", "itens_pauta", "PautaItem", "votacao", False),
    ("Votacao", "proposicoes_afetadas", "VotacaoProposicao", "votacao", True),
    ("Proposicao", "votacoes_afetadas", "VotacaoProposicao", "proposicao", True),
]

IDS_DA_API = [
    ("proposicao", "id"),
    ("tema", "cod_tema"),
    ("deputado", "id"),
    ("partido", "id"),
    ("legislatura", "id"),
    ("bloco", "id"),
    ("frente", "id"),
    ("orgao", "id"),
    ("evento", "id"),
]


def _classes():
    return {m.class_.__name__: m.class_ for m in _db.Model.registry.mappers}


def _fks(tabela):
    return {fk.target_fullname for fk in _db.metadata.tables[tabela].foreign_keys}


def test_exatamente_32_tabelas(db):
    assert set(db.metadata.tables) == set(PKS)
    assert len(db.metadata.tables) == 32


def test_tabelas_criadas_no_banco(db):
    tabelas = {t for t in inspect(db.engine).get_table_names() if not t.startswith("noticia_fts")}
    assert tabelas == set(PKS)


@pytest.mark.parametrize("tabela, colunas", PKS.items())
def test_chave_primaria(db, tabela, colunas):
    assert {c.name for c in db.metadata.tables[tabela].primary_key.columns} == colunas


@pytest.mark.parametrize("tabela, coluna", IDS_DA_API)
def test_ids_da_api_nao_sao_gerados_pelo_banco(db, tabela, coluna):
    assert db.metadata.tables[tabela].c[coluna].autoincrement is False


def test_42_chaves_estrangeiras(db):
    assert sum(len(t.foreign_keys) for t in db.metadata.tables.values()) == 42


def test_tabelas_sem_fk_para_a_api(db):
    assert _fks("trecho_rag") == set()
    assert _fks("noticia_fonte") == {"noticia.id"}
    assert not db.metadata.tables["pauta_item"].c["proposicao_relacionada_id"].foreign_keys


def test_regra_t1_sem_atalhos(db):
    assert _fks("lideranca") == {"deputado.id"}
    assert "orgao_id" not in db.metadata.tables["proposicao"].c


def test_partido_sigla_sem_unique(db):
    tabela = db.metadata.tables["partido"]
    assert not tabela.c["sigla"].unique
    assert not any(i.unique for i in tabela.indexes)


def test_lista_tem_42_relacionamentos():
    assert len(RELACIONAMENTOS) == 42


@pytest.mark.parametrize("pai, atr_pai, filho, atr_filho, cascade", RELACIONAMENTOS)
def test_relacionamento(db, pai, atr_pai, filho, atr_filho, cascade):
    classes = _classes()
    lado_pai = inspect(classes[pai]).relationships[atr_pai]
    lado_filho = inspect(classes[filho]).relationships[atr_filho]

    assert lado_pai.mapper.class_ is classes[filho]
    assert lado_filho.mapper.class_ is classes[pai]
    assert lado_pai.back_populates == atr_filho
    assert lado_filho.back_populates == atr_pai
    assert lado_pai.uselist is True
    assert lado_filho.uselist is False
    assert lado_pai.cascade.delete_orphan is cascade


def test_nenhum_relacionamento_fora_da_secao_5_5(db):
    total = sum(len(inspect(c).relationships) for c in _classes().values())
    assert total == 2 * len(RELACIONAMENTOS)
