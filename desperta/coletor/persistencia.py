import os
import sqlite3
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from desperta.auth.models import Administrador
from desperta.ext.db import db
from desperta.ext.db.verificacao import FALHA, OK, Resultado, verificar_banco
from desperta.ia.models import TrechoRAG
from desperta.noticias.models import Noticia, NoticiaFonte, NoticiaRevisao
from desperta.orgaos.models import Orgao
from desperta.parlamentares.models import Deputado
from desperta.proposicoes.models import Proposicao, Tema
from desperta.sistema.models import Coleta, LogSistema
from desperta.votacoes.models import Votacao, Voto

from .execucao import ATUALIZADO, IGUAL, Execucao

# ----------------------------------------------------------
# Testes de persistencia: gravam, releem, atualizam e apagam numa COPIA do banco
# Os ids de teste ficam bem acima dos ids da Camara, para nao colidir com dados reais
# ----------------------------------------------------------
ID_TESTE = 990_000_001
AMOSTRA = 50
TEXTO_COM_ACENTOS = "Ação, coração e pão: “aspas”, ç, ã, é — e emoji 🗳️"
DATA_COM_MICROSSEGUNDOS = datetime(2026, 11, 4, 21, 30, 15, 123456)
COLUNAS_DE_SINCRONIZACAO = {"criado_em", "atualizado_em", "sincronizado_em", "hash_origem", "filhos_sincronizados_em"}


class ClienteSemRede:
    """A Execucao conta as requisicoes do cliente; aqui nenhuma chamada a API e feita."""

    requisicoes = 0
    erros_http = 0


def _proposicao_de_teste(id_=ID_TESTE, **campos):
    return Proposicao(
        **{
            "id": id_,
            "sigla_tipo": "PL",
            "cod_tipo": 139,
            "descricao_tipo": "Projeto de Lei",
            "numero": 1,
            "ano": 2026,
            "ementa": TEXTO_COM_ACENTOS,
            "data_apresentacao": DATA_COM_MICROSSEGUNDOS,
            "url_inteiro_teor": None,
            "data_status": None,
            "regime": None,
            "apreciacao": "Plenário",
            "hash_origem": "0" * 64,
            **campos,
        }
    )


def _valores_do_registro(registro):
    colunas = registro.__table__.columns.keys()
    return {coluna: getattr(registro, coluna) for coluna in colunas if coluna not in COLUNAS_DE_SINCRONIZACAO}


# ======================================================
# CASOS
# ======================================================
def _ida_e_volta(caminho):
    """Grava, fecha a conexao, abre de novo e compara: texto, datas, nulos, booleano, texto como id e bytes."""
    orgao_id = db.session.scalar(db.select(Orgao.id).limit(1))
    deputado_id = db.session.scalar(db.select(Deputado.id).limit(1))
    embedding = os.urandom(3072)
    id_votacao = f"{ID_TESTE}-1"
    db.session.add(_proposicao_de_teste())
    db.session.flush()
    db.session.add(
        Votacao(
            id=id_votacao,
            data=date(2026, 11, 4),
            data_hora_registro=DATA_COM_MICROSSEGUNDOS,
            orgao_id=orgao_id,
            sigla_orgao="PLEN",
            descricao=TEXTO_COM_ACENTOS,
            aprovacao=False,
            hash_origem="0" * 64,
        )
    )
    db.session.flush()
    db.session.add(
        Voto(
            votacao_id=id_votacao,
            deputado_id=deputado_id,
            tipo_voto=None,
            data_registro=DATA_COM_MICROSSEGUNDOS,
            sigla_partido="PT",
        )
    )
    db.session.add(
        TrechoRAG(
            tipo="proposicao",
            ref_id=str(ID_TESTE),
            parte=1,
            texto=TEXTO_COM_ACENTOS,
            tokens=1,
            embedding=embedding,
            modelo_embedding="teste-de-persistencia",
            hash_texto="0" * 64,
        )
    )
    db.session.commit()
    # Conexao nova: o que for lido agora veio do arquivo, e nao da memoria da sessao
    db.session.remove()
    db.engine.dispose()

    proposicao = db.session.get(Proposicao, ID_TESTE)
    votacao = db.session.get(Votacao, id_votacao)
    voto = db.session.get(Voto, (id_votacao, deputado_id))
    trecho = db.session.scalar(db.select(TrechoRAG).filter_by(modelo_embedding="teste-de-persistencia"))
    assert proposicao.ementa == TEXTO_COM_ACENTOS, "texto com acentos mudou"
    assert proposicao.data_apresentacao == DATA_COM_MICROSSEGUNDOS, "data e hora mudaram"
    assert (proposicao.regime, proposicao.data_status, proposicao.url_inteiro_teor) == (None, None, None)
    assert votacao.aprovacao is False and votacao.data == date(2026, 11, 4), "booleano ou data mudaram"
    assert voto.tipo_voto is None, "voto secreto perdeu o vazio"
    assert trecho.embedding == embedding, "embedding mudou"

    # Outra conexao, fora do SQLAlchemy, tambem enxerga o que foi gravado (WAL ja persistido)
    with sqlite3.connect(caminho) as conexao:
        assert conexao.execute("SELECT ementa FROM proposicao WHERE id = ?", (ID_TESTE,)).fetchone()[0] == (
            TEXTO_COM_ACENTOS
        )
    return "texto com acentos, data com microssegundos, nulos, booleano, id em texto e 3.072 bytes iguais"


