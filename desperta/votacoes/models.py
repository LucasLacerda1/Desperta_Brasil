from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.orgaos.models import Evento, Orgao, PautaItem
    from desperta.parlamentares.models import Deputado, Partido
    from desperta.proposicoes.models import Proposicao

ORIENTACAO_TIPOS_LIDERANCA = ("P", "B")


# === Votacao (deliberacao em Plenario ou comissao) ===
class Votacao(db.Model):
    __tablename__ = "votacao"

    # ======================================================
    # IDENTIFICACAO (id da API em texto, ex.: "2310837-8")
    # ======================================================
    id: Mapped[str] = mapped_column(db.Text, primary_key=True)

    # ======================================================
    # DADOS DA VOTACAO
    # ======================================================
    data: Mapped[date] = mapped_column(db.Date, nullable=False, index=True)
    data_hora_registro: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    evento_id: Mapped[Optional[int]] = mapped_column(db.Integer, db.ForeignKey("evento.id"), nullable=True, index=True)
    orgao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("orgao.id"), nullable=False, index=True)
    sigla_orgao: Mapped[str] = mapped_column(db.Text, nullable=False)
    proposicao_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("proposicao.id"), nullable=True, index=True
    )
    descricao: Mapped[str] = mapped_column(db.Text, nullable=False)
    aprovacao: Mapped[Optional[bool]] = mapped_column(db.Boolean, nullable=True)

    # ------------------------------------------------------
    # EVENTO
    # ------------------------------------------------------
    evento: Mapped[Optional["Evento"]] = relationship(
        "Evento",
        back_populates="votacoes"
    )

    # ------------------------------------------------------
    # ORGAO
    # ------------------------------------------------------
    orgao: Mapped["Orgao"] = relationship(
        "Orgao",
        back_populates="votacoes"
    )

    # ------------------------------------------------------
    # PROPOSICOES
    # ------------------------------------------------------
    proposicao: Mapped[Optional["Proposicao"]] = relationship(
        "Proposicao",
        back_populates="votacoes"
    )

    proposicoes_afetadas: Mapped[List["VotacaoProposicao"]] = relationship(
        "VotacaoProposicao",
        back_populates="votacao",
        cascade="all, delete-orphan"
    )

    # ------------------------------------------------------
    # VOTOS
    # ------------------------------------------------------
    votos: Mapped[List["Voto"]] = relationship(
        "Voto",
        back_populates="votacao",
        cascade="all, delete-orphan"
    )

    # ------------------------------------------------------
    # ORIENTACOES
    # ------------------------------------------------------
    orientacoes: Mapped[List["Orientacao"]] = relationship(
        "Orientacao",
        back_populates="votacao",
        cascade="all, delete-orphan"
    )

    # ------------------------------------------------------
    # ITENS DE PAUTA
    # ------------------------------------------------------
    itens_pauta: Mapped[List["PautaItem"]] = relationship(
        "PautaItem",
        back_populates="votacao"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Votacao id='{self.id}' "
            f"data={self.data} aprovacao={self.aprovacao}>"
        )


# === Voto (voto nominal de cada deputado) ===
class Voto(db.Model):
    __tablename__ = "voto"

    votacao_id: Mapped[str] = mapped_column(db.Text, db.ForeignKey("votacao.id"), primary_key=True)
    deputado_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("deputado.id"), primary_key=True)
    # Sim, Nao, Abstencao, Obstrucao...
    tipo_voto: Mapped[str] = mapped_column(db.Text, nullable=False)
    data_registro: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    # Partido no dia do voto (D4)
    sigla_partido: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # VOTACAO
    # ------------------------------------------------------
    votacao: Mapped["Votacao"] = relationship(
        "Votacao",
        back_populates="votos"
    )

    # ------------------------------------------------------
    # DEPUTADO
    # ------------------------------------------------------
    deputado: Mapped["Deputado"] = relationship(
        "Deputado",
        back_populates="votos"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Voto votacao_id='{self.votacao_id}' "
            f"deputado_id={self.deputado_id} tipo_voto='{self.tipo_voto}'>"
        )


# === Orientacao (orientacao de partido ou bloco, so no Plenario) ===
class Orientacao(db.Model):
    __tablename__ = "orientacao"
    __table_args__ = (
        db.CheckConstraint(f"tipo_lideranca IN {ORIENTACAO_TIPOS_LIDERANCA}", name="ck_orientacao_tipo_lideranca"),
    )

    votacao_id: Mapped[str] = mapped_column(db.Text, db.ForeignKey("votacao.id"), primary_key=True)
    partido_bloco: Mapped[str] = mapped_column(db.Text, primary_key=True)
    # P (partido) ou B (bloco)
    tipo_lideranca: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Bloco nao tem id
    partido_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("partido.id"), nullable=True, index=True
    )
    orientacao: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # VOTACAO
    # ------------------------------------------------------
    votacao: Mapped["Votacao"] = relationship(
        "Votacao",
        back_populates="orientacoes"
    )

    # ------------------------------------------------------
    # PARTIDO
    # ------------------------------------------------------
    partido: Mapped[Optional["Partido"]] = relationship(
        "Partido",
        back_populates="orientacoes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Orientacao votacao_id='{self.votacao_id}' "
            f"partido_bloco='{self.partido_bloco}' orientacao='{self.orientacao}'>"
        )


# === VotacaoProposicao (proposicoes afetadas pela votacao) ===
class VotacaoProposicao(db.Model):
    __tablename__ = "votacao_proposicao"

    votacao_id: Mapped[str] = mapped_column(db.Text, db.ForeignKey("votacao.id"), primary_key=True)
    proposicao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("proposicao.id"), primary_key=True)

    # ------------------------------------------------------
    # VOTACAO
    # ------------------------------------------------------
    votacao: Mapped["Votacao"] = relationship(
        "Votacao",
        back_populates="proposicoes_afetadas"
    )

    # ------------------------------------------------------
    # PROPOSICAO
    # ------------------------------------------------------
    proposicao: Mapped["Proposicao"] = relationship(
        "Proposicao",
        back_populates="votacoes_afetadas"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<VotacaoProposicao votacao_id='{self.votacao_id}' "
            f"proposicao_id={self.proposicao_id}>"
        )
