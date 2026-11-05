import re
from collections import Counter
from dataclasses import dataclass, field

from desperta.ext.db import db
from desperta.sistema.models import LogSistema

from .models import Voto

# ----------------------------------------------------------
# Transparencia (05/11/2026): o portal diz por que uma votacao nao tem o voto de cada deputado.
# O banco guarda o que a API mandou; aqui o codigo classifica e explica.
# ----------------------------------------------------------
PENDENTE = "pendente"
ERRO_NA_COLETA = "erro_na_coleta"
SECRETA = "secreta"
SIMBOLICA = "simbolica"
NOMINAL = "nominal"
INCONSISTENTE = "inconsistente"
SITUACOES_DOS_VOTOS = (PENDENTE, ERRO_NA_COLETA, SECRETA, SIMBOLICA, NOMINAL, INCONSISTENTE)

PLACAR = re.compile(r"(Sim|Não|Abstenção|Obstrução|Total): (\d+)")
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


def situacao_dos_votos(votacao):
    """Classifica os votos da votacao: pendente, erro na coleta, secreta, simbolica, nominal ou inconsistente."""
    votos = Counter(
        dict(
            db.session.execute(
                db.select(Voto.tipo_voto, db.func.count()).filter_by(votacao_id=votacao.id).group_by(Voto.tipo_voto)
            ).all()
        )
    )
    placar = placar_da_camara(votacao.descricao)
    total = sum(votos.values())
    if votacao.filhos_sincronizados_em is None:
        if _teve_erro_na_coleta(votacao.id):
            return SituacaoDosVotos(
                ERRO_NA_COLETA, "A coleta dos votos desta votação falhou e será repetida.", placar, votos
            )
        return SituacaoDosVotos(PENDENTE, "Os votos desta votação ainda estão sendo coletados.", placar, votos)
    if total == 0:
        return SituacaoDosVotos(
            SIMBOLICA, "Votação simbólica: a Câmara não registra o voto de cada deputado.", placar, votos
        )
    if votos[None] == total:
        explicacao = "Votação secreta: a Câmara divulgou só o placar total"
        frase = placar_em_frase(placar)
        explicacao += f" ({frase})." if frase else "."
        return SituacaoDosVotos(SECRETA, explicacao, placar, votos)
    if votos[None]:
        return SituacaoDosVotos(
            INCONSISTENTE,
            f"Dados incompletos da Câmara: {votos[None]} dos {total} votos vieram sem o tipo.",
            placar,
            votos,
        )
    return SituacaoDosVotos(NOMINAL, f"Votação nominal: {total} votos registrados.", placar, votos)