def _upsert_sem_duplicar():
    """Regravar registros reais iguais nao cria linha nova nem marca como atualizado (RNF06)."""
    amostra = db.session.scalars(
        db.select(Proposicao).where(Proposicao.id < ID_TESTE).order_by(Proposicao.id).limit(AMOSTRA)
    ).all()
    valores = [(registro.id, _valores_do_registro(registro)) for registro in amostra]
    linhas_antes = db.session.scalar(db.select(db.func.count()).select_from(Proposicao))
    with Execucao(ClienteSemRede(), "proposicoes", "detalhe", "teste de persistencia") as execucao:
        for chave, campos in valores:
            execucao.principal(Proposicao, chave, campos)
        primeira = (execucao.coleta.itens_novos, execucao.coleta.itens_atualizados)
        for chave, campos in valores:
            execucao.principal(Proposicao, chave, campos)
        segunda_novos = execucao.coleta.itens_novos - primeira[0]
        segunda_atualizados = execucao.coleta.itens_atualizados - primeira[1]
    db.session.commit()
    linhas_depois = db.session.scalar(db.select(db.func.count()).select_from(Proposicao))
    assert linhas_depois == linhas_antes, f"linhas mudaram de {linhas_antes} para {linhas_depois}"
    assert (segunda_novos, segunda_atualizados) == (0, 0), "a segunda gravacao nao deu tudo igual"
    return (
        f"{len(valores)} proposicoes reais regravadas 2 vezes; na 2a, 0 novas e 0 atualizadas; {linhas_depois} linhas"
    )


def _atualizacao():
    """Conteudo mudado: a linha e atualizada no lugar, com hash e atualizado_em novos."""
    registro = db.session.get(Proposicao, ID_TESTE)
    hash_antes = registro.hash_origem
    campos = _valores_do_registro(registro)
    campos["ementa"] = TEXTO_COM_ACENTOS + " (corrigida)"
    with Execucao(ClienteSemRede(), "proposicoes", "detalhe", "teste de persistencia") as execucao:
        gravado = execucao.principal(Proposicao, ID_TESTE, campos)
        situacao = gravado.situacao_coleta
        inicio = execucao.inicio
    db.session.commit()
    registro = db.session.get(Proposicao, ID_TESTE)
    assert situacao == ATUALIZADO, f"situacao {situacao}"
    assert registro.ementa.endswith("(corrigida)") and registro.hash_origem != hash_antes
    assert registro.atualizado_em == inicio
    with Execucao(ClienteSemRede(), "proposicoes", "detalhe", "teste de persistencia") as execucao:
        de_novo = execucao.principal(Proposicao, ID_TESTE, campos).situacao_coleta
    assert de_novo == IGUAL, f"segunda vez deu {de_novo}"
    return "mesma linha atualizada, hash e atualizado_em novos; repetir a mesma mudanca deu igual"


def _isolamento_de_erro():
    """Um registro com campo obrigatorio vazio nao derruba os outros (decisao 10.2)."""
    ids = [ID_TESTE + 1, ID_TESTE + 2, ID_TESTE + 3]
    with Execucao(ClienteSemRede(), "proposicoes", "detalhe", "teste de persistencia") as execucao:
        for id_ in ids:
            campos = _valores_do_registro(_proposicao_de_teste(id_))
            if id_ == ids[1]:
                campos["ementa"] = None
            execucao.principal(Proposicao, id_, campos)
        coleta_id = execucao.coleta.id
    db.session.commit()
    gravadas = db.session.scalar(db.select(db.func.count()).select_from(Proposicao).where(Proposicao.id.in_(ids)))
    coleta = db.session.get(Coleta, coleta_id)
    erro = db.session.scalar(db.select(LogSistema).where(LogSistema.coleta_id == coleta_id, LogSistema.nivel == "erro"))
    assert gravadas == 2, f"{gravadas} gravadas"
    assert coleta.status == "parcial", coleta.status
    assert erro is not None and "proposicao.ementa" in erro.descricao
    return "2 de 3 gravadas; a com ementa vazia foi desfeita sozinha, com erro no log e coleta parcial"


