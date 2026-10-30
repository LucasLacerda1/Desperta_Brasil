from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.parlamentares.models import Deputado
    from desperta.proposicoes.models import Proposicao, Tramitacao
    from desperta.votacoes.models import Votacao


# === Orgao (Plenario, comissoes, Mesa Diretora) ===
class Orgao(db.Model):
    __tablename__ = "orgao"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    sigla: Mapped[str] = mapped_column(db.Text, nullable=False)
    nome: Mapped[str] = mapped_column(db.Text, nullable=False)
    apelido: Mapped[str] = mapped_column(db.Text, nullable=False)
    cod_tipo_orgao: Mapped[int] = mapped_column(db.Integer, nullable=False)
    tipo_orgao: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # TRAMITACOES
    # ------------------------------------------------------
    tramitacoes: Mapped[List["Tramitacao"]] = relationship(
        "Tramitacao",
        back_populates="orgao"
    )

    # ------------------------------------------------------
    # EVENTOS
    # ------------------------------------------------------
    eventos: Mapped[List["Evento"]] = relationship(
        "Evento",
        back_populates="orgao"
    )

    # ------------------------------------------------------
    # VOTACOES
    # ------------------------------------------------------
    votacoes: Mapped[List["Votacao"]] = relationship(
        "Votacao",
        back_populates="orgao"
    )

    # ------------------------------------------------------
    # MEMBROS
    # ------------------------------------------------------
    membros: Mapped[List["DeputadoOrgao"]] = relationship(
        "DeputadoOrgao",
        back_populates="orgao"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Orgao id={self.id} "
            f"sigla='{self.sigla}'>"
        )


# === DeputadoOrgao (cargos de deputados em orgaos) ===
class DeputadoOrgao(db.Model):
    __tablename__ = "deputado_orgao"

    deputado_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("deputado.id"), primary_key=True)
    orgao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("orgao.id"), primary_key=True)
    data_inicio: Mapped[date] = mapped_column(db.Date, primary_key=True)
    # Numero ou texto na API: gravar como texto
    cod_titulo: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Presidente, Titular, Suplente...
    titulo: Mapped[str] = mapped_column(db.Text, nullable=False)
    data_fim: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)

    # ------------------------------------------------------
    # DEPUTADO
    # ------------------------------------------------------
    deputado: Mapped["Deputado"] = relationship(
        "Deputado",
        back_populates="cargos"
    )

    # ------------------------------------------------------
    # ORGAO
    # ------------------------------------------------------
    orgao: Mapped["Orgao"] = relationship(
        "Orgao",
        back_populates="membros"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<DeputadoOrgao deputado_id={self.deputado_id} "
            f"orgao_id={self.orgao_id} titulo='{self.titulo}'>"
        )


# === Evento (sessao ou reuniao) ===
class Evento(db.Model):
    __tablename__ = "evento"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    data_hora_inicio: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, index=True)
    data_hora_fim: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)
    situacao: Mapped[str] = mapped_column(db.Text, nullable=False)
    descricao_tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    descricao: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Primeiro orgao da lista da API (D1)
    orgao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("orgao.id"), nullable=False, index=True)
    local: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    url_registro: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    url_documento_pauta: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)

    # ------------------------------------------------------
    # ORGAO
    # ------------------------------------------------------
    orgao: Mapped["Orgao"] = relationship(
        "Orgao",
        back_populates="eventos"
    )

    # ------------------------------------------------------
    # VOTACOES
    # ------------------------------------------------------
    votacoes: Mapped[List["Votacao"]] = relationship(
        "Votacao",
        back_populates="evento"
    )

    # ------------------------------------------------------
    # PAUTA
    # ------------------------------------------------------
    pauta: Mapped[List["PautaItem"]] = relationship(
        "PautaItem",
        back_populates="evento",
        cascade="all, delete-orphan",
        order_by="PautaItem.ordem"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Evento id={self.id} "
            f"inicio={self.data_hora_inicio} situacao='{self.situacao}'>"
        )


# === PautaItem (item da pauta de um evento) ===
class PautaItem(db.Model):
    __tablename__ = "pauta_item"

    evento_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("evento.id"), primary_key=True)
    ordem: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    proposicao_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("proposicao.id"), nullable=True, index=True
    )
    # Sem FK: a proposicao relacionada pode nao estar no banco
    proposicao_relacionada_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    relator_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("deputado.id"), nullable=True, index=True
    )
    regime: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    situacao_item: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    topico: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    texto_parecer: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    votacao_id: Mapped[Optional[str]] = mapped_column(db.Text, db.ForeignKey("votacao.id"), nullable=True, index=True)

    # ------------------------------------------------------
    # EVENTO
    # ------------------------------------------------------
    evento: Mapped["Evento"] = relationship(
        "Evento",
        back_populates="pauta"
    )

    # ------------------------------------------------------
    # PROPOSICAO
    # ------------------------------------------------------
    proposicao: Mapped[Optional["Proposicao"]] = relationship(
        "Proposicao",
        back_populates="pautas"
    )

    # ------------------------------------------------------
    # RELATOR
    # ------------------------------------------------------
    relator: Mapped[Optional["Deputado"]] = relationship(
        "Deputado",
        back_populates="relatorias",
        foreign_keys=[relator_id]
    )

    # ------------------------------------------------------
    # VOTACAO
    # ------------------------------------------------------
    votacao: Mapped[Optional["Votacao"]] = relationship(
        "Votacao",
        back_populates="itens_pauta"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<PautaItem evento_id={self.evento_id} "
            f"ordem={self.ordem}>"
        )
