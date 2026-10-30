from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db
from desperta.ext.db.mixins import SincronizacaoMixin, VinculoSincronizadoMixin

if TYPE_CHECKING:
    from desperta.orgaos.models import DeputadoOrgao, PautaItem
    from desperta.proposicoes.models import ProposicaoAutor
    from desperta.votacoes.models import Orientacao, Voto

DEPUTADO_SEXOS = ("M", "F")


# === Deputado (parlamentar da Camara) ===
class Deputado(SincronizacaoMixin, db.Model):
    __tablename__ = "deputado"
    __table_args__ = (
        db.CheckConstraint(f"sexo IN {DEPUTADO_SEXOS}", name="sexo"),
        db.Index("ix_deputado_id_legislatura_sigla_partido", "id_legislatura", "sigla_partido"),
    )

    # ======================================================
    # IDENTIFICACAO (mesmo id da API da Camara)
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    sigla_uf: Mapped[str] = mapped_column(db.Text, nullable=False, index=True)
    # M ou F (filtro siglaSexo da chamada)
    sexo: Mapped[str] = mapped_column(db.Text, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    url_foto: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ======================================================
    # MANDATO
    # ======================================================
    id_legislatura: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("legislatura.id"), nullable=False)
    # D3: partido_id pode ser nulo, sigla_partido sempre preenchida
    partido_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("partido.id"), nullable=True, index=True
    )
    sigla_partido: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ------------------------------------------------------
    # LEGISLATURA
    # ------------------------------------------------------
    legislatura: Mapped["Legislatura"] = relationship(
        "Legislatura",
        back_populates="deputados"
    )

    # ------------------------------------------------------
    # PARTIDO
    # ------------------------------------------------------
    partido: Mapped[Optional["Partido"]] = relationship(
        "Partido",
        back_populates="deputados"
    )

    # ------------------------------------------------------
    # AUTORIAS
    # ------------------------------------------------------
    autorias: Mapped[List["ProposicaoAutor"]] = relationship(
        "ProposicaoAutor",
        back_populates="deputado"
    )

    # ------------------------------------------------------
    # VOTOS
    # ------------------------------------------------------
    votos: Mapped[List["Voto"]] = relationship(
        "Voto",
        back_populates="deputado"
    )

    # ------------------------------------------------------
    # LIDERANCAS
    # ------------------------------------------------------
    liderancas: Mapped[List["Lideranca"]] = relationship(
        "Lideranca",
        back_populates="deputado"
    )

    # ------------------------------------------------------
    # CARGOS EM ORGAOS
    # ------------------------------------------------------
    cargos: Mapped[List["DeputadoOrgao"]] = relationship(
        "DeputadoOrgao",
        back_populates="deputado"
    )

    # ------------------------------------------------------
    # FRENTES
    # ------------------------------------------------------
    frentes: Mapped[List["FrenteMembro"]] = relationship(
        "FrenteMembro",
        back_populates="deputado"
    )

    # ------------------------------------------------------
    # RELATORIAS
    # ------------------------------------------------------
    relatorias: Mapped[List["PautaItem"]] = relationship(
        "PautaItem",
        back_populates="relator"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Deputado id={self.id} "
            f"nome='{self.nome}' {self.sigla_partido}-{self.sigla_uf}>"
        )


# === Partido (sigla sem UNIQUE: ligacoes sempre pelo id) ===
class Partido(SincronizacaoMixin, db.Model):
    __tablename__ = "partido"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    sigla: Mapped[str] = mapped_column(db.Text, nullable=False)
    nome: Mapped[str] = mapped_column(db.Text, nullable=False)
    url_logo: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)

    # ------------------------------------------------------
    # DEPUTADOS
    # ------------------------------------------------------
    deputados: Mapped[List["Deputado"]] = relationship(
        "Deputado",
        back_populates="partido"
    )

    # ------------------------------------------------------
    # ORIENTACOES
    # ------------------------------------------------------
    orientacoes: Mapped[List["Orientacao"]] = relationship(
        "Orientacao",
        back_populates="partido"
    )

    # ------------------------------------------------------
    # BLOCOS
    # ------------------------------------------------------
    blocos: Mapped[List["BlocoPartido"]] = relationship(
        "BlocoPartido",
        back_populates="partido"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Partido id={self.id} "
            f"sigla='{self.sigla}'>"
        )


# === Legislatura (periodo de mandato) ===
class Legislatura(SincronizacaoMixin, db.Model):
    __tablename__ = "legislatura"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    data_inicio: Mapped[date] = mapped_column(db.Date, nullable=False)
    data_fim: Mapped[date] = mapped_column(db.Date, nullable=False)

    # ------------------------------------------------------
    # DEPUTADOS
    # ------------------------------------------------------
    deputados: Mapped[List["Deputado"]] = relationship(
        "Deputado",
        back_populates="legislatura"
    )

    # ------------------------------------------------------
    # BLOCOS
    # ------------------------------------------------------
    blocos: Mapped[List["Bloco"]] = relationship(
        "Bloco",
        back_populates="legislatura"
    )

    # ------------------------------------------------------
    # FRENTES
    # ------------------------------------------------------
    frentes: Mapped[List["Frente"]] = relationship(
        "Frente",
        back_populates="legislatura"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Legislatura id={self.id} "
            f"{self.data_inicio} a {self.data_fim}>"
        )


