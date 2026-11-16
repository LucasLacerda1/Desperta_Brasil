"""
RF07 (decisao 25.5): relatorio da semana na Camara.

Montado so com o que esta no banco, com frases prontas, como o GeradorFrases: nenhum numero,
nome ou data e inventado. Nao usa a busca nem a rede neural. O relatorio entra como rascunho
do tipo "relatorio" e passa pela revisao da equipe, como toda noticia.
"""

import json
import time as relogio
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from flask import current_app

from desperta.ext.api import BRASILIA
from desperta.ext.db import db
from desperta.noticias.services import criar_rascunho
from desperta.proposicoes.models import Proposicao, Tema
from desperta.proposicoes.services import situacao_mudou, tema_principal
from desperta.sistema.models import LogSistema
from desperta.sistema.services import ultima_coleta_concluida
from desperta.votacoes.models import Votacao

from .geracao import ErroDeGeracao, _dados_da_votacao, _geracao_existente, _proposicao_da_votacao, _registrar_erro
from .gerador import (
    LIMITE_RESUMO,
    LIMITE_TITULO,
    SITUACOES_DE_AVANCO,
    VOTACAO_DE_MERITO,
    _cortar,
    _descricao_da_votacao,
    _frase,
    _limpar_ementa,
    _placar,
)
from .models import GeracaoIA

CASO = "relatorio_semanal"
GERADOR = "relatorio-semanal-v1"
# O relatorio nao usa a busca: o campo modelo_embedding de geracao_ia diz isso
SEM_BUSCA = "nenhum (relatorio sem busca)"
# Tema da noticia do relatorio: "Processo Legislativo e Atuacao Parlamentar", tema oficial da Camara
TEMA_DO_RELATORIO = 53
SIGLA_DO_PLENARIO = "PLEN"
ITENS_POR_GRUPO = 15
TEMAS_NO_RELATORIO = 5
EMENTA_NO_RELATORIO = 200
MESES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
# Ordem em que as situacoes de avanco aparecem; as que nao estao aqui vem depois, em ordem alfabetica
ORDEM_DOS_AVANCOS = (
    "aguardando sanção",
    "transformado em norma jurídica",
    "aguardando apreciação pelo senado federal",
    "aguardando redação final",
    "aguardando envio à redação final",
    "pronta para pauta",
)


# === VotacaoDaSemana (votacao de projeto no Plenario) ===
@dataclass
class VotacaoDaSemana:
    votacao_id: str
    identificacao: str
    data: date
    descricao: str
    placar: str
    ementa: str
    aprovacao: Optional[bool]


# === Avanco (proposicao que mudou para uma situacao de avanco) ===
@dataclass
class Avanco:
    proposicao_id: int
    identificacao: str
    situacao: str
    data: date
    ementa: str


# === DadosDaSemana (tudo o que o relatorio conta, ja lido do banco) ===
@dataclass
class DadosDaSemana:
    inicio: date
    fim: date
    votacoes_no_plenario: int = 0
    votacoes_em_comissoes: int = 0
    de_projetos: List[VotacaoDaSemana] = field(default_factory=list)
    avancos: Dict[str, List[Avanco]] = field(default_factory=dict)
    novas: Counter = field(default_factory=Counter)
    # A Camara demora a dar tema as proposicoes novas (23.2): quantas ja tem, e os temas mais comuns
    novas_com_tema: int = 0
    temas: List[Tuple[str, int]] = field(default_factory=list)
    ultima_coleta: Optional[datetime] = None

    def vazia(self):
        return not (self.votacoes_no_plenario or self.votacoes_em_comissoes or self.avancos or self.novas)


# ======================================================
# PERIODO
# ======================================================
def semana_ate(fim):
    """Os sete dias que terminam em fim."""
    return fim - timedelta(days=6), fim


def semana_passada(hoje=None):
    """Os sete dias que terminam ontem: a rotina semanal roda no domingo de madrugada."""
    return semana_ate((hoje or date.today()) - timedelta(days=1))


def periodo_em_texto(inicio, fim):
    if inicio.year != fim.year:
        return (
            f"{inicio.day} de {MESES[inicio.month - 1]} de {inicio.year} "
            f"a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
        )
    if inicio.month != fim.month:
        return f"{inicio.day} de {MESES[inicio.month - 1]} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
    return f"{inicio.day} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"


# ======================================================
# LEITURA DO BANCO
# ======================================================
def _identificacao(proposicao):
    return f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano}"


def _ementa(proposicao):
    return _cortar(_limpar_ementa(proposicao.ementa or ""), EMENTA_NO_RELATORIO)


