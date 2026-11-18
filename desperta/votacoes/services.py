import re
from collections import Counter
from dataclasses import dataclass, field

from desperta.ext.api import iso_camara, url_camara
from desperta.ext.db import db
from desperta.ext.erros import NaoEncontrado
from desperta.parlamentares.models import Deputado
from desperta.proposicoes.models import Proposicao
from desperta.sistema.models import LogSistema

from .models import Orientacao, Votacao, VotacaoProposicao, Voto

# ----------------------------------------------------------
# Transparencia (05/11/2026): o portal diz por que uma votacao nao tem o voto de cada deputado.
# O banco guarda o que a API mandou; aqui o codigo classifica e explica.
# ----------------------------------------------------------
PENDENTE = "pendente"
ERRO_NA_COLETA = "erro_na_coleta"
# Decisao 25.13: os dados abertos nao dizem que a votacao foi secreta; dizem so que veio o placar
SO_PLACAR = "so_placar"
SIMBOLICA = "simbolica"
NOMINAL = "nominal"
INCONSISTENTE = "inconsistente"
SITUACOES_DOS_VOTOS = (PENDENTE, ERRO_NA_COLETA, SO_PLACAR, SIMBOLICA, NOMINAL, INCONSISTENTE)

PLACAR = re.compile(r"(Sim|Não|Abstenção|Obstrução|Total): (\d+)")
# Decisao tomada com os dados reais: "aprovada" quase sempre e requerimento ou redacao final, nao o projeto
VOTACAO_DE_MERITO = re.compile(
    r"^(?:Aprovad|Rejeitad)[oa] (?:o|a) (?:Projeto de|Proposta de Emenda|Medida Provis[oó]ria|Substitutivo)"
)
# Tabelas filhas da votacao que podem registrar erro no log
TABELAS_DA_VOTACAO = ("votacao", "voto", "orientacao", "votacao_proposicao")


@dataclass
class SituacaoDosVotos:
    codigo: str
    explicacao: str
    # Placar que a Camara escreve na descricao ("Sim: 404; Nao: 61...")
    placar_da_camara: dict = field(default_factory=dict)
    # Votos gravados no banco, por tipo; None conta os votos sem tipo
    votos: Counter = field(default_factory=Counter)


def placar_da_camara(descricao):
    return {tipo: int(valor) for tipo, valor in PLACAR.findall(descricao or "")}


def placar_em_frase(placar):
    """{"Sim": 404, "Nao": 61, "Abstencao": 1} -> "404 a favor, 61 contra e 1 abstenção"."""
    partes = []
    if "Sim" in placar:
        partes.append(f"{placar['Sim']} a favor")
    if "Não" in placar:
        partes.append(f"{placar['Não']} contra")
    for tipo, singular, plural in (("Abstenção", "abstenção", "abstenções"), ("Obstrução", "obstrução", "obstruções")):
        if placar.get(tipo):
            partes.append(f"{placar[tipo]} {singular if placar[tipo] == 1 else plural}")
    if len(partes) > 1:
        return ", ".join(partes[:-1]) + " e " + partes[-1]
    return partes[0] if partes else ""


def _teve_erro_na_coleta(id_votacao):
    return (
        db.session.scalar(
            db.select(LogSistema.id)
            .where(
                LogSistema.nivel == "erro",
                LogSistema.entidade.in_(TABELAS_DA_VOTACAO),
                db.or_(LogSistema.entidade_id == id_votacao, LogSistema.entidade_id.like(f"{id_votacao}/%")),
            )
            .limit(1)
        )
        is not None
    )


def e_votacao_de_merito(descricao):
    """A votacao decidiu o proprio projeto (aprovou ou rejeitou), e nao um requerimento ou um destaque."""
    return bool(VOTACAO_DE_MERITO.match((descricao or "").strip()))


def classificar_votos(votacao, votos):
    """
    So para votacao com os votos ja coletados (filhos_sincronizados_em preenchido):
    simbolica, so o placar, inconsistente ou nominal. votos: Counter por tipo (None = sem tipo).
    Separada da consulta para servir tambem ao calculo em lote (fila por prioridade, 25.15).
    """
    placar = placar_da_camara(votacao.descricao)
    total = sum(votos.values())
    if total == 0:
        return SituacaoDosVotos(
            SIMBOLICA, "Votação simbólica: a Câmara não registra o voto de cada deputado.", placar, votos
        )
    if votos[None] == total:
        # Decisao 25.13: o texto afirma so o que os dados abertos mostram, sem dizer por que
        frase = placar_em_frase(placar)
        if frase:
            explicacao = f"Os dados abertos da Câmara trazem só o placar total ({frase}), sem o voto de cada deputado."
        else:
            presencas = "1 presença" if total == 1 else f"{total} presenças"
            explicacao = (
                f"Os dados abertos da Câmara registram {presencas}, sem o voto de cada deputado e sem o placar."
            )
        return SituacaoDosVotos(SO_PLACAR, explicacao, placar, votos)
    if votos[None]:
        return SituacaoDosVotos(
            INCONSISTENTE,
            f"Dados incompletos da Câmara: {votos[None]} dos {total} votos vieram sem o tipo.",
            placar,
            votos,
        )
    return SituacaoDosVotos(NOMINAL, f"Votação nominal: {total} votos registrados.", placar, votos)


