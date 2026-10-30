from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.proposicoes.models import Tema


# === Visitante (visitante anonimo, identificado por cookie) ===
class Visitante(db.Model):
    __tablename__ = "visitante"

    # UUID do cookie
    id: Mapped[str] = mapped_column(db.String(36), primary_key=True)
    # JSON
    preferencias: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    # Aceite de cookies (LGPD)
    consentimento: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    # Apagado apos 12 meses sem acesso
    ultimo_acesso: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())

    # ------------------------------------------------------
    # TEMAS
    # ------------------------------------------------------
    temas: Mapped[List["VisitanteTema"]] = relationship(
        "VisitanteTema",
        back_populates="visitante",
        cascade="all, delete-orphan"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Visitante id='{self.id}' "
            f"consentimento={self.consentimento}>"
        )


# === VisitanteTema (acessos do visitante por tema) ===
class VisitanteTema(db.Model):
    __tablename__ = "visitante_tema"

    visitante_id: Mapped[str] = mapped_column(db.String(36), db.ForeignKey("visitante.id"), primary_key=True)
    cod_tema: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("tema.cod_tema"), primary_key=True)
    acessos: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)

    # ------------------------------------------------------
    # VISITANTE
    # ------------------------------------------------------
    visitante: Mapped["Visitante"] = relationship(
        "Visitante",
        back_populates="temas"
    )

    # ------------------------------------------------------
    # TEMA
    # ------------------------------------------------------
    tema: Mapped["Tema"] = relationship(
        "Tema",
        back_populates="visitantes"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<VisitanteTema visitante_id='{self.visitante_id}' "
            f"cod_tema={self.cod_tema} acessos={self.acessos}>"
        )
