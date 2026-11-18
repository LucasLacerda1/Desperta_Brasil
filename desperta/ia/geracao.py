import json
import time

from flask import current_app

from desperta.ext.db import db
from desperta.noticias.models import Noticia
from desperta.noticias import viva
from desperta.noticias.services import criar_rascunho, secoes_do_corpo
from desperta.orgaos.models import Orgao
from desperta.proposicoes.models import Proposicao, ProposicaoAutor, Tramitacao
from desperta.proposicoes.services import tema_da_noticia
from desperta.proposicoes.situacoes import SITUACOES, situacao_conhecida
from desperta.sistema.lacunas import URL_FICHA, lacunas_das_fontes
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao, VotacaoProposicao
from desperta.votacoes.services import situacao_dos_votos

from . import services
from .gerador import (
    CASO_VOTACAO,
    SECAO_ONDE_ESTA,
    SECAO_VOTACAO,
    DadosLacuna,
    DadosNoticia,
    DadosProposicao,
    DadosTramitacao,
    DadosVotacao,
    TRAMITACOES_NO_CORPO,
    criar_gerador,
)
from .models import GeracaoIA, GeracaoTrecho

TAMANHO_CONSULTA = 300
# Sem o modelo da busca (21.3): o campo modelo_embedding de geracao_ia diz que a busca foi so por palavras
SO_PALAVRAS = "nenhum (busca so por palavras)"


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
        cod_situacao=proposicao.cod_situacao,
        explicacao_situacao=SITUACOES.get(proposicao.cod_situacao),
    )


def _avisar_situacao_desconhecida(proposicao):
    """Decisao 25.13: codigo fora do dicionario mostra so o nome da Camara e avisa a equipe."""
    if situacao_conhecida(proposicao.cod_situacao, proposicao.situacao):
        return
    db.session.add(
        LogSistema(
            nivel="aviso",
            modulo="IA",
            acao="situacao_desconhecida",
            descricao=(
                f"Codigo de situacao {proposicao.cod_situacao} ({proposicao.situacao!r}) fora do dicionario "
                "de desperta/proposicoes/situacoes.py: a noticia mostra so o nome da Camara."
            ),
            entidade="proposicao",
            entidade_id=str(proposicao.id),
        )
    )


def _lacunas(fontes):
    """Decisao 25.13: so as falhas da Camara entram na secao; a pratica normal ja esta no resultado."""
    return [
        DadosLacuna(texto=lacuna.texto, provas=[prova.em_texto() for prova in lacuna.provas])
        for lacuna in lacunas_das_fontes(fontes)
        if lacuna.falha_da_camara
    ]


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


def chave_do_fato(entrada):
    """
    O que identifica o fato (25.16). A entrada gravada traz tambem a data da situacao da proposicao,
    que muda a cada passo do andamento: comparar a entrada inteira fazia a mesma votacao (ou a mesma
    proposicao nova) ser escrita de novo a cada passo. Votacao: o id da votacao; proposicao nova: o id
    da proposicao; mudanca de situacao: a proposicao e a data da situacao.
    entrada: o JSON (texto) ou o dict.
    """
    if isinstance(entrada, str):
        try:
            entrada = json.loads(entrada)
        except ValueError:
            return ("texto", entrada)
    caso = entrada.get("caso")
    if "ref" in entrada:
        # Geracao que falhou antes de ler o registro
        return (caso, "ref", str(entrada["ref"]))
    if caso == CASO_VOTACAO:
        return (caso, entrada.get("votacao_id"))
    if caso == "situacao":
        return (caso, entrada.get("proposicao_id"), entrada.get("data_status"))
    if caso == "nova":
        return (caso, entrada.get("proposicao_id"))
    # Relatorio, boletim e outros: a entrada inteira identifica
    return ("entrada", json.dumps(entrada, sort_keys=True))


def _geracao_existente(entrada):
    """Gerar de novo o mesmo fato nao duplica a noticia; so a rejeitada pode ser refeita."""
    chave = chave_do_fato(entrada)
    dados = json.loads(entrada)
    if "proposicao_id" not in dados:
        # Relatorio semanal e outros sem proposicao: a entrada inteira identifica o fato
        return db.session.scalar(
            db.select(GeracaoIA)
            .join(Noticia, Noticia.id == GeracaoIA.noticia_id)
            .where(GeracaoIA.entrada == entrada, GeracaoIA.status == "ok", Noticia.status != "rejeitada")
            .limit(1)
        )
    # A entrada e JSON com as chaves em ordem: "proposicao_id" vem sempre antes de "votacao_id"
    candidatas = db.session.scalars(
        db.select(GeracaoIA)
        .join(Noticia, Noticia.id == GeracaoIA.noticia_id)
        .where(
            GeracaoIA.entrada.like(f'%"proposicao_id": {dados["proposicao_id"]},%'),
            GeracaoIA.status == "ok",
            Noticia.status != "rejeitada",
        )
        .order_by(GeracaoIA.id)
    )
    return next((geracao for geracao in candidatas if chave_do_fato(geracao.entrada) == chave), None)