def contar_votos(votacao_ids):
    """{votacao_id: Counter por tipo} de varias votacoes numa consulta so."""
    contagem = {votacao_id: Counter() for votacao_id in votacao_ids}
    if not contagem:
        return contagem
    for votacao_id, tipo, total in db.session.execute(
        db.select(Voto.votacao_id, Voto.tipo_voto, db.func.count())
        .where(Voto.votacao_id.in_(list(contagem)))
        .group_by(Voto.votacao_id, Voto.tipo_voto)
    ):
        contagem[votacao_id][tipo] = total
    return contagem


def situacao_dos_votos(votacao):
    """Classifica os votos da votacao: pendente, erro na coleta, so o placar, simbolica, nominal ou inconsistente."""
    votos = contar_votos([votacao.id])[votacao.id]
    if votacao.filhos_sincronizados_em is None:
        placar = placar_da_camara(votacao.descricao)
        if _teve_erro_na_coleta(votacao.id):
            return SituacaoDosVotos(
                ERRO_NA_COLETA, "A coleta dos votos desta votação falhou e será repetida.", placar, votos
            )
        return SituacaoDosVotos(PENDENTE, "Os votos desta votação ainda estão sendo coletados.", placar, votos)
    return classificar_votos(votacao, votos)


# ======================================================
# PORTAL: PAGINA DA VOTACAO (RF09)
# ======================================================
# Decisao 10.1: orientacao de bloco nao e ligada ao bloco; na exibicao, tres grupos
LIDERANCAS_DE_GOVERNO = ("Governo", "Maioria", "Minoria", "Oposição")
SEM_VOTO_INFORMADO = "não informado pela Câmara"


def buscar_votacao(votacao_id):
    votacao = db.session.get(Votacao, votacao_id)
    if votacao is None:
        raise NaoEncontrado("Votacao nao encontrada.")
    return votacao


def _resultado(aprovacao):
    if aprovacao is None:
        return "resultado não informado pela Câmara"
    return "aprovada" if aprovacao else "rejeitada"


def orientacoes_em_grupos(votacao_id):
    grupos = {"partidos": [], "liderancas": [], "blocos": []}
    for o in db.session.scalars(
        db.select(Orientacao).filter_by(votacao_id=votacao_id).order_by(Orientacao.partido_bloco)
    ):
        item = {"nome": o.partido_bloco, "orientacao": o.orientacao.strip() or SEM_VOTO_INFORMADO}
        if o.tipo_lideranca == "P":
            item["partido_id"] = o.partido_id
            grupos["partidos"].append(item)
        elif o.partido_bloco in LIDERANCAS_DE_GOVERNO:
            grupos["liderancas"].append(item)
        else:
            grupos["blocos"].append(item)
    return grupos


def como_dict(votacao):
    """Resultado, situacao dos votos (22.5), voto de cada deputado e orientacoes (RF09)."""
    from desperta.sistema.lacunas import lacunas_da_votacao

    situacao = situacao_dos_votos(votacao)
    votos = db.session.execute(
        db.select(Voto, Deputado)
        .join(Deputado, Deputado.id == Voto.deputado_id)
        .where(Voto.votacao_id == votacao.id)
        .order_by(Deputado.nome)
    ).all()
    afetadas = db.session.scalars(
        db.select(Proposicao)
        .join(VotacaoProposicao, VotacaoProposicao.proposicao_id == Proposicao.id)
        .where(VotacaoProposicao.votacao_id == votacao.id)
        .order_by(Proposicao.id)
    ).all()

    def resumo(proposicao):
        return {
            "id": proposicao.id,
            "sigla": f"{proposicao.sigla_tipo} {proposicao.numero}/{proposicao.ano}",
            "ementa": proposicao.ementa,
        }

    objeto = db.session.get(Proposicao, votacao.proposicao_id) if votacao.proposicao_id else None
    return {
        "id": votacao.id,
        "data": iso_camara(votacao.data),
        "data_hora_registro": iso_camara(votacao.data_hora_registro),
        "orgao": {
            "id": votacao.orgao_id,
            "sigla": votacao.sigla_orgao.strip() or (votacao.orgao.nome if votacao.orgao else None),
        },
        "evento_id": votacao.evento_id,
        "descricao": votacao.descricao,
        "aprovacao": votacao.aprovacao,
        "resultado": _resultado(votacao.aprovacao),
        "proposicao": resumo(objeto) if objeto else None,
        "proposicoes_afetadas": [resumo(p) for p in afetadas],
        "situacao_dos_votos": {
            "codigo": situacao.codigo,
            "explicacao": situacao.explicacao,
            "placar_da_camara": situacao.placar_da_camara,
        },
        "total_por_tipo": {(tipo or SEM_VOTO_INFORMADO): total for tipo, total in situacao.votos.items()},
        "votos": [
            {
                "deputado_id": deputado.id,
                "nome": deputado.nome,
                "sigla_partido": voto.sigla_partido,
                "sigla_uf": deputado.sigla_uf,
                "url_foto": deputado.url_foto,
                "voto": voto.tipo_voto or SEM_VOTO_INFORMADO,
            }
            for voto, deputado in votos
        ],
        "orientacoes": orientacoes_em_grupos(votacao.id),
        # Decisao 25.13: o que a Camara nao informou, com prova (sem o nivel, que e interno)
        "lacunas": [lacuna.publica() for lacuna in lacunas_da_votacao(votacao)],
        "url_dados_abertos": url_camara(f"votacoes/{votacao.id}"),
    }
