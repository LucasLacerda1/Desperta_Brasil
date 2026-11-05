import os
import re
from collections import Counter
from dataclasses import dataclass

from flask import current_app
from sqlalchemy import text

from desperta.ext.db import db

# ----------------------------------------------------------
# Verificacao do banco (so leitura): estrutura, integridade e coerencia dos dados
# Decisao 11.1: o SQL proprio do SQLite (PRAGMA) fica em ext/db
# ----------------------------------------------------------
OK = "ok"
FALHA = "falha"
AVISO = "aviso"
INFO = "info"

PLACAR = re.compile(r"(Sim|Não|Abstenção|Total): (\d+)")
TIPOS_NO_PLACAR = ("Sim", "Não", "Abstenção")
# O voto do presidente da sessao aparece como "Artigo 17" e nao entra no total da Camara
VOTO_DO_PRESIDENTE = "Artigo 17"

# Datas de inicio e fim que precisam estar em ordem
PERIODOS = (
    ("legislatura", "data_inicio", "data_fim"),
    ("evento", "data_hora_inicio", "data_hora_fim"),
    ("lideranca", "data_inicio", "data_fim"),
    ("deputado_orgao", "data_inicio", "data_fim"),
    ("frente_membro", "data_inicio", "data_fim"),
)

# Como achar o registro de origem de cada trecho do RAG (tipo + ref_id, sem FK)
ORIGEM_DOS_TRECHOS = {
    "proposicao": "SELECT CAST(id AS TEXT) FROM proposicao",
    "tramitacao": "SELECT proposicao_id || '/' || sequencia FROM tramitacao",
    "votacao": "SELECT id FROM votacao",
    "evento": "SELECT CAST(id AS TEXT) FROM evento",
    "pauta_item": "SELECT evento_id || '/' || ordem FROM pauta_item",
}
ORIGEM_DAS_FONTES = {
    "proposicao": "SELECT CAST(id AS TEXT) FROM proposicao",
    "votacao": "SELECT id FROM votacao",
    "deputado": "SELECT CAST(id AS TEXT) FROM deputado",
    "evento": "SELECT CAST(id AS TEXT) FROM evento",
    "orgao": "SELECT CAST(id AS TEXT) FROM orgao",
    "partido": "SELECT CAST(id AS TEXT) FROM partido",
}


@dataclass
class Resultado:
    grupo: str
    nome: str
    situacao: str
    detalhe: str


def _valor(sql, **params):
    return db.session.execute(text(sql), params).scalar()


def _tabelas_do_banco():
    return {nome for (nome,) in db.session.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))}


def _colunas(tabela):
    return {linha[1] for linha in db.session.execute(text(f'PRAGMA table_info("{tabela}")'))}


def _versao_mais_nova():
    """A ultima migracao da pasta migrations do proprio projeto, e nao da pasta em que o comando roda."""
    from alembic.config import Config as ConfigAlembic
    from alembic.script import ScriptDirectory

    pasta = current_app.extensions["migrate"].directory
    if not os.path.isabs(pasta):
        pasta = os.path.join(os.path.dirname(current_app.root_path), pasta)
    config = ConfigAlembic()
    config.set_main_option("script_location", pasta)
    return ScriptDirectory.from_config(config).get_current_head()


# ======================================================
# ESTRUTURA
# ======================================================
def _estrutura():
    grupo = "Estrutura"
    integridade = [linha[0] for linha in db.session.execute(text("PRAGMA integrity_check"))]
    yield Resultado(
        grupo,
        "Integridade do arquivo (integrity_check)",
        OK if integridade == ["ok"] else FALHA,
        "; ".join(integridade[:3]),
    )
    violacoes = db.session.execute(text("PRAGMA foreign_key_check")).fetchall()
    yield Resultado(
        grupo, "Chaves estrangeiras (foreign_key_check)", OK if not violacoes else FALHA, f"{len(violacoes)} violacoes"
    )
    faltando = sorted(set(db.metadata.tables) - _tabelas_do_banco())
    yield Resultado(
        grupo,
        f"As {len(db.metadata.tables)} tabelas do modelo existem",
        OK if not faltando else FALHA,
        "faltam: " + ", ".join(faltando) if faltando else "todas presentes",
    )
    atual = _valor("SELECT version_num FROM alembic_version") if "alembic_version" in _tabelas_do_banco() else None
    mais_nova = _versao_mais_nova()
    yield Resultado(
        grupo,
        "Versao do esquema e a ultima migracao",
        OK if atual == mais_nova else FALHA,
        f"banco {atual}, migracoes {mais_nova}",
    )
    modo = _valor("PRAGMA journal_mode")
    yield Resultado(grupo, "Modo WAL", OK if modo == "wal" else FALHA, modo)
    yield Resultado(grupo, "foreign_keys ligado na conexao", OK if _valor("PRAGMA foreign_keys") == 1 else FALHA, "")