def _votacoes(dados, tipos):
    votacoes = db.session.scalars(
        db.select(Votacao)
        .where(Votacao.data >= dados.inicio, Votacao.data <= dados.fim)
        .order_by(Votacao.data_hora_registro, Votacao.id)
    ).all()
    for votacao in votacoes:
        if votacao.sigla_orgao != SIGLA_DO_PLENARIO:
            dados.votacoes_em_comissoes += 1
            continue
        dados.votacoes_no_plenario += 1
        descricao = _descricao_da_votacao(votacao)
        # So aprovacao ou rejeicao de projeto, como no GeradorFrases; requerimento nao entra na lista
        if not VOTACAO_DE_MERITO.match(descricao):
            continue
        try:
            proposicao = _proposicao_da_votacao(votacao)
        except ErroDeGeracao:
            continue
        if proposicao.sigla_tipo not in tipos:
            continue
        dados.de_projetos.append(
            VotacaoDaSemana(
                votacao_id=votacao.id,
                identificacao=_identificacao(proposicao),
                data=votacao.data,
                descricao=descricao,
                placar=_placar(_dados_da_votacao(votacao)),
                ementa=_ementa(proposicao),
                aprovacao=votacao.aprovacao,
            )
        )


def _proposicoes(dados, tipos):
    inicio, fim = datetime.combine(dados.inicio, time.min), datetime.combine(dados.fim, time.max)
    novas = db.session.execute(
        db.select(Proposicao.id, Proposicao.sigla_tipo).where(
            Proposicao.sigla_tipo.in_(tipos), Proposicao.data_apresentacao.between(inicio, fim)
        )
    ).all()
    dados.novas = Counter(linha.sigla_tipo for linha in novas)
    por_tema = Counter(filter(None, (tema_principal(linha.id) for linha in novas)))
    dados.novas_com_tema = sum(por_tema.values())
    nomes = dict(db.session.execute(db.select(Tema.cod_tema, Tema.nome).where(Tema.cod_tema.in_(por_tema))).all())
    # Empate: ordem alfabetica, para o texto sair sempre igual
    ordenados = sorted(por_tema.items(), key=lambda item: (-item[1], nomes[item[0]]))
    dados.temas = [(nomes[cod_tema], total) for cod_tema, total in ordenados[:TEMAS_NO_RELATORIO]]

    mudaram = db.session.scalars(
        db.select(Proposicao)
        .where(Proposicao.sigla_tipo.in_(tipos), Proposicao.data_status.between(inicio, fim))
        .order_by(Proposicao.data_status.desc(), Proposicao.id)
    ).all()
    grupos = {}
    for proposicao in mudaram:
        situacao = (proposicao.situacao or "").strip()
        if situacao.lower() not in SITUACOES_DE_AVANCO:
            continue
        # Decisao 25.1: a data do status anda a cada passo; so conta se a situacao e outra
        if not situacao_mudou(proposicao.id, proposicao.cod_situacao, proposicao.data_status):
            continue
        grupos.setdefault(situacao, []).append(
            Avanco(
                proposicao_id=proposicao.id,
                identificacao=_identificacao(proposicao),
                situacao=situacao,
                data=proposicao.data_status.date(),
                ementa=_ementa(proposicao),
            )
        )

    def ordem(situacao):
        chave = situacao.lower()
        posicao = ORDEM_DOS_AVANCOS.index(chave) if chave in ORDEM_DOS_AVANCOS else len(ORDEM_DOS_AVANCOS)
        return posicao, chave

    dados.avancos = {situacao: grupos[situacao] for situacao in sorted(grupos, key=ordem)}


def ler_semana(inicio, fim):
    dados = DadosDaSemana(inicio=inicio, fim=fim, ultima_coleta=ultima_coleta_concluida())
    tipos = current_app.config["TIPOS_ACOMPANHADOS"]
    _votacoes(dados, tipos)
    _proposicoes(dados, tipos)
    return dados


# ======================================================
# TEXTO (FRASES PRONTAS)
# ======================================================
def _n(numero, singular, plural):
    return f"{numero:,}".replace(",", ".") + " " + (singular if numero == 1 else plural)


def _lista(partes):
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " e " + partes[-1]


def _novas_em_texto(novas):
    return _lista([f"{total} {sigla}" for sigla, total in sorted(novas.items(), key=lambda item: (-item[1], item[0]))])


def _abertura(dados):
    periodo = periodo_em_texto(dados.inicio, dados.fim)
    texto = (
        f"De {periodo}, a Câmara dos Deputados registrou "
        f"{_n(dados.votacoes_no_plenario, 'votação', 'votações')} no Plenário e "
        f"{_n(dados.votacoes_em_comissoes, 'votação', 'votações')} em comissões."
    )
    total = sum(dados.novas.values())
    if total:
        verbo = "Foi apresentada" if total == 1 else "Foram apresentadas"
        texto += (
            f" {verbo} {_n(total, 'proposição', 'proposições')} dos tipos que o portal acompanha: "
            f"{_novas_em_texto(dados.novas)}."
        )
    return texto


