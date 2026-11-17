"""
Boletins do dia (decisao 25.13, item 4; registro em 25.17).

Os fatos pequenos (votacao de procedimento no Plenario, votacoes em comissao, passo de situacao
que nao e marco e proposicao nova de tipo menor, como o PDL) deixam de virar uma noticia cada um:
entram no boletim do dia, um por tipo de fato, cada fato com o seu link. Escolhas do Lucas (17/11):
- se a proposicao do fato pequeno ja tem noticia viva, o fato tambem entra nela como atualizacao;
- os boletins sao divididos por tipo de fato: Plenario, comissoes, andamento e proposicoes novas.
Nenhum fato se perde: o fato grande continua virando noticia propria, e na duvida tambem.
O boletim entra como rascunho do tipo "relatorio" e passa pela revisao, como toda noticia.
"""

import json
import time as relogio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from flask import current_app

from desperta.ext.api import BRASILIA
from desperta.ext.db import db
from desperta.noticias.services import criar_rascunho
from desperta.proposicoes.models import Proposicao
from desperta.proposicoes.services import URL_PAGINA, situacao_mudou
from desperta.proposicoes.situacoes import MARCOS, SITUACOES, situacao_informada
from desperta.sistema.models import LogSistema
from desperta.sistema.services import ultima_coleta_concluida
from desperta.votacoes.models import Votacao
from desperta.votacoes.services import e_votacao_de_merito

from .geracao import ErroDeGeracao, _dados_da_votacao, _geracao_existente, _proposicao_da_votacao, _registrar_erro
from .gerador import (
    CASO_NOVA,
    CASO_SITUACAO,
    CASO_VOTACAO,
    LIMITE_RESUMO,
    LIMITE_TITULO,
    _cortar,
    _descricao_da_votacao,
    _frase,
    _limpar_ementa,
    _placar,
)
from .models import GeracaoIA

CASO = "boletim"
GERADOR = "boletim-v1"
SEM_BUSCA = "nenhum (relatorio sem busca)"
TEMA_DO_BOLETIM = 53  # Processo Legislativo e Atuacao Parlamentar, como o relatorio semanal
EMENTA_NO_BOLETIM = 160
EXPLICACAO_SIMBOLICA = (
    "Votação simbólica: a Câmara não registra o voto de cada deputado; o resultado é anunciado "
    "por quem preside a sessão."
)
SIGLA_DO_PLENARIO = "PLEN"

PROPRIA = "propria"
BOLETIM = "boletim"

# Categoria: titulo do boletim (a ordem e a da geracao)
PLENARIO = "plenario"
COMISSOES = "comissoes"
ANDAMENTO = "andamento"
NOVAS = "novas"
CATEGORIAS = {
    PLENARIO: "votações de procedimento no Plenário",
    COMISSOES: "votações nas comissões",
    ANDAMENTO: "andamento das proposições",
    NOVAS: "proposições novas",
}
# Proposicao nova que vira noticia propria; as outras (PDL) vao para o boletim
NOVAS_DE_PESO = ("PEC", "MPV", "PL", "PLP")


# ======================================================
# CLASSIFICACAO: NOTICIA PROPRIA OU BOLETIM
# ======================================================
@dataclass
class Classificacao:
    destino: str
    categoria: Optional[str]
    motivo: str


def _falha_grave(proposicao, votacao):
    """Decisao 25.13: lacuna de nivel 1 ou 2 (contradicao ou ocultacao) sempre vira noticia propria."""
    from desperta.sistema.lacunas import CONTRADICAO, OCULTACAO, lacunas_da_proposicao, lacunas_da_votacao

    lacunas = lacunas_da_proposicao(proposicao)
    if votacao is not None:
        lacunas += lacunas_da_votacao(votacao, proposicao.id)
    graves = [lacuna.codigo for lacuna in lacunas if lacuna.nivel in (CONTRADICAO, OCULTACAO)]
    return graves[0] if graves else None


