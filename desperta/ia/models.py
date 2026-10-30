from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.noticias.models import Noticia

GERACAO_IA_STATUS = ("ok", "erro")
TRECHO_RAG_TIPOS = ("proposicao", "tramitacao", "votacao", "evento", "pauta_item")


# === GeracaoIA (cada execucao da IA, mesmo com erro) ===
class GeracaoIA(db.Model):
    __tablename__ = "geracao_ia"
    __table_args__ = (
        db.CheckConstraint(f"status IN {GERACAO_IA_STATUS}", name="status"),
        db.Index("ix_geracao_ia_status_criado_em", "status", "criado_em"),
    )

    # ======================================================
    # IDENTIFICACAO
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    # Nulo se a geracao falhou
    noticia_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("noticia.id"), nullable=True, index=True
    )

    # ======================================================
    # ENTRADA
    # ======================================================
    modelo_geracao: Mapped[str] = mapped_column(db.String(100), nullable=False)
    modelo_embedding: Mapped[str] = mapped_column(db.String(100), nullable=False)
    consulta: Mapped[str] = mapped_column(db.Text, nullable=False)
    top_k: Mapped[int] = mapped_column(db.Integer, nullable=False, default=8)
    versao_prompt: Mapped[str] = mapped_column(db.String(50), nullable=False)
    # JSON com os ids usados
    entrada: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ======================================================
    # RESULTADO
    # ======================================================
    tokens_entrada: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    tokens_saida: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    duracao_ms: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False)
    erro: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())

    # ------------------------------------------------------
    # NOTICIA
    # ------------------------------------------------------
    noticia: Mapped[Optional["Noticia"]] = relationship(
        "Noticia",
        back_populates="geracoes"
    )

    # ------------------------------------------------------
    # TRECHOS
    # ------------------------------------------------------
    trechos: Mapped[List["GeracaoTrecho"]] = relationship(
        "GeracaoTrecho",
        back_populates="geracao",
        cascade="all, delete-orphan",
        order_by="GeracaoTrecho.posicao"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<GeracaoIA id={self.id} "
            f"modelo='{self.modelo_geracao}' status='{self.status}'>"
        )


# === TrechoRAG (pedaco de texto com embedding) ===
class TrechoRAG(db.Model):
    __tablename__ = "trecho_rag"
    __table_args__ = (
        db.UniqueConstraint("tipo", "ref_id", "parte", "modelo_embedding", name="uq_trecho_rag_tipo_ref_parte_modelo"),
        db.CheckConstraint(f"tipo IN {TRECHO_RAG_TIPOS}", name="tipo"),
        db.Index("ix_trecho_rag_tipo_ref_id", "tipo", "ref_id"),
    )

    # ======================================================
    # ORIGEM (id usado na tabela virtual do sqlite-vec)
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    tipo: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Id do registro de origem, sem FK
    ref_id: Mapped[str] = mapped_column(db.String(20), nullable=False)
    parte: Mapped[int] = mapped_column(db.Integer, nullable=False)

    # ======================================================
    # TEXTO E EMBEDDING
    # ======================================================
    texto: Mapped[str] = mapped_column(db.Text, nullable=False)
    tokens: Mapped[int] = mapped_column(db.Integer, nullable=False)
    # 768 float32 = 3.072 bytes
    embedding: Mapped[bytes] = mapped_column(db.LargeBinary, nullable=False)
    modelo_embedding: Mapped[str] = mapped_column(db.String(100), nullable=False)
    # SHA-256 em hexadecimal
    hash_texto: Mapped[str] = mapped_column(db.String(64), nullable=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())

    # ------------------------------------------------------
    # GERACOES
    # ------------------------------------------------------
    geracoes: Mapped[List["GeracaoTrecho"]] = relationship(
        "GeracaoTrecho",
        back_populates="trecho"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<TrechoRAG id={self.id} "
            f"tipo='{self.tipo}' ref_id='{self.ref_id}' parte={self.parte}>"
        )


# === GeracaoTrecho (trechos recuperados em cada geracao) ===
class GeracaoTrecho(db.Model):
    __tablename__ = "geracao_trecho"

    geracao_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("geracao_ia.id"), primary_key=True)
    trecho_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("trecho_rag.id"), primary_key=True, index=True)
    # 1 = mais parecido
    posicao: Mapped[int] = mapped_column(db.Integer, nullable=False)
    # Cosseno
    similaridade: Mapped[float] = mapped_column(db.Float, nullable=False)

    # ------------------------------------------------------
    # GERACAO
    # ------------------------------------------------------
    geracao: Mapped["GeracaoIA"] = relationship(
        "GeracaoIA",
        back_populates="trechos"
    )

    # ------------------------------------------------------
    # TRECHO
    # ------------------------------------------------------
    trecho: Mapped["TrechoRAG"] = relationship(
        "TrechoRAG",
        back_populates="geracoes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<GeracaoTrecho geracao_id={self.geracao_id} "
            f"trecho_id={self.trecho_id} posicao={self.posicao}>"
        )
