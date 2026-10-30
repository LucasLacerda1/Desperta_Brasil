from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.auth.models import Administrador
    from desperta.ia.models import GeracaoIA
    from desperta.proposicoes.models import Tema

NOTICIA_TIPOS = ("noticia", "relatorio")
NOTICIA_ORIGENS = ("ia", "equipe")
NOTICIA_STATUS = ("rascunho", "em_revisao", "publicada", "rejeitada", "arquivada")
NOTICIA_FONTE_TIPOS = ("proposicao", "votacao", "deputado", "evento", "orgao", "partido")
NOTICIA_REVISAO_ACOES = ("editou", "aprovou", "rejeitou", "publicou", "arquivou")


# === Noticia (noticia ou relatorio escrito pela IA ou pela equipe) ===
class Noticia(db.Model):
    __tablename__ = "noticia"
    __table_args__ = (
        db.CheckConstraint(f"tipo IN {NOTICIA_TIPOS}", name="tipo"),
        db.CheckConstraint(f"origem IN {NOTICIA_ORIGENS}", name="origem"),
        db.CheckConstraint(f"status IN {NOTICIA_STATUS}", name="status"),
        db.Index("ix_noticia_status_publicado_em", "status", "publicado_em"),
        db.Index("ix_noticia_cod_tema_status_publicado_em", "cod_tema", "status", "publicado_em"),
    )

    # ======================================================
    # CONTEUDO
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    titulo: Mapped[str] = mapped_column(db.String(200), nullable=False)
    # Gerado do titulo; nao muda depois de publicado
    slug: Mapped[str] = mapped_column(db.String(220), nullable=False, unique=True, index=True)
    resumo: Mapped[str] = mapped_column(db.String(500), nullable=False)
    corpo: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ======================================================
    # CLASSIFICACAO
    # ======================================================
    tipo: Mapped[str] = mapped_column(db.String(20), nullable=False, default="noticia")
    origem: Mapped[str] = mapped_column(db.String(20), nullable=False)
    cod_tema: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("tema.cod_tema"), nullable=False)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False, default="rascunho")

    # ======================================================
    # DATAS E CONTADOR
    # ======================================================
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    publicado_em: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True, index=True)
    # Preenchido pelo service quando o texto muda (sem onupdate: somar visualizacao nao altera a data)
    alterado_em: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)
    visualizacoes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)

    # ------------------------------------------------------
    # TEMA
    # ------------------------------------------------------
    tema: Mapped["Tema"] = relationship(
        "Tema",
        back_populates="noticias"
    )

    # ------------------------------------------------------
    # FONTES
    # ------------------------------------------------------
    fontes: Mapped[List["NoticiaFonte"]] = relationship(
        "NoticiaFonte",
        back_populates="noticia",
        cascade="all, delete-orphan",
        order_by="NoticiaFonte.ordem"
    )

    # ------------------------------------------------------
    # REVISOES
    # ------------------------------------------------------
    revisoes: Mapped[List["NoticiaRevisao"]] = relationship(
        "NoticiaRevisao",
        back_populates="noticia",
        cascade="all, delete-orphan",
        order_by="NoticiaRevisao.data_hora"
    )

    # ------------------------------------------------------
    # GERACOES DA IA
    # ------------------------------------------------------
    geracoes: Mapped[List["GeracaoIA"]] = relationship(
        "GeracaoIA",
        back_populates="noticia"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Noticia id={self.id} "
            f"slug='{self.slug}' status='{self.status}'>"
        )


# === NoticiaFonte (registros da API usados na noticia) ===
class NoticiaFonte(db.Model):
    __tablename__ = "noticia_fonte"
    __table_args__ = (
        db.CheckConstraint(f"tipo IN {NOTICIA_FONTE_TIPOS}", name="tipo"),
        db.Index("ix_noticia_fonte_tipo_ref_id", "tipo", "ref_id"),
    )

    noticia_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("noticia.id"), primary_key=True)
    tipo: Mapped[str] = mapped_column(db.String(20), primary_key=True)
    # Id do registro, sem FK (cabe id de votacao); o back-end confere se existe
    ref_id: Mapped[str] = mapped_column(db.String(20), primary_key=True)
    # 1 = fonte principal (gera o link da fonte oficial)
    ordem: Mapped[int] = mapped_column(db.Integer, nullable=False)

    # ------------------------------------------------------
    # NOTICIA
    # ------------------------------------------------------
    noticia: Mapped["Noticia"] = relationship(
        "Noticia",
        back_populates="fontes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<NoticiaFonte noticia_id={self.noticia_id} "
            f"tipo='{self.tipo}' ref_id='{self.ref_id}'>"
        )


# === NoticiaRevisao (historico de revisao, uma linha por acao) ===
class NoticiaRevisao(db.Model):
    __tablename__ = "noticia_revisao"
    __table_args__ = (
        db.CheckConstraint(f"acao IN {NOTICIA_REVISAO_ACOES}", name="acao"),
        db.Index("ix_noticia_revisao_noticia_id_data_hora", "noticia_id", "data_hora"),
    )

    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    noticia_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("noticia.id"), nullable=False)
    admin_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("administrador.id"), nullable=False, index=True)
    acao: Mapped[str] = mapped_column(db.String(20), nullable=False)
    # Retorno para melhorar a IA
    comentario: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    data_hora: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())

    # ------------------------------------------------------
    # NOTICIA
    # ------------------------------------------------------
    noticia: Mapped["Noticia"] = relationship(
        "Noticia",
        back_populates="revisoes"
    )

    # ------------------------------------------------------
    # ADMINISTRADOR
    # ------------------------------------------------------
    administrador: Mapped["Administrador"] = relationship(
        "Administrador",
        back_populates="revisoes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<NoticiaRevisao id={self.id} "
            f"noticia_id={self.noticia_id} acao='{self.acao}'>"
        )