def classificar(caso, proposicao, votacao=None):
    """
    Regra provisoria ate o filtro calibrado (item 6): pelo codigo da Camara sempre que da.
    Na duvida, noticia propria, com aviso no log: o erro possivel e uma noticia a mais, nunca um fato escondido.
    """
    grave = _falha_grave(proposicao, votacao)
    if grave:
        return Classificacao(PROPRIA, None, f"falha grave nos dados da Câmara: {grave}")
    if caso == CASO_VOTACAO and votacao is not None:
        if votacao.sigla_orgao == SIGLA_DO_PLENARIO:
            if e_votacao_de_merito(votacao.descricao):
                return Classificacao(PROPRIA, None, "votação do próprio projeto no Plenário")
            return Classificacao(BOLETIM, PLENARIO, "votação de procedimento no Plenário")
        return Classificacao(BOLETIM, COMISSOES, "votação em comissão")
    if caso == CASO_SITUACAO:
        if not situacao_informada(proposicao.cod_situacao, proposicao.situacao):
            return Classificacao(BOLETIM, ANDAMENTO, "passo do andamento sem situação informada")
        if proposicao.cod_situacao in MARCOS:
            return Classificacao(PROPRIA, None, "marco de situação")
        if proposicao.cod_situacao in SITUACOES:
            return Classificacao(BOLETIM, ANDAMENTO, "mudança de situação que não é marco")
    if caso == CASO_NOVA:
        if proposicao.sigla_tipo in NOVAS_DE_PESO:
            return Classificacao(PROPRIA, None, f"{proposicao.sigla_tipo} novo")
        return Classificacao(BOLETIM, NOVAS, f"{proposicao.sigla_tipo} novo")
    db.session.add(
        LogSistema(
            nivel="aviso",
            modulo="IA",
            acao="classificacao_desconhecida",
            descricao=(
                f"Fato {caso} da proposicao {proposicao.id} (situacao {proposicao.cod_situacao}) sem regra: "
                "vira noticia propria."
            ),
            entidade="proposicao",
            entidade_id=str(proposicao.id),
        )
    )
    return Classificacao(PROPRIA, None, "sem regra (seguro na dúvida)")


def tem_noticia_viva(proposicao_id):
    """A proposicao ja tem noticia da IA aberta ou publicada (25.16)."""
    from desperta.noticias import viva

    return viva.aberta_da_proposicao(proposicao_id) is not None or (
        viva.publicada_da_proposicao(proposicao_id) is not None
    )


# ======================================================
# FATOS DE UM DIA
# ======================================================
@dataclass
class Item:
    proposicao_id: int
    # A linha do boletim, sem o marcador e sem o link
    texto: str
    fonte: Tuple[str, str]
    # Grupo dentro do boletim: o orgao, a situacao ou o tipo
    grupo: str = ""
    explicacao: Optional[str] = None


@dataclass
class DadosDoDia:
    dia: date
    itens: Dict[str, List[Item]] = field(default_factory=dict)
    ultima_coleta: Optional[datetime] = None

    def total(self):
        return sum(len(lista) for lista in self.itens.values())


def _identificacao(proposicao):
    return f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano}"


def _ementa(proposicao):
    return _cortar(_limpar_ementa(proposicao.ementa or ""), EMENTA_NO_BOLETIM)


def _nome_do_orgao(votacao):
    """Nome da comissao com a sigla, que sozinha o leitor nao conhece (decisao 14.1: sigla vazia mostra o nome)."""
    sigla = (votacao.sigla_orgao or "").strip()
    nome = (votacao.orgao.nome or "").strip() if votacao.orgao else ""
    if nome and sigla:
        return f"{nome} ({sigla})"
    return nome or sigla or "órgão não informado"


def _item_da_votacao(votacao, proposicao, categoria):
    resultado = {True: "aprovado", False: "rejeitado", None: "resultado não informado pela Câmara"}[votacao.aprovacao]
    dados_da_votacao = _dados_da_votacao(votacao)
    # A explicacao da votacao simbolica vem uma vez so, no comeco do boletim
    placar = "Votação simbólica." if dados_da_votacao.situacao == "simbolica" else _placar(dados_da_votacao)
    texto = (
        f"{_identificacao(proposicao)} ({_ementa(proposicao)}): {_frase(_descricao_da_votacao(votacao))} "
        f"Resultado: {resultado}." + (f" {placar}" if placar else "")
    )
    return Item(
        proposicao_id=proposicao.id,
        texto=texto,
        fonte=("votacao", votacao.id),
        grupo=_nome_do_orgao(votacao) if categoria == COMISSOES else "",
    )