# ======================================================
# COERENCIA DOS DADOS
# ======================================================
def _placares():
    """Os votos gravados batem com o placar que a Camara escreve na descricao da votacao."""
    certas = 0
    erradas = []
    votacoes = db.session.execute(text("SELECT id, descricao FROM votacao WHERE descricao LIKE '%Total:%'"))
    for id_votacao, descricao in votacoes:
        placar = {chave: int(valor) for chave, valor in PLACAR.findall(descricao)}
        votos = Counter(
            dict(
                db.session.execute(
                    text("SELECT COALESCE(tipo_voto, ''), COUNT(*) FROM voto WHERE votacao_id = :id GROUP BY 1"),
                    {"id": id_votacao},
                ).all()
            )
        )
        total = sum(votos.values())
        if total == 0:
            continue
        presentes = total - votos[VOTO_DO_PRESIDENTE]
        # Votacao secreta: todos sem tipo; so o total pode ser conferido
        secreta = votos[""] == total
        bate = presentes == placar.get("Total") and (
            secreta or all(votos[tipo] == placar.get(tipo, 0) for tipo in TIPOS_NO_PLACAR)
        )
        if bate:
            certas += 1
        else:
            erradas.append(id_votacao)
    situacao = OK if not erradas else FALHA
    detalhe = f"{certas} de {certas + len(erradas)} votacoes batem"
    if erradas:
        detalhe += "; nao batem: " + ", ".join(erradas[:5])
    return Resultado("Coerencia", "Votos gravados x placar da Camara", situacao, detalhe)


def _referencias_sem_fk():
    tabelas = _tabelas_do_banco()
    perdidos = 0
    for tipo, origem in ORIGEM_DOS_TRECHOS.items():
        perdidos += _valor(
            f"SELECT COUNT(*) FROM trecho_rag WHERE tipo = :tipo AND ref_id NOT IN ({origem}) "
            "AND id NOT IN (SELECT trecho_id FROM geracao_trecho)",
            tipo=tipo,
        )
    yield Resultado(
        "Coerencia",
        "Trechos do RAG apontam para registros que existem",
        OK if not perdidos else FALHA,
        f"{perdidos} trechos sem origem",
    )
    sem_origem = 0
    if "noticia_fonte" in tabelas:
        for tipo, origem in ORIGEM_DAS_FONTES.items():
            sem_origem += _valor(
                f"SELECT COUNT(*) FROM noticia_fonte WHERE tipo = :tipo AND ref_id NOT IN ({origem})", tipo=tipo
            )
    yield Resultado(
        "Coerencia",
        "Fontes das noticias apontam para registros que existem",
        OK if not sem_origem else FALHA,
        f"{sem_origem} fontes sem origem",
    )


def _indices_de_busca():
    tabelas = _tabelas_do_banco()
    pares = (
        ("noticia_fts_docsize", "noticia", "Busca de texto das noticias (FTS5)"),
        ("trecho_fts_docsize", "trecho_rag", "Busca por palavras dos trechos (FTS5)"),
        ("vec_trecho_rowids", "trecho_rag", "Indice vetorial dos trechos (sqlite-vec)"),
    )
    for indice, tabela, nome in pares:
        if indice not in tabelas:
            yield Resultado("Coerencia", nome, INFO, "indice ainda nao criado")
            continue
        no_indice = _valor(f"SELECT COUNT(*) FROM {indice}")
        na_tabela = _valor(f"SELECT COUNT(*) FROM {tabela}")
        yield Resultado(
            "Coerencia",
            nome,
            OK if no_indice == na_tabela else FALHA,
            f"{no_indice} no indice, {na_tabela} em {tabela}",
        )


def _embeddings():
    errados = _valor("SELECT COUNT(*) FROM trecho_rag WHERE LENGTH(embedding) <> 3072")
    total = _valor("SELECT COUNT(*) FROM trecho_rag")
    return Resultado(
        "Coerencia",
        "Embeddings com 768 float32 (3.072 bytes)",
        OK if not errados else FALHA,
        f"{total - errados} de {total}",
    )


