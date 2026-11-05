import json
import time

from flask import current_app

from desperta.ext.db import db
from desperta.noticias.models import Noticia
from desperta.noticias.services import criar_rascunho
from desperta.orgaos.models import Orgao
from desperta.proposicoes.models import Proposicao, ProposicaoAutor, ProposicaoTema, Tramitacao
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao, VotacaoProposicao
from desperta.votacoes.services import situacao_dos_votos

from . import services
from .gerador import (
    CASO_VOTACAO,
    DadosNoticia,
    DadosProposicao,
    DadosTramitacao,
    DadosVotacao,
    TRAMITACOES_NO_CORPO,
    criar_gerador,
)
from .models import GeracaoIA, GeracaoTrecho

TAMANHO_CONSULTA = 300


class ErroDeGeracao(Exception):
    """O registro nao permite escrever a noticia; vira geracao_ia com status erro."""


def _nome_do_orgao(orgao_id, sigla):
    """Decisao 14.1: sigla vazia e "sem valor"; mostra o nome."""
    if sigla:
        return sigla
    orgao = db.session.get(Orgao, orgao_id)
    return orgao.nome if orgao else "órgão não informado"


def _dados_da_proposicao(proposicao):
    autores = db.session.scalars(
        db.select(ProposicaoAutor).filter_by(proposicao_id=proposicao.id).order_by(ProposicaoAutor.ordem)
    ).all()
    return DadosProposicao(
        sigla=proposicao.sigla_tipo,
        numero=proposicao.numero,
        ano=proposicao.ano,
        descricao_tipo=proposicao.descricao_tipo,
        ementa=proposicao.ementa,
        apresentada_em=proposicao.data_apresentacao.date(),
        autor=autores[0].nome if autores else None,
        mais_autores=len(autores) > 1,
        situacao=proposicao.situacao,
        regime=proposicao.regime,
        apreciacao=proposicao.apreciacao,
    )


def _tramitacoes(proposicao_id):
    passos = db.session.scalars(
        db.select(Tramitacao)
        .filter_by(proposicao_id=proposicao_id)
        .order_by(Tramitacao.sequencia.desc())
        .limit(TRAMITACOES_NO_CORPO)
    ).all()
    return [
        DadosTramitacao(
            data=passo.data_hora.date(),
            orgao=_nome_do_orgao(passo.orgao_id, passo.sigla_orgao),
            descricao=passo.descricao,
            despacho=passo.despacho,
        )
        for passo in reversed(passos)
    ]


def _proposicao_da_votacao(votacao):
    """A proposicao objeto pode ser um requerimento: prefere a afetada de um tipo acompanhado."""
    ids = list(db.session.scalars(db.select(VotacaoProposicao.proposicao_id).filter_by(votacao_id=votacao.id)))
    if votacao.proposicao_id and votacao.proposicao_id not in ids:
        ids.append(votacao.proposicao_id)
    proposicoes = db.session.scalars(db.select(Proposicao).where(Proposicao.id.in_(ids))).all()
    acompanhados = current_app.config["TIPOS_ACOMPANHADOS"]
    proposicoes = sorted(proposicoes, key=lambda item: (item.sigla_tipo not in acompanhados, item.id))
    if not proposicoes:
        raise ErroDeGeracao(f"A votacao {votacao.id} nao tem proposicao no banco.")
    return proposicoes[0]


def _dados_da_votacao(votacao):
    situacao = situacao_dos_votos(votacao)
    contagem = situacao.votos
    return DadosVotacao(
        descricao=votacao.descricao,
        data=votacao.data,
        sigla_orgao=votacao.sigla_orgao,
        orgao=_nome_do_orgao(votacao.orgao_id, votacao.sigla_orgao),
        aprovacao=votacao.aprovacao,
        sim=contagem.get("Sim", 0),
        nao=contagem.get("Não", 0),
        abstencao=contagem.get("Abstenção", 0),
        situacao=situacao.codigo,
        explicacao=situacao.explicacao,
    )


def _ler_origem(caso, ref):
    """Devolve (proposicao, votacao ou None); caso que nao existe para em erro, antes de escrever."""
    if caso == CASO_VOTACAO:
        votacao = db.session.get(Votacao, str(ref))
        if votacao is None:
            raise ErroDeGeracao(f"Votacao {ref} nao encontrada.")
        return _proposicao_da_votacao(votacao), votacao
    proposicao = db.session.get(Proposicao, int(ref))
    if proposicao is None:
        raise ErroDeGeracao(f"Proposicao {ref} nao encontrada.")
    return proposicao, None


def _tema_principal(proposicao):
    """A noticia precisa de um tema (RF05): o de maior relevancia entre os que a API mandou."""
    cod_tema = db.session.scalar(
        db.select(ProposicaoTema.cod_tema)
        .filter_by(proposicao_id=proposicao.id)
        .order_by(ProposicaoTema.relevancia.desc(), ProposicaoTema.cod_tema)
        .limit(1)
    )
    if cod_tema is None:
        raise ErroDeGeracao(f"A proposicao {proposicao.id} nao tem tema.")
    return cod_tema


