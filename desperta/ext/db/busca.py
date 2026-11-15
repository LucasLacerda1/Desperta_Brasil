import re
import threading
import unicodedata
from functools import lru_cache

from sqlalchemy import event, inspect, text
from sqlalchemy.exc import OperationalError

# ----------------------------------------------------------
# Raiz das palavras (decisao 25.3)
# O FTS5 nao tem stemmer de portugues. O indice guarda o texto ja reduzido a raiz
# ("professores" e "professora" viram "professor"), e a consulta e reduzida do mesmo jeito.
# Snowball (snowballstemmer, BSD) e Python puro: nao e modelo e pode rodar na API.
# ----------------------------------------------------------
_PALAVRA = re.compile(r"\w+")
_por_thread = threading.local()


def _stemmer():
    # O stemmer guarda estado enquanto trabalha: um por thread
    if not hasattr(_por_thread, "stemmer"):
        import snowballstemmer

        _por_thread.stemmer = snowballstemmer.stemmer("portuguese")
    return _por_thread.stemmer


def _sem_acento(texto):
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


@lru_cache(maxsize=100_000)
def _raizes_da_palavra(palavra):
    """
    A raiz da palavra como foi escrita e a raiz dela sem acento, quando sao diferentes.
    O Snowball depende do acento ("vacinação" vira "vacin", mas "vacinacao" vira "vacinaca"):
    com as duas no indice, quem digita sem acento tambem acha.
    """
    stemmer = _stemmer()
    escrita = _sem_acento(stemmer.stemWord(palavra))
    sem_acento = stemmer.stemWord(_sem_acento(palavra))
    return tuple(dict.fromkeys(r for r in (escrita, sem_acento) if r))


def grupos_de_raizes(consulta):
    """Uma tupla de raizes para cada palavra diferente da consulta, na ordem em que aparecem."""
    palavras = dict.fromkeys(_PALAVRA.findall(str(consulta or "").lower()))
    return list(dict.fromkeys(grupo for grupo in map(_raizes_da_palavra, palavras) if grupo))


def raiz(texto):
    """O texto em minusculas, com cada palavra trocada pelas suas raizes, sem acento (e o que o indice guarda)."""
    if not texto:
        return ""
    return " ".join(r for palavra in _PALAVRA.findall(str(texto).lower()) for r in _raizes_da_palavra(palavra))


def raizes_da_consulta(consulta):
    """Todas as raizes das palavras da consulta, sem repetir."""
    return list(dict.fromkeys(r for grupo in grupos_de_raizes(consulta) for r in grupo))


def registrar_funcoes(conexao_dbapi):
    """raiz() dentro do SQL serve so para refazer um indice inteiro (INSERT ... SELECT raiz(texto))."""
    conexao_dbapi.create_function("raiz", 1, raiz, deterministic=True)


def acompanhar_pela_raiz(modelo, tabela, colunas):
    """
    Mantem o indice das raizes a cada gravacao do modelo feita pelo ORM.
    De proposito nao ha gatilho no banco chamando raiz(): com gatilho, uma versao do codigo
    sem a funcao (outra branch, por exemplo) nao conseguiria mais gravar na tabela.
    Exclusao em lote, fora do ORM, precisa apagar do indice por conta propria.
    """
    lista = ", ".join(colunas)
    marcas = ", ".join(f":{coluna}" for coluna in colunas)
    inserir = text(f"INSERT INTO {tabela}(rowid, {lista}) VALUES (:id, {marcas})")
    apagar = text(f"DELETE FROM {tabela} WHERE rowid = :id")

    def valores(alvo):
        return {"id": alvo.id, **{coluna: raiz(getattr(alvo, coluna)) for coluna in colunas}}

    def executar(conexao, *comandos):
        try:
            for comando, parametros in comandos:
                conexao.execute(comando, parametros)
        except OperationalError as erro:
            # Indice ainda nao criado neste banco: quem cria o indice ja inclui o que existe
            if "no such table" not in str(erro):
                raise

    @event.listens_for(modelo, "after_insert")
    def _inserido(mapper, conexao, alvo):
        executar(conexao, (inserir, valores(alvo)))

    @event.listens_for(modelo, "after_update")
    def _alterado(mapper, conexao, alvo):
        estado = inspect(alvo)
        if any(estado.attrs[coluna].history.has_changes() for coluna in colunas):
            executar(conexao, (apagar, {"id": alvo.id}), (inserir, valores(alvo)))

    @event.listens_for(modelo, "after_delete")
    def _apagado(mapper, conexao, alvo):
        executar(conexao, (apagar, {"id": alvo.id}))