def _periodos():
    for tabela, inicio, fim in PERIODOS:
        invertidos = _valor(f"SELECT COUNT(*) FROM {tabela} WHERE {fim} IS NOT NULL AND {fim} < {inicio}")
        yield Resultado(
            "Coerencia",
            f"{tabela}: fim depois do inicio",
            OK if not invertidos else FALHA,
            f"{invertidos} com o fim antes do inicio",
        )


def _sincronizacao():
    hashes_ruins = 0
    sem_data = 0
    tabelas = 0
    for tabela in sorted(db.metadata.tables):
        colunas = _colunas(tabela)
        if "hash_origem" in colunas:
            tabelas += 1
            hashes_ruins += _valor(
                f"SELECT COUNT(*) FROM {tabela} WHERE LENGTH(hash_origem) <> 64 OR hash_origem GLOB '*[^0-9a-f]*'"
            )
        if "sincronizado_em" in colunas:
            sem_data += _valor(f"SELECT COUNT(*) FROM {tabela} WHERE sincronizado_em IS NULL")
    yield Resultado(
        "Coerencia",
        "hash_origem em SHA-256 (64 hexadecimais)",
        OK if not hashes_ruins else FALHA,
        f"{tabelas} tabelas; {hashes_ruins} hashes invalidos",
    )
    yield Resultado(
        "Coerencia", "sincronizado_em preenchido", OK if not sem_data else FALHA, f"{sem_data} linhas sem data"
    )


def _coletas():
    trava = os.path.exists(os.path.join(current_app.instance_path, "coletor.lock"))
    abertas = db.session.execute(
        text("SELECT id, recurso, iniciado_em FROM coleta WHERE finalizado_em IS NULL ORDER BY id")
    ).fetchall()
    if trava:
        detalhe = f"{len(abertas)} abertas, com uma coleta rodando agora"
        situacao = INFO
    else:
        detalhe = "; ".join(f"{id_} ({recurso}, {str(inicio)[:16]})" for id_, recurso, inicio in abertas)
        situacao = OK if not abertas else AVISO
    return Resultado("Coerencia", "Coletas sem horario de fim (interrompidas)", situacao, detalhe or "nenhuma")


# ======================================================
# INFORMACOES (nao sao erro)
# ======================================================
def _informacoes():
    tipos = current_app.config["TIPOS_ACOMPANHADOS"]
    marcadores = ", ".join(f":t{posicao}" for posicao in range(len(tipos)))
    pendentes = _valor(
        f"SELECT COUNT(*) FROM proposicao WHERE filhos_sincronizados_em IS NULL AND sigla_tipo IN ({marcadores})",
        **{f"t{posicao}": tipo for posicao, tipo in enumerate(tipos)},
    )
    yield Resultado(
        "Informacao",
        "Proposicoes dos tipos acompanhados sem autores, temas e tramitacoes",
        INFO,
        f"{pendentes} pendentes; a diaria tenta de novo",
    )
    votacoes = _valor("SELECT COUNT(*) FROM votacao WHERE filhos_sincronizados_em IS NULL")
    yield Resultado("Informacao", "Votacoes sem votos e orientacoes completos", INFO, f"{votacoes} pendentes")
    secretas = _valor(
        "SELECT COUNT(*) FROM (SELECT votacao_id FROM voto GROUP BY votacao_id HAVING COUNT(tipo_voto) = 0)"
    )
    yield Resultado("Informacao", "Votacoes secretas (votos sem tipo)", INFO, str(secretas))
    principais = ("proposicao", "tramitacao", "votacao", "voto", "deputado", "evento", "trecho_rag")
    contagem = ", ".join(
        f"{tabela} {_valor(f'SELECT COUNT(*) FROM {tabela}'):,}".replace(",", ".") for tabela in principais
    )
    yield Resultado("Informacao", "Linhas nas tabelas principais", INFO, contagem)


def verificar_banco():
    """Devolve a lista de resultados; nada e gravado."""
    resultados = list(_estrutura())
    resultados.append(_placares())
    resultados.extend(_referencias_sem_fk())
    resultados.extend(_indices_de_busca())
    resultados.append(_embeddings())
    resultados.extend(_periodos())
    resultados.extend(_sincronizacao())
    resultados.append(_coletas())
    resultados.extend(_informacoes())
    return resultados