def _secao_de_votacoes(dados):
    if not dados.votacoes_no_plenario:
        return None
    outras = dados.votacoes_no_plenario - len(dados.de_projetos)
    if not dados.de_projetos:
        return (
            f"Votações de projetos no Plenário: nenhuma. "
            f"{'A votação' if outras == 1 else 'As ' + _n(outras, 'votação', 'votações')} do Plenário "
            f"{'foi' if outras == 1 else 'foram'} de requerimentos, redação final e outros procedimentos."
        )
    linhas = [f"Votações de projetos no Plenário ({len(dados.de_projetos)}):"]
    for item in dados.de_projetos:
        linha = f"- {item.identificacao}, em {item.data:%d/%m/%Y}: {_frase(item.descricao)} {item.placar}".strip()
        if item.ementa:
            linha += f" Ementa: {_frase(item.ementa)}"
        linhas.append(linha)
    if outras:
        linhas.append(
            f"{'A outra votação' if outras == 1 else 'As outras ' + _n(outras, 'votação', 'votações')} do Plenário "
            f"{'foi' if outras == 1 else 'foram'} de requerimentos, redação final e outros procedimentos."
        )
    return "\n".join(linhas)


def _secao_de_avancos(dados):
    if not dados.avancos:
        return None
    total = sum(len(grupo) for grupo in dados.avancos.values())
    linhas = [f"O que avançou ({_n(total, 'proposição', 'proposições')}):"]
    for situacao, grupo in dados.avancos.items():
        linhas.append(f'Situação "{situacao}" ({len(grupo)}):')
        for item in grupo[:ITENS_POR_GRUPO]:
            linha = f"- {item.identificacao}, em {item.data:%d/%m/%Y}"
            linhas.append(f"{linha}: {_frase(item.ementa)}" if item.ementa else f"{linha}.")
        resto = len(grupo) - ITENS_POR_GRUPO
        if resto > 0:
            linhas.append(f"- e mais {_n(resto, 'proposição', 'proposições')} nessa situação.")
    return "\n".join(linhas)


def _secao_de_temas(dados):
    if not dados.temas:
        return None
    total = sum(dados.novas.values())
    classificadas = (
        f"A Câmara já deu tema a {dados.novas_com_tema} das {_n(total, 'proposição nova', 'proposições novas')}. "
        if dados.novas_com_tema < total
        else ""
    )
    return f"{classificadas}Temas mais comuns entre elas: " + _lista([f"{n} ({t})" for n, t in dados.temas]) + "."


def _fecho(dados):
    if dados.ultima_coleta is None:
        ate = "com os dados guardados no banco do portal"
    else:
        momento = dados.ultima_coleta.replace(tzinfo=timezone.utc).astimezone(BRASILIA)
        ate = (
            f"com os dados que a Câmara publicou até {momento:%d/%m/%Y}, às {momento:%H}h{momento:%M} "
            "(última coleta concluída pelo portal)"
        )
    return (
        f"Como este relatório foi feito: montado automaticamente {ate}, "
        "só com os registros oficiais. Nenhum número, nome ou data foi escrito à mão."
    )


def _resumo(dados):
    periodo = periodo_em_texto(dados.inicio, dados.fim)
    frases = [
        f"De {periodo}, a Câmara fez {_n(dados.votacoes_no_plenario, 'votação', 'votações')} no Plenário "
        f"e {_n(dados.votacoes_em_comissoes, 'votação', 'votações')} em comissões."
    ]
    if dados.de_projetos:
        aprovados = sum(1 for item in dados.de_projetos if item.aprovacao)
        rejeitados = sum(1 for item in dados.de_projetos if item.aprovacao is False)
        aprovacao = _n(aprovados, "projeto foi aprovado", "projetos foram aprovados") if aprovados else None
        rejeicao = _n(rejeitados, "projeto foi rejeitado", "projetos foram rejeitados") if rejeitados else None
        if aprovacao and rejeicao:
            frases.append(f"No Plenário, {aprovacao} e {rejeicao}.")
        elif aprovacao or rejeicao:
            outro = "nenhum foi rejeitado" if aprovacao else "nenhum foi aprovado"
            frases.append(f"No Plenário, {aprovacao or rejeicao} e {outro}.")
    avancos = sum(len(grupo) for grupo in dados.avancos.values())
    if avancos:
        frases.append(
            f"{_n(avancos, 'proposição mudou', 'proposições mudaram')} para uma situação de avanço, "
            "como pauta do Plenário, Senado ou sanção."
        )
    novas = sum(dados.novas.values())
    if novas:
        frases.append(f"{_n(novas, 'proposição nova foi apresentada', 'proposições novas foram apresentadas')}.")
    return " ".join(frases)