def _entrada(caso, proposicao, votacao):
    """Os ids usados; data_status separa duas mudancas de situacao da mesma proposicao."""
    return json.dumps(
        {
            "caso": caso,
            "proposicao_id": proposicao.id,
            "votacao_id": votacao.id if votacao else None,
            # Fase 2b: a Camara pode nao informar a data da situacao
            "data_status": proposicao.data_status.isoformat() if proposicao.data_status else None,
        },
        sort_keys=True,
    )


def _geracao_existente(entrada):
    """Gerar de novo o mesmo fato nao duplica a noticia; so a rejeitada pode ser refeita."""
    return db.session.scalar(
        db.select(GeracaoIA)
        .join(Noticia, Noticia.id == GeracaoIA.noticia_id)
        .where(GeracaoIA.entrada == entrada, GeracaoIA.status == "ok", Noticia.status != "rejeitada")
        .limit(1)
    )


def _fontes(proposicao, votacao):
    """A primeira gera o link da fonte oficial."""
    fontes = []
    if votacao:
        fontes.append(("votacao", votacao.id))
    fontes.append(("proposicao", str(proposicao.id)))
    if votacao:
        fontes.append(("orgao", str(votacao.orgao_id)))
    return fontes


def _registrar_erro(caso, ref, consulta, entrada, gerador_nome, versao, erro, inicio):
    db.session.rollback()
    config = current_app.config
    geracao = GeracaoIA(
        modelo_geracao=gerador_nome,
        modelo_embedding=config["EMBEDDING_MODEL"],
        consulta=consulta,
        top_k=config["RAG_TOP_K"],
        versao_prompt=versao,
        entrada=entrada,
        duracao_ms=int((time.monotonic() - inicio) * 1000),
        status="erro",
        erro=str(erro),
    )
    db.session.add(geracao)
    db.session.add(
        LogSistema(
            nivel="erro",
            modulo="IA",
            acao="gerar_noticia",
            descricao=f"caso={caso} ref={ref}: {erro}",
            entidade="geracao_ia",
        )
    )
    db.session.commit()
    return geracao


def gerar_noticia(modelo, caso, ref, gerador=None):
    """
    Secao 6: toda execucao grava geracao_ia, mesmo com erro; a noticia entra como rascunho (RF06).
    modelo None: sem a RoBERTaLexPT (21.3), busca so por palavras. Devolve (geracao, nova).
    """
    config = current_app.config
    inicio = time.monotonic()
    consulta = f"{caso} {ref}"
    entrada = json.dumps({"caso": caso, "ref": str(ref)})
    nome = config["GERADOR"]
    versao = "desconhecida"
    try:
        gerador = gerador or criar_gerador(config["GERADOR"])
        nome, versao = gerador.nome, gerador.versao_prompt
        proposicao, votacao = _ler_origem(caso, ref)
        consulta = f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano} {proposicao.ementa}"[
            :TAMANHO_CONSULTA
        ]
        entrada = _entrada(caso, proposicao, votacao)
        existente = _geracao_existente(entrada)
        if existente:
            return existente, False

        cod_tema = _tema_principal(proposicao)
        dados = DadosNoticia(
            caso=caso,
            proposicao=_dados_da_proposicao(proposicao),
            votacao=_dados_da_votacao(votacao) if votacao else None,
            tramitacoes=_tramitacoes(proposicao.id),
        )
        fontes = _fontes(proposicao, votacao)
        achados = services.buscar(modelo, consulta, modo="hibrida" if modelo else "palavras")
        texto = gerador.escrever(consulta, [achado.trecho.texto for achado in achados], dados)

        noticia = criar_rascunho(texto.titulo, texto.resumo, texto.corpo, cod_tema, fontes)
        geracao = GeracaoIA(
            noticia_id=noticia.id,
            modelo_geracao=gerador.nome,
            modelo_embedding=config["EMBEDDING_MODEL"],
            consulta=consulta,
            top_k=config["RAG_TOP_K"],
            versao_prompt=gerador.versao_prompt,
            entrada=entrada,
            tokens_entrada=texto.tokens_entrada,
            tokens_saida=texto.tokens_saida,
            duracao_ms=int((time.monotonic() - inicio) * 1000),
            status="ok",
        )
        db.session.add(geracao)
        db.session.flush()
        db.session.add_all(
            GeracaoTrecho(
                geracao_id=geracao.id,
                trecho_id=achado.trecho.id,
                posicao=achado.posicao,
                similaridade=achado.similaridade,
            )
            for achado in achados
        )
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="IA",
                acao="gerar_noticia",
                descricao=f"caso={caso} ref={ref} gerador={gerador.nome} trechos={len(achados)}",
                entidade="noticia",
                entidade_id=str(noticia.id),
            )
        )
        db.session.commit()
        return geracao, True
    except Exception as erro:
        return _registrar_erro(caso, ref, consulta, entrada, nome, versao, erro, inicio), True