def _fontes(proposicao, votacao):
    """A primeira gera o link da fonte oficial."""
    fontes = []
    if votacao:
        fontes.append(("votacao", votacao.id))
    fontes.append(("proposicao", str(proposicao.id)))
    if votacao:
        fontes.append(("orgao", str(votacao.orgao_id)))
    return fontes


def _data_do_fato(caso, proposicao, votacao):
    if votacao is not None:
        return votacao.data
    if caso == "situacao" and proposicao.data_status is not None:
        return proposicao.data_status.date()
    return proposicao.data_apresentacao.date()


def _fato(caso, proposicao, votacao, texto, fontes):
    """Decisao 25.16: o fato novo como atualizacao da noticia viva (titulo, paragrafo e o placar ou a situacao)."""
    secoes = {secao["titulo"]: secao["texto"] for secao in secoes_do_corpo(texto.corpo)}
    detalhes = []
    if SECAO_VOTACAO in secoes:
        detalhes.append(secoes[SECAO_VOTACAO])
    if caso == "situacao" and SECAO_ONDE_ESTA in secoes:
        detalhes.append(secoes[SECAO_ONDE_ESTA].split("\n\n")[0])
    return viva.Fato(
        data=_data_do_fato(caso, proposicao, votacao),
        titulo=texto.titulo,
        resumo=texto.resumo,
        detalhes=detalhes,
        fontes=fontes,
    )


def _modelo_da_busca(modelo):
    """Decisao 25.10 e transparencia (22.5): o modelo que fez a busca de verdade, ou que foi so por palavras."""
    return modelo.nome if modelo is not None else SO_PALAVRAS


def _registrar_erro(caso, ref, consulta, entrada, gerador_nome, versao, erro, inicio, modelo_embedding):
    db.session.rollback()
    config = current_app.config
    geracao = GeracaoIA(
        modelo_geracao=gerador_nome,
        modelo_embedding=modelo_embedding,
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
    modelo e o de RAG_MODELO (25.10); None: sem ele (21.3), busca so por palavras. Devolve (geracao, nova).
    """
    config = current_app.config
    inicio = time.monotonic()
    consulta = f"{caso} {ref}"
    entrada = json.dumps({"caso": caso, "ref": str(ref)})
    nome = config["GERADOR"]
    versao = "desconhecida"
    try:
        # Primeiro os dados: assim todo erro seguinte grava a entrada completa, e a geracao
        # automatica reconhece o fato que ja deu erro (desperta/ia/automatico.py)
        proposicao, votacao = _ler_origem(caso, ref)
        consulta = f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano} {proposicao.ementa}"[
            :TAMANHO_CONSULTA
        ]
        entrada = _entrada(caso, proposicao, votacao)
        existente = _geracao_existente(entrada)
        if existente:
            return existente, False
        gerador = gerador or criar_gerador(config["GERADOR"])
        nome, versao = gerador.nome, gerador.versao_prompt

        # 25.2 e 25.6: o tema principal, ou o tema especial quando a Camara nao informou nenhum;
        # a falta de tema entra nas lacunas (25.13)
        cod_tema, _ = tema_da_noticia(proposicao.id)
        fontes = _fontes(proposicao, votacao)
        dados = DadosNoticia(
            caso=caso,
            proposicao=_dados_da_proposicao(proposicao),
            votacao=_dados_da_votacao(votacao) if votacao else None,
            tramitacoes=_tramitacoes(proposicao.id),
            lacunas=_lacunas(fontes),
            url_mais_informacoes=URL_FICHA.format(proposicao.id),
        )
        _avisar_situacao_desconhecida(proposicao)
        achados = services.buscar(modelo, consulta, modo="hibrida" if modelo else "palavras")
        texto = gerador.escrever(consulta, [achado.trecho.texto for achado in achados], dados)

        # 25.16: noticia viva; o fato entra na noticia aberta da proposicao, vira rascunho de
        # atualizacao da publicada, ou abre uma noticia nova
        noticia = viva.destino_do_fato(
            proposicao.id,
            _fato(caso, proposicao, votacao, texto, fontes),
            cod_tema,
            fontes,
            lambda: criar_rascunho(texto.titulo, texto.resumo, texto.corpo, cod_tema, fontes),
        )
        geracao = GeracaoIA(
            noticia_id=noticia.id,
            modelo_geracao=gerador.nome,
            modelo_embedding=_modelo_da_busca(modelo),
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
        return (
            _registrar_erro(caso, ref, consulta, entrada, nome, versao, erro, inicio, _modelo_da_busca(modelo)),
            True,
        )