def ler_dia(dia, tipos=None):
    """Os fatos pequenos do dia, por categoria (mesmos fatos que o gerar-novos considera, 23.2 e 25.1)."""
    tipos = tipos or current_app.config["TIPOS_ACOMPANHADOS"]
    dados = DadosDoDia(dia=dia, itens={categoria: [] for categoria in CATEGORIAS})
    inicio, fim = datetime.combine(dia, datetime.min.time()), datetime.combine(
        dia + timedelta(days=1), datetime.min.time()
    )

    for votacao in db.session.scalars(
        db.select(Votacao).where(Votacao.data == dia).order_by(Votacao.data_hora_registro, Votacao.id)
    ):
        try:
            proposicao = _proposicao_da_votacao(votacao)
        except ErroDeGeracao:
            continue
        if proposicao.sigla_tipo not in tipos:
            continue
        classificacao = classificar(CASO_VOTACAO, proposicao, votacao)
        if classificacao.destino == BOLETIM:
            dados.itens[classificacao.categoria].append(_item_da_votacao(votacao, proposicao, classificacao.categoria))

    for proposicao in db.session.scalars(
        db.select(Proposicao)
        .where(Proposicao.sigla_tipo.in_(tipos), Proposicao.data_status >= inicio, Proposicao.data_status < fim)
        .order_by(Proposicao.data_status, Proposicao.id)
    ):
        if proposicao.data_status.date() <= proposicao.data_apresentacao.date():
            continue
        if not situacao_mudou(proposicao.id, proposicao.cod_situacao, proposicao.data_status):
            continue
        classificacao = classificar(CASO_SITUACAO, proposicao)
        if classificacao.destino != BOLETIM:
            continue
        informada = situacao_informada(proposicao.cod_situacao, proposicao.situacao)
        dados.itens[ANDAMENTO].append(
            Item(
                proposicao_id=proposicao.id,
                texto=f"{_identificacao(proposicao)}: {_ementa(proposicao)}",
                fonte=("proposicao", str(proposicao.id)),
                grupo=proposicao.situacao.strip() if informada else "Situação não informada pela Câmara",
                explicacao=SITUACOES.get(proposicao.cod_situacao) if informada else None,
            )
        )

    for proposicao in db.session.scalars(
        db.select(Proposicao)
        .where(
            Proposicao.sigla_tipo.in_(tipos),
            Proposicao.data_apresentacao >= inicio,
            Proposicao.data_apresentacao < fim,
        )
        .order_by(Proposicao.data_apresentacao, Proposicao.id)
    ):
        classificacao = classificar(CASO_NOVA, proposicao)
        if classificacao.destino != BOLETIM:
            continue
        autores = sorted(proposicao.autores, key=lambda autor: autor.ordem)
        autoria = ""
        if autores:
            autoria = f", de {autores[0].nome}" + (" e outros" if len(autores) > 1 else "")
        dados.itens[NOVAS].append(
            Item(
                proposicao_id=proposicao.id,
                texto=f"{_identificacao(proposicao)}{autoria}: {_ementa(proposicao)}",
                fonte=("proposicao", str(proposicao.id)),
                grupo=proposicao.sigla_tipo,
            )
        )
    dados.ultima_coleta = ultima_coleta_concluida()
    return dados


# ======================================================
# TEXTO
# ======================================================
def _n(numero, singular, plural):
    return f"{numero} {singular if numero == 1 else plural}"


def _linha(item):
    """Cada fato com o seu link: a pagina da proposicao no site da Camara."""
    return f"- {item.texto} {URL_PAGINA.format(item.proposicao_id)}"


def _por_grupo(itens):
    grupos = {}
    for item in itens:
        grupos.setdefault(item.grupo, []).append(item)
    return grupos


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
        f"Como este boletim foi feito: montado automaticamente {ate}, só com os registros oficiais. "
        "Nenhum número, nome ou data foi escrito à mão. Os fatos mais importantes do dia têm notícia própria."
    )


def _resumo(categoria, dia, itens):
    data = f"{dia:%d/%m/%Y}"
    if categoria == PLENARIO:
        return (
            f"Em {data}, o Plenário da Câmara fez {_n(len(itens), 'votação', 'votações')} de procedimento "
            f"(requerimentos, destaques, urgências e outras) sobre "
            f"{_n(len({i.proposicao_id for i in itens}), 'proposição', 'proposições')}."
        )
    if categoria == COMISSOES:
        orgaos = len({item.grupo for item in itens})
        return (
            f"Em {data}, as comissões da Câmara registraram {_n(len(itens), 'votação', 'votações')} "
            f"em {_n(orgaos, 'comissão', 'comissões')}."
        )
    if categoria == ANDAMENTO:
        return f"Em {data}, {_n(len(itens), 'proposição mudou', 'proposições mudaram')} de situação na Câmara."
    return f"Em {data}, {_n(len(itens), 'proposição foi apresentada', 'proposições foram apresentadas')} na Câmara."