def _restricoes():
    barrados = []
    tentativas = {
        "id repetido": lambda: db.session.add(_proposicao_de_teste()),
        "deputado inexistente": lambda: db.session.add(
            Voto(
                votacao_id=f"{ID_TESTE}-1",
                deputado_id=999_999_999,
                tipo_voto="Sim",
                data_registro=DATA_COM_MICROSSEGUNDOS,
                sigla_partido="PT",
            )
        ),
        "status invalido": lambda: db.session.add(
            Noticia(
                titulo="t",
                slug=f"teste-{ID_TESTE}",
                resumo="r",
                corpo="c",
                origem="ia",
                cod_tema=_tema(),
                status="inventado",
            )
        ),
    }
    for nome, tentar in tentativas.items():
        # Sessao limpa: o conflito tem de vir do banco, e nao do mapa de objetos do SQLAlchemy
        db.session.expunge_all()
        try:
            tentar()
            db.session.flush()
        except IntegrityError:
            barrados.append(nome)
        finally:
            db.session.rollback()
    assert len(barrados) == len(tentativas), f"so barrou: {barrados}"
    return "barrados: " + ", ".join(barrados)


def _tema():
    return db.session.scalar(db.select(Tema.cod_tema).limit(1))


def _cascata():
    admin = Administrador(nome="Teste", email=f"teste-{ID_TESTE}@desperta.org")
    admin.set_senha("teste")
    noticia = Noticia(titulo="Teste", slug=f"teste-{ID_TESTE}", resumo="r", corpo="c", origem="ia", cod_tema=_tema())
    db.session.add_all([admin, noticia])
    db.session.flush()
    db.session.add_all(
        [
            NoticiaFonte(noticia_id=noticia.id, tipo="proposicao", ref_id=str(ID_TESTE), ordem=1),
            NoticiaRevisao(noticia_id=noticia.id, admin_id=admin.id, acao="aprovou"),
        ]
    )
    db.session.commit()
    id_noticia = noticia.id
    db.session.delete(noticia)
    db.session.commit()
    sobras = db.session.scalar(
        db.select(db.func.count()).select_from(NoticiaFonte).where(NoticiaFonte.noticia_id == id_noticia)
    ) + db.session.scalar(
        db.select(db.func.count()).select_from(NoticiaRevisao).where(NoticiaRevisao.noticia_id == id_noticia)
    )
    assert sobras == 0, f"{sobras} filhos ficaram"
    return "apagar a noticia levou a fonte e a revisao"


CASOS = (
    ("Ida e volta: gravar, fechar, reabrir e ler igual", "ida_e_volta"),
    ("Upsert: regravar dados reais nao duplica nem atualiza", "upsert"),
    ("Atualizacao no lugar, com hash novo", "atualizacao"),
    ("Erro num registro nao derruba os outros", "isolamento"),
    ("Restricoes barram id repetido, FK invalida e valor invalido", "restricoes"),
    ("Cascata ao apagar a noticia", "cascata"),
)


def testar_persistencia(caminho):
    """Roda os casos em ordem; caminho e o arquivo da copia, ja ligado a db.session."""
    funcoes = {
        "ida_e_volta": lambda: _ida_e_volta(caminho),
        "upsert": _upsert_sem_duplicar,
        "atualizacao": _atualizacao,
        "isolamento": _isolamento_de_erro,
        "restricoes": _restricoes,
        "cascata": _cascata,
    }
    resultados = []
    for nome, chave in CASOS:
        try:
            resultados.append(Resultado("Persistencia", nome, OK, funcoes[chave]()))
        except Exception as erro:  # o relatorio mostra a falha e segue para o proximo caso
            db.session.rollback()
            resultados.append(Resultado("Persistencia", nome, FALHA, f"{type(erro).__name__}: {erro}"))
    # Depois de tudo, a copia continua integra
    for resultado in verificar_banco()[:2]:
        resultados.append(
            Resultado("Persistencia", f"Depois dos testes: {resultado.nome}", resultado.situacao, resultado.detalhe)
        )
    return resultados