# ----------------------------------------------------------
# Busca de texto nas noticias (tabelas virtuais FTS5)
# Nao sao modelos SQLAlchemy e nao contam como tabelas do modelo.
# noticia_fts guarda as palavras como estao; noticia_fts_raiz guarda as raizes (25.3)
# e e a que a busca do portal usa.
# ----------------------------------------------------------
CRIAR_BUSCA_TEXTO = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS noticia_fts USING fts5(
        titulo, resumo, corpo,
        content='noticia', content_rowid='id',
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS noticia_fts_ai AFTER INSERT ON noticia BEGIN
        INSERT INTO noticia_fts(rowid, titulo, resumo, corpo)
        VALUES (new.id, new.titulo, new.resumo, new.corpo);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS noticia_fts_ad AFTER DELETE ON noticia BEGIN
        INSERT INTO noticia_fts(noticia_fts, rowid, titulo, resumo, corpo)
        VALUES ('delete', old.id, old.titulo, old.resumo, old.corpo);
    END
    """,
    # So OF titulo, resumo, corpo: somar visualizacoes nao reindexa a noticia
    """
    CREATE TRIGGER IF NOT EXISTS noticia_fts_au AFTER UPDATE OF titulo, resumo, corpo ON noticia BEGIN
        INSERT INTO noticia_fts(noticia_fts, rowid, titulo, resumo, corpo)
        VALUES ('delete', old.id, old.titulo, old.resumo, old.corpo);
        INSERT INTO noticia_fts(rowid, titulo, resumo, corpo)
        VALUES (new.id, new.titulo, new.resumo, new.corpo);
    END
    """,
    # Indice das raizes: tabela FTS5 comum (guarda o proprio texto), mantida pelo codigo (acompanhar_pela_raiz)
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS noticia_fts_raiz USING fts5(
        titulo, resumo, corpo,
        tokenize='unicode61 remove_diacritics 2'
    )
    """,
)

REMOVER_BUSCA_RAIZ = ("DROP TABLE IF EXISTS noticia_fts_raiz",)
REMOVER_BUSCA_TEXTO = REMOVER_BUSCA_RAIZ + (
    "DROP TRIGGER IF EXISTS noticia_fts_au",
    "DROP TRIGGER IF EXISTS noticia_fts_ad",
    "DROP TRIGGER IF EXISTS noticia_fts_ai",
    "DROP TABLE IF EXISTS noticia_fts",
)


def criar_busca_texto(conexao):
    for comando in CRIAR_BUSCA_TEXTO:
        conexao.execute(text(comando))


def remover_busca_texto(conexao):
    for comando in REMOVER_BUSCA_TEXTO:
        conexao.execute(text(comando))


def preencher_busca_raiz(conexao):
    """Refaz o indice das raizes a partir das noticias (para banco que ja tinha noticias)."""
    conexao.execute(text("DELETE FROM noticia_fts_raiz"))
    conexao.execute(
        text(
            "INSERT INTO noticia_fts_raiz(rowid, titulo, resumo, corpo) "
            "SELECT id, raiz(titulo), raiz(resumo), raiz(corpo) FROM noticia"
        )
    )


def conferir_busca_raiz(conexao):
    """
    Rede de seguranca: se o indice das raizes nao tem uma linha por noticia (noticias gravadas
    por uma versao do codigo que nao o mantinha), refaz o indice. Devolve True se refez.
    """
    existe = conexao.execute(text("SELECT 1 FROM sqlite_master WHERE name = 'noticia_fts_raiz'")).first()
    if not existe:
        # Banco que ainda nao passou pela migracao da 25.3: a migracao cria e preenche o indice
        return False
    noticias = conexao.execute(text("SELECT COUNT(*) FROM noticia")).scalar()
    no_indice = conexao.execute(text("SELECT COUNT(*) FROM noticia_fts_raiz_docsize")).scalar()
    if noticias == no_indice:
        return False
    preencher_busca_raiz(conexao)
    return True


def remover_busca_raiz(conexao):
    for comando in REMOVER_BUSCA_RAIZ:
        conexao.execute(text(comando))