def escrever(categoria, dados):
    """(titulo, resumo, corpo) do boletim de uma categoria."""
    itens = dados.itens[categoria]
    titulo = f"Boletim de {dados.dia:%d/%m/%Y}: {CATEGORIAS[categoria]}"
    partes = []
    if categoria in (PLENARIO, COMISSOES) and any("Votação simbólica." in item.texto for item in itens):
        partes.append(EXPLICACAO_SIMBOLICA)
    if categoria == PLENARIO:
        partes.append("## Votações\n\n" + "\n".join(_linha(item) for item in itens))
    else:
        for grupo, lista in sorted(_por_grupo(itens).items()):
            explicacao = next((item.explicacao for item in lista if item.explicacao), None)
            cabecalho = f"## {grupo}" + (f"\n\n{explicacao}" if explicacao else "")
            partes.append(cabecalho + "\n\n" + "\n".join(_linha(item) for item in lista))
    corpo = "\n\n".join(partes + [_fecho(dados)])
    return _cortar(titulo, LIMITE_TITULO), _cortar(_resumo(categoria, dados.dia, itens), LIMITE_RESUMO), corpo


# ======================================================
# GERACAO
# ======================================================
def _entrada(dia, categoria):
    return json.dumps({"caso": CASO, "categoria": categoria, "dia": dia.isoformat()}, sort_keys=True)


def _tema():
    from desperta.proposicoes.models import Tema

    if db.session.get(Tema, TEMA_DO_BOLETIM) is None:
        raise ErroDeGeracao(f"O tema {TEMA_DO_BOLETIM} (Processo Legislativo) nao esta no banco.")
    return TEMA_DO_BOLETIM


def gerar_boletins(dia=None, hoje=None, simular=False):
    """
    Os boletins de um dia (padrao: ontem), um por categoria com fatos. O mesmo dia e a mesma
    categoria nao geram dois boletins (so se o primeiro foi rejeitado). Devolve [(categoria, geracao, novo)];
    na simulacao, [(categoria, numero de fatos, None)].
    """
    dia = dia or (hoje or date.today()) - timedelta(days=1)
    dados = ler_dia(dia)
    resultado = []
    for categoria, itens in dados.itens.items():
        if not itens:
            continue
        if simular:
            resultado.append((categoria, len(itens), None))
            continue
        comeco = relogio.monotonic()
        entrada = _entrada(dia, categoria)
        consulta = f"boletim de {dia.isoformat()}: {categoria}"
        try:
            existente = _geracao_existente(entrada)
            if existente:
                resultado.append((categoria, existente, False))
                continue
            titulo, resumo, corpo = escrever(categoria, dados)
            fontes = list(dict.fromkeys(item.fonte for item in itens))
            noticia = criar_rascunho(titulo, resumo, corpo, _tema(), fontes)
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
                    acao="boletim",
                    descricao=f"Boletim de {dia:%d/%m/%Y} ({categoria}): {len(itens)} fatos",
                    entidade="noticia",
                    entidade_id=str(noticia.id),
                )
            )
            db.session.commit()
            resultado.append((categoria, geracao, True))
        except Exception as erro:
            geracao = _registrar_erro(CASO, consulta, consulta, entrada, GERADOR, GERADOR, erro, comeco, SEM_BUSCA)
            resultado.append((categoria, geracao, False))
    return resultado


def em_texto(dia, resultado):
    if not resultado:
        return f"{dia:%d/%m/%Y}: nenhum fato pequeno, nenhum boletim"
    partes = []
    for categoria, geracao, novo in resultado:
        if novo is None:
            partes.append(f"{categoria}={geracao} fatos")
        elif geracao.status != "ok":
            partes.append(f"{categoria}=erro ({geracao.erro})")
        else:
            partes.append(f"{categoria}={'novo' if novo else 'ja existia'} (noticia {geracao.noticia_id})")
    return f"{dia:%d/%m/%Y}: " + ", ".join(partes)