def escrever(dados):
    """Devolve (titulo, resumo, corpo) do relatorio."""
    titulo = f"A semana na Câmara: {periodo_em_texto(dados.inicio, dados.fim)}"
    partes = [_abertura(dados), _secao_de_votacoes(dados), _secao_de_avancos(dados), _secao_de_temas(dados)]
    corpo = "\n\n".join([parte for parte in partes if parte] + [_fecho(dados)])
    return _cortar(titulo, LIMITE_TITULO), _cortar(_resumo(dados), LIMITE_RESUMO), corpo


# ======================================================
# GERACAO
# ======================================================
def _entrada(inicio, fim):
    return json.dumps({"caso": CASO, "inicio": inicio.isoformat(), "fim": fim.isoformat()}, sort_keys=True)


def _tema():
    """A noticia precisa de um tema (RF05): o relatorio fala do trabalho da Camara como um todo."""
    if db.session.get(Tema, TEMA_DO_RELATORIO) is None:
        raise ErroDeGeracao(f"O tema {TEMA_DO_RELATORIO} (Processo Legislativo) nao esta no banco.")
    return TEMA_DO_RELATORIO


def _fontes(dados):
    """Votacoes e proposicoes citadas pelo nome no texto; a primeira e a fonte principal."""
    fontes = [("votacao", item.votacao_id) for item in dados.de_projetos]
    for grupo in dados.avancos.values():
        fontes += [("proposicao", str(item.proposicao_id)) for item in grupo[:ITENS_POR_GRUPO]]
    return list(dict.fromkeys(fontes))


def previa(fim=None, hoje=None):
    """O relatorio da semana sem gravar nada: (dados, titulo, resumo, corpo)."""
    inicio, fim = semana_ate(fim) if fim else semana_passada(hoje)
    dados = ler_semana(inicio, fim)
    return (dados, *escrever(dados))


def gerar_relatorio_semanal(fim=None, hoje=None):
    """
    Grava o relatorio da semana como rascunho do tipo "relatorio" e registra a geracao_ia.
    Devolve (geracao, novo). A mesma semana nao gera dois relatorios (so se o primeiro foi
    rejeitado); semana sem nenhum movimento nao gera nada e devolve (None, False).
    """
    comeco = relogio.monotonic()
    inicio, fim = semana_ate(fim) if fim else semana_passada(hoje)
    consulta = f"relatorio semanal de {inicio.isoformat()} a {fim.isoformat()}"
    entrada = _entrada(inicio, fim)
    try:
        existente = _geracao_existente(entrada)
        if existente:
            return existente, False
        dados = ler_semana(inicio, fim)
        if dados.vazia():
            db.session.add(
                LogSistema(
                    nivel="info",
                    modulo="IA",
                    acao="relatorio_semanal",
                    descricao=f"Semana de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y} sem movimento: nada foi gerado.",
                )
            )
            db.session.commit()
            return None, False
        titulo, resumo, corpo = escrever(dados)
        noticia = criar_rascunho(titulo, resumo, corpo, _tema(), _fontes(dados))
        noticia.tipo = "relatorio"
        geracao = GeracaoIA(
            noticia_id=noticia.id,
            modelo_geracao=GERADOR,
            modelo_embedding=SEM_BUSCA,
            consulta=consulta,
            top_k=0,
            versao_prompt=GERADOR,
            entrada=entrada,
            tokens_entrada=0,
            tokens_saida=len(titulo.split()) + len(resumo.split()) + len(corpo.split()),
            duracao_ms=int((relogio.monotonic() - comeco) * 1000),
            status="ok",
        )
        db.session.add(geracao)
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="IA",
                acao="relatorio_semanal",
                descricao=(
                    f"Semana de {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}: {len(dados.de_projetos)} votacoes de projetos, "
                    f"{sum(len(g) for g in dados.avancos.values())} avancos, {sum(dados.novas.values())} novas"
                ),
                entidade="noticia",
                entidade_id=str(noticia.id),
            )
        )
        db.session.commit()
        return geracao, True
    except Exception as erro:
        return (
            _registrar_erro(CASO, f"{inicio}/{fim}", consulta, entrada, GERADOR, GERADOR, erro, comeco, SEM_BUSCA),
            False,
        )


def em_texto(geracao, novo):
    """Uma linha para o terminal e para o agendador.log."""
    if geracao is None:
        return "semana sem movimento, nada foi gerado"
    if geracao.status == "erro":
        return f"erro na geracao {geracao.id}: {geracao.erro}"
    if not novo:
        return f"a semana ja tem o rascunho {geracao.noticia.slug}"
    return f"rascunho {geracao.noticia.slug} (geracao {geracao.id})"
