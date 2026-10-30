from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.noticias.models import Noticia
    from desperta.orgaos.models import Orgao, PautaItem
    from desperta.parlamentares.models import Deputado
    from desperta.visitantes.models import VisitanteTema
    from desperta.votacoes.models import Votacao, VotacaoProposicao


# === Proposicao (projeto de lei, PEC ou outra proposta) ===
class Proposicao(db.Model):
    __tablename__ = "proposicao"

    # ======================================================
    # IDENTIFICACAO (mesmo id da API da Camara)
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    sigla_tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    cod_tipo: Mapped[int] = mapped_column(db.Integer, nullable=False)
    descricao_tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    numero: Mapped[int] = mapped_column(db.Integer, nullable=False)
    ano: Mapped[int] = mapped_column(db.Integer, nullable=False, index=True)

    # ======================================================
    # CONTEUDO
    # ======================================================
    ementa: Mapped[str] = mapped_column(db.Text, nullable=False)
    ementa_detalhada: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    data_apresentacao: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, index=True)
    url_inteiro_teor: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ======================================================
    # SITUACAO ATUAL (statusProposicao)
    # ======================================================
    cod_situacao: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    situacao: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    data_status: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    regime: Mapped[str] = mapped_column(db.Text, nullable=False)
    apreciacao: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # AUTORES
    # ------------------------------------------------------
    autores: Mapped[List["ProposicaoAutor"]] = relationship(
        "ProposicaoAutor",
        back_populates="proposicao",
        cascade="all, delete-orphan",
        order_by="ProposicaoAutor.ordem"
    )

    # ------------------------------------------------------
    # TRAMITACOES
    # ------------------------------------------------------
    tramitacoes: Mapped[List["Tramitacao"]] = relationship(
        "Tramitacao",
        back_populates="proposicao",
        cascade="all, delete-orphan",
        order_by="Tramitacao.sequencia"
    )

    # ------------------------------------------------------
    # TEMAS
    # ------------------------------------------------------
    temas: Mapped[List["ProposicaoTema"]] = relationship(
        "ProposicaoTema",
        back_populates="proposicao",
        cascade="all, delete-orphan"
    )

    # ------------------------------------------------------
    # VOTACOES
    # ------------------------------------------------------
    votacoes: Mapped[List["Votacao"]] = relationship(
        "Votacao",
        back_populates="proposicao"
    )

    votacoes_afetadas: Mapped[List["VotacaoProposicao"]] = relationship(
        "VotacaoProposicao",
        back_populates="proposicao",
        cascade="all, delete-orphan"
    )

    # ------------------------------------------------------
    # PAUTAS
    # ------------------------------------------------------
    pautas: Mapped[List["PautaItem"]] = relationship(
        "PautaItem",
        back_populates="proposicao"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Proposicao id={self.id} "
            f"{self.sigla_tipo} {self.numero}/{self.ano}>"
        )


# === ProposicaoAutor (quem assina a proposicao) ===
class ProposicaoAutor(db.Model):
    __tablename__ = "proposicao_autor"

    proposicao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("proposicao.id"), primary_key=True)
    ordem: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    # Nulo se o autor nao e deputado
    deputado_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("deputado.id"), nullable=True, index=True
    )
    nome: Mapped[str] = mapped_column(db.Text, nullable=False)
    cod_tipo: Mapped[int] = mapped_column(db.Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    proponente: Mapped[bool] = mapped_column(db.Boolean, nullable=False)

    # ------------------------------------------------------
    # PROPOSICAO
    # ------------------------------------------------------
    proposicao: Mapped["Proposicao"] = relationship(
        "Proposicao",
        back_populates="autores"
    )

    # ------------------------------------------------------
    # DEPUTADO
    # ------------------------------------------------------
    deputado: Mapped[Optional["Deputado"]] = relationship(
        "Deputado",
        back_populates="autorias"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<ProposicaoAutor proposicao_id={self.proposicao_id} "
            f"ordem={self.ordem} nome='{self.nome}'>"
        )


# === ProposicaoTema (temas de cada proposicao) ===
class ProposicaoTema(db.Model):
    __tablename__ = "proposicao_tema"

    proposicao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("proposicao.id"), primary_key=True)
    cod_tema: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("tema.cod_tema"), primary_key=True)
    relevancia: Mapped[int] = mapped_column(db.Integer, nullable=False)

    # ------------------------------------------------------
    # PROPOSICAO
    # ------------------------------------------------------
    proposicao: Mapped["Proposicao"] = relationship(
        "Proposicao",
        back_populates="temas"
    )

    # ------------------------------------------------------
    # TEMA
    # ------------------------------------------------------
    tema: Mapped["Tema"] = relationship(
        "Tema",
        back_populates="proposicoes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<ProposicaoTema proposicao_id={self.proposicao_id} "
            f"cod_tema={self.cod_tema}>"
        )


# === Tema (tema oficial, usado como categoria do portal) ===
class Tema(db.Model):
    __tablename__ = "tema"

    cod_tema: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Nome do icone Material Symbols, definido pelo portal
    icone: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # PROPOSICOES
    # ------------------------------------------------------
    proposicoes: Mapped[List["ProposicaoTema"]] = relationship(
        "ProposicaoTema",
        back_populates="tema"
    )

    # ------------------------------------------------------
    # NOTICIAS
    # ------------------------------------------------------
    noticias: Mapped[List["Noticia"]] = relationship(
        "Noticia",
        back_populates="tema"
    )

    # ------------------------------------------------------
    # VISITANTES
    # ------------------------------------------------------
    visitantes: Mapped[List["VisitanteTema"]] = relationship(
        "VisitanteTema",
        back_populates="tema"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Tema cod_tema={self.cod_tema} "
            f"nome='{self.nome}'>"
        )


# === Tramitacao (passo do andamento da proposicao) ===
class Tramitacao(db.Model):
    __tablename__ = "tramitacao"

    proposicao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("proposicao.id"), primary_key=True)
    sequencia: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    data_hora: Mapped[datetime] = mapped_column(db.DateTime, nullable=False)
    orgao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("orgao.id"), nullable=False, index=True)
    sigla_orgao: Mapped[str] = mapped_column(db.Text, nullable=False)
    cod_tipo_tramitacao: Mapped[str] = mapped_column(db.Text, nullable=False)
    descricao: Mapped[str] = mapped_column(db.Text, nullable=False)
    cod_situacao: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    situacao: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    despacho: Mapped[str] = mapped_column(db.Text, nullable=False)
    regime: Mapped[str] = mapped_column(db.Text, nullable=False)
    ambito: Mapped[str] = mapped_column(db.Text, nullable=False)
    apreciacao: Mapped[str] = mapped_column(db.Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)

    # ------------------------------------------------------
    # PROPOSICAO
    # ------------------------------------------------------
    proposicao: Mapped["Proposicao"] = relationship(
        "Proposicao",
        back_populates="tramitacoes"
    )

    # ------------------------------------------------------
    # ORGAO
    # ------------------------------------------------------
    orgao: Mapped["Orgao"] = relationship(
        "Orgao",
        back_populates="tramitacoes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Tramitacao proposicao_id={self.proposicao_id} "
            f"sequencia={self.sequencia}>"
        )