# === Lideranca (lideres e vice-lideres das bancadas) ===
class Lideranca(SincronizacaoMixin, db.Model):
    __tablename__ = "lideranca"
    __table_args__ = (
        # Chave natural: o upsert usa estas colunas, porque o id e gerado pelo banco
        db.UniqueConstraint(
            "deputado_id", "bancada_nome", "titulo", "data_inicio",
            name="uq_lideranca_deputado_bancada_titulo_inicio"
        ),
        db.Index("ix_lideranca_bancada_nome_data_inicio", "bancada_nome", "data_inicio"),
    )

    # Unica tabela da API com id gerado pelo banco
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    deputado_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("deputado.id"), nullable=False, index=True)
    bancada_nome: Mapped[str] = mapped_column(db.Text, nullable=False)
    # partido, bloco, Governo, Oposicao...
    bancada_tipo: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Lider, Vice-lider...
    titulo: Mapped[str] = mapped_column(db.Text, nullable=False)
    data_inicio: Mapped[date] = mapped_column(db.Date, nullable=False)
    data_fim: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)

    # ------------------------------------------------------
    # DEPUTADO
    # ------------------------------------------------------
    deputado: Mapped["Deputado"] = relationship(
        "Deputado",
        back_populates="liderancas"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Lideranca id={self.id} "
            f"titulo='{self.titulo}' bancada='{self.bancada_nome}'>"
        )


# === Bloco (bloco partidario ou federacao) ===
class Bloco(SincronizacaoMixin, db.Model):
    __tablename__ = "bloco"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(db.Text, nullable=False)
    federacao: Mapped[bool] = mapped_column(db.Boolean, nullable=False)
    id_legislatura: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("legislatura.id"), nullable=False, index=True)

    # ======================================================
    # CONTROLE DOS SUB-RECURSOS (/blocos/{id}/partidos; nulo = ainda nao buscados)
    # ======================================================
    filhos_sincronizados_em: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True, index=True)

    # ------------------------------------------------------
    # LEGISLATURA
    # ------------------------------------------------------
    legislatura: Mapped["Legislatura"] = relationship(
        "Legislatura",
        back_populates="blocos"
    )

    # ------------------------------------------------------
    # PARTIDOS
    # ------------------------------------------------------
    partidos: Mapped[List["BlocoPartido"]] = relationship(
        "BlocoPartido",
        back_populates="bloco",
        cascade="all, delete-orphan"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Bloco id={self.id} "
            f"nome='{self.nome}'>"
        )


# === BlocoPartido (composicao atual do bloco) ===
class BlocoPartido(VinculoSincronizadoMixin, db.Model):
    __tablename__ = "bloco_partido"

    bloco_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("bloco.id"), primary_key=True)
    partido_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("partido.id"), primary_key=True, index=True)

    # ------------------------------------------------------
    # BLOCO
    # ------------------------------------------------------
    bloco: Mapped["Bloco"] = relationship(
        "Bloco",
        back_populates="partidos"
    )

    # ------------------------------------------------------
    # PARTIDO
    # ------------------------------------------------------
    partido: Mapped["Partido"] = relationship(
        "Partido",
        back_populates="blocos"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<BlocoPartido bloco_id={self.bloco_id} "
            f"partido_id={self.partido_id}>"
        )


# === Frente (frente parlamentar) ===
class Frente(SincronizacaoMixin, db.Model):
    __tablename__ = "frente"

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=False)
    titulo: Mapped[str] = mapped_column(db.Text, nullable=False)
    id_legislatura: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("legislatura.id"), nullable=False, index=True)
    keywords: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)

    # ======================================================
    # CONTROLE DOS SUB-RECURSOS (/frentes/{id}, /frentes/{id}/membros; nulo = ainda nao buscados)
    # ======================================================
    filhos_sincronizados_em: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True, index=True)

    # ------------------------------------------------------
    # LEGISLATURA
    # ------------------------------------------------------
    legislatura: Mapped["Legislatura"] = relationship(
        "Legislatura",
        back_populates="frentes"
    )

    # ------------------------------------------------------
    # MEMBROS
    # ------------------------------------------------------
    membros: Mapped[List["FrenteMembro"]] = relationship(
        "FrenteMembro",
        back_populates="frente",
        cascade="all, delete-orphan"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Frente id={self.id} "
            f"titulo='{self.titulo}'>"
        )


# === FrenteMembro (deputado que participa da frente) ===
class FrenteMembro(VinculoSincronizadoMixin, db.Model):
    __tablename__ = "frente_membro"

    frente_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("frente.id"), primary_key=True)
    deputado_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("deputado.id"), primary_key=True, index=True)
    cod_titulo: Mapped[str] = mapped_column(db.Text, nullable=False)
    # Signatario, Coordenador, Presidente
    titulo: Mapped[str] = mapped_column(db.Text, nullable=False)
    data_inicio: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)
    data_fim: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)

    # ------------------------------------------------------
    # FRENTE
    # ------------------------------------------------------
    frente: Mapped["Frente"] = relationship(
        "Frente",
        back_populates="membros"
    )

    # ------------------------------------------------------
    # DEPUTADO
    # ------------------------------------------------------
    deputado: Mapped["Deputado"] = relationship(
        "Deputado",
        back_populates="frentes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<FrenteMembro frente_id={self.frente_id} "
            f"deputado_id={self.deputado_id} titulo='{self.titulo}'>"
        )
