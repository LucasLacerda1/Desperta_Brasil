"""
Item 4 da decisao 22.10: depois de cada coleta, os fatos novos viram rascunho sozinhos.

Decisao do Lucas (07/11/2026): entram todas as votacoes (Plenario e comissoes) que afetam
um tipo acompanhado, todas as mudancas de situacao e todas as proposicoes novas dos tipos
acompanhados. Os fatos sao procurados numa janela de dias (GERACAO_JANELA_DIAS), e o que
ja tem geracao e pulado, entao rodar de novo nao duplica nada.

Decisao 25.1 (14/11/2026): mudanca de situacao e a situacao ser outra, e nao a data do
status ter andado (a Camara muda essa data a cada passo do andamento).
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from flask import current_app

from desperta.ext.db import db
from desperta.ext.db.busca import conferir_busca_raiz
from desperta.proposicoes.models import Proposicao, ProposicaoTema
from desperta.noticias.models import Noticia, NoticiaFonte
from desperta.proposicoes.models import TEMA_SEM_CLASSIFICACAO
from desperta.proposicoes.services import situacao_mudou, tema_principal
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao, VotacaoProposicao

from .geracao import _entrada, _ler_origem, chave_do_fato, gerar_noticia
from .gerador import CASO_NOVA, CASO_SITUACAO, CASO_VOTACAO
from .models import GeracaoIA


# === Resumo (o que aconteceu numa execucao) ===
@dataclass
class Resumo:
    inicio: date
    candidatos: int = 0
    gerados: Counter = field(default_factory=Counter)
    erros: int = 0
    ja_feitos: int = 0
    # Decisao 25.6: gerados no tema especial, porque a Camara ainda nao informou o tema
    sem_tema: int = 0
    # Noticias que sairam do tema especial porque a Camara classificou a proposicao
    temas_atualizados: int = 0
    pendentes: int = 0
    nao_feitos_pelo_limite: int = 0
    # Na simulacao: os (caso, ref) que seriam gerados
    simulados: list = field(default_factory=list)

    def em_texto(self):
        gerados = ", ".join(f"{caso}={total}" for caso, total in sorted(self.gerados.items())) or "nenhum"
        return (
            f"desde {self.inicio:%d/%m/%Y}: candidatos={self.candidatos} gerados=({gerados}) erros={self.erros} "
            f"ja_feitos={self.ja_feitos} sem_tema_da_camara={self.sem_tema} temas_atualizados={self.temas_atualizados} "
            f"pendentes_na_coleta={self.pendentes} "
            f"deixados_pelo_limite={self.nao_feitos_pelo_limite}"
        )


# ======================================================
# ESCOLHA DOS FATOS
# ======================================================
def _acompanhadas():
    return db.select(Proposicao.id).where(Proposicao.sigla_tipo.in_(current_app.config["TIPOS_ACOMPANHADOS"]))


def _votacoes(inicio):
    """Votacoes da janela que afetam uma proposicao acompanhada, no Plenario ou em comissao."""
    acompanhadas = _acompanhadas()
    afetadas = db.select(VotacaoProposicao.votacao_id).where(VotacaoProposicao.proposicao_id.in_(acompanhadas))
    return db.session.execute(
        db.select(Votacao.id, Votacao.filhos_sincronizados_em)
        .where(
            Votacao.data >= inicio,
            db.or_(Votacao.id.in_(afetadas), Votacao.proposicao_id.in_(acompanhadas)),
        )
        .order_by(Votacao.data_hora_registro, Votacao.id)
    ).all()


def _proposicoes(inicio):
    """Situacao que mudou de verdade (25.1) depois do dia da apresentacao, e proposicao apresentada na janela."""
    momento = datetime.combine(inicio, time.min)
    linhas = db.session.execute(
        db.select(
            Proposicao.id,
            Proposicao.data_apresentacao,
            Proposicao.data_status,
            Proposicao.cod_situacao,
            Proposicao.filhos_sincronizados_em,
        )
        .where(
            Proposicao.sigla_tipo.in_(current_app.config["TIPOS_ACOMPANHADOS"]),
            db.or_(Proposicao.data_apresentacao >= momento, Proposicao.data_status >= momento),
        )
        .order_by(Proposicao.data_status, Proposicao.id)
    ).all()
    situacoes, novas = [], []
    for linha in linhas:
        if (
            linha.data_status
            and linha.data_status >= momento
            and (linha.data_status.date() > linha.data_apresentacao.date())
            and situacao_mudou(linha.id, linha.cod_situacao, linha.data_status)
        ):
            # A situacao do dia da apresentacao ja aparece na noticia da proposicao nova
            situacoes.append(linha)
        if linha.data_apresentacao >= momento:
            novas.append(linha)
    novas.sort(key=lambda linha: (linha.data_apresentacao, linha.id))
    return situacoes, novas


def fatos_da_janela(inicio):
    """(caso, ref, pendente) em ordem: votacoes primeiro, como na coleta (decisao 15.2)."""
    situacoes, novas = _proposicoes(inicio)
    fatos = [(CASO_VOTACAO, linha.id, linha.filhos_sincronizados_em is None) for linha in _votacoes(inicio)]
    fatos += [(CASO_SITUACAO, linha.id, linha.filhos_sincronizados_em is None) for linha in situacoes]
    fatos += [(CASO_NOVA, linha.id, linha.filhos_sincronizados_em is None) for linha in novas]
    return fatos


# ======================================================
# GERACAO
# ======================================================
def _entradas_feitas(refazer_erros):
    """
    Fato que ja tem geracao nao e gerado de novo, nem quando a equipe rejeitou a noticia
    (o comando flask ia gerar continua podendo refazer a rejeitada, a mao).
    """
    consulta = db.select(GeracaoIA.entrada)
    if refazer_erros:
        consulta = consulta.where(GeracaoIA.status == "ok")
    # 25.16: compara o que identifica o fato, e nao a entrada inteira (ver chave_do_fato)
    return {chave_do_fato(entrada) for entrada in db.session.scalars(consulta)}


def _tem_tema(proposicao_id):
    return db.session.scalar(db.select(ProposicaoTema.cod_tema).filter_by(proposicao_id=proposicao_id).limit(1))


def atualizar_temas():
    """
    Decisao 25.6: noticia no tema especial cuja proposicao ja ganhou tema da Camara passa para
    o tema principal (25.2). O texto nao muda: ele diz que, quando foi escrito, nao havia tema.
    Devolve quantas noticias mudaram de tema; cada mudanca fica no log.
    """
    linhas = db.session.execute(
        db.select(Noticia, NoticiaFonte.ref_id)
        .join(NoticiaFonte, NoticiaFonte.noticia_id == Noticia.id)
        .where(
            Noticia.cod_tema == TEMA_SEM_CLASSIFICACAO,
            Noticia.status.in_(("rascunho", "em_revisao", "publicada")),
            NoticiaFonte.tipo == "proposicao",
        )
        .order_by(Noticia.id, NoticiaFonte.ordem)
    ).all()
    mudaram = 0
    vistas = set()
    for noticia, ref_id in linhas:
        if noticia.id in vistas or not ref_id.isdigit():
            continue
        vistas.add(noticia.id)
        cod_tema = tema_principal(int(ref_id))
        if cod_tema is None:
            continue
        noticia.cod_tema = cod_tema
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="IA",
                acao="tema_atualizado",
                descricao=(
                    f"A Camara informou o tema da proposicao {ref_id}: a noticia saiu de 'sem tema' para {cod_tema}."
                ),
                entidade="noticia",
                entidade_id=str(noticia.id),
            )
        )
        mudaram += 1
    db.session.commit()
    return mudaram


def gerar_novos(modelo, dias=None, limite=None, simular=False, refazer_erros=False, hoje=None):
    """
    Gera os rascunhos dos fatos da janela. modelo None: so busca por palavras (21.3).
    simular=True nao grava nada: so diz o que seria gerado.
    """
    dias = current_app.config["GERACAO_JANELA_DIAS"] if dias is None else dias
    inicio = (hoje or date.today()) - timedelta(days=dias)
    resumo = Resumo(inicio=inicio)
    feitas = _entradas_feitas(refazer_erros)
    if not simular:
        resumo.temas_atualizados = atualizar_temas()
    if not simular and conferir_busca_raiz(db.session.connection()):
        # Decisao 25.3: havia noticia fora do indice das raizes (gravada por outra versao do codigo)
        db.session.add(
            LogSistema(
                nivel="aviso",
                modulo="IA",
                acao="busca_raiz_refeita",
                descricao="O indice da busca pela raiz das palavras nao tinha todas as noticias e foi refeito.",
            )
        )
        db.session.commit()

    for caso, ref, pendente in fatos_da_janela(inicio):
        resumo.candidatos += 1
        if pendente:
            # Autores, temas, tramitacoes ou votos ainda nao chegaram: fica para a proxima execucao
            resumo.pendentes += 1
            continue
        proposicao, votacao = _ler_origem(caso, ref)
        entrada = chave_do_fato(_entrada(caso, proposicao, votacao))
        if entrada in feitas:
            resumo.ja_feitos += 1
            continue
        sem_tema = not _tem_tema(proposicao.id)
        if limite is not None and sum(resumo.gerados.values()) + resumo.erros >= limite:
            resumo.nao_feitos_pelo_limite += 1
            continue
        feitas.add(entrada)
        if simular:
            resumo.simulados.append((caso, ref))
            resumo.gerados[caso] += 1
            resumo.sem_tema += sem_tema
            continue
        geracao, _ = gerar_noticia(modelo, caso, ref)
        if geracao.status == "ok":
            resumo.gerados[caso] += 1
            # Decisao 25.6: a proposicao sem tema da Camara vira noticia no tema especial
            resumo.sem_tema += sem_tema
        else:
            resumo.erros += 1

    if not simular:
        db.session.add(
            LogSistema(
                nivel="aviso" if resumo.erros else "info",
                modulo="IA",
                acao="gerar_novos",
                descricao=resumo.em_texto(),
            )
        )
        db.session.commit()
    return resumo


# ======================================================
# DEPOIS DE CADA COLETA (AGENDADOR)
# ======================================================
def carregar_modelo_ou_nada(qual=None):
    """
    Decisao 21.3: sem o modelo (pendrive fora, no caso da RoBERTaLexPT), sem a placa pedida ou sem o
    PyTorch, devolve None e deixa um aviso no log; a geracao segue so com a busca por palavras.
    Decisao 25.10: qual e roberta ou e5; o padrao e o da escrita dos rascunhos (RAG_MODELO).
    """
    from flask import current_app

    from . import embeddings, services

    try:
        return services.carregar_modelo(qual or current_app.config["RAG_MODELO"])
    except embeddings.ModeloAusente:
        # O aviso ja foi para o log em carregar_modelo
        return None
    except (embeddings.DispositivoIndisponivel, ImportError) as erro:
        db.session.add(LogSistema(nivel="aviso", modulo="IA", acao="modelo_indisponivel", descricao=str(erro)))
        db.session.commit()
        return None


def depois_da_coleta():
    """
    Secao 6.1 e decisao 23.2: indexa o que e novo ou mudou e escreve os rascunhos dos fatos novos.
    Decisao 25.10: cada modelo indexa os seus trechos; sem um deles, a indexacao dele fica para a
    proxima vez (ela e incremental pelo hash_texto) e o outro segue. A escrita usa o de RAG_MODELO.
    Devolve ({modelo: resumo da indexacao ou None}, resumo da geracao).
    """
    from flask import current_app

    from . import services

    modelos = {qual: carregar_modelo_ou_nada(qual) for qual in services.MODELOS}
    indexacoes = {qual: services.indexar(modelo) if modelo is not None else None for qual, modelo in modelos.items()}
    return indexacoes, gerar_novos(modelos[current_app.config["RAG_MODELO"]])
