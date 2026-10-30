from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.noticias.models import NoticiaRevisao
    from desperta.sistema.models import LogSistema

ADMINISTRADOR_PAPEIS = ("admin", "editor")


# === Administrador (membro da equipe) ===
class Administrador(db.Model):
    __tablename__ = "administrador"
    __table_args__ = (
        db.CheckConstraint(f"papel IN {ADMINISTRADOR_PAPEIS}", name="ck_administrador_papel"),
    )

    # ======================================================
    # IDENTIFICACAO
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(254), nullable=False, unique=True, index=True)

    # ======================================================
    # ACESSO
    # ======================================================
    senha_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    papel: Mapped[str] = mapped_column(db.String(20), nullable=False, default="editor")
    ativo: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    ultimo_acesso: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    # ------------------------------------------------------
    # REVISOES
    # ------------------------------------------------------
    revisoes: Mapped[List["NoticiaRevisao"]] = relationship(
        "NoticiaRevisao",
        back_populates="administrador"
    )

    # ------------------------------------------------------
    # LOGS
    # ------------------------------------------------------
    logs: Mapped[List["LogSistema"]] = relationship(
        "LogSistema",
        back_populates="administrador"
    )

    # ======================================================
    # SENHA
    # ======================================================
    def set_senha(self, senha: str) -> None:
        self.senha_hash = generate_password_hash(senha)

    def confere_senha(self, senha: str) -> bool:
        return check_password_hash(self.senha_hash, senha)

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Administrador id={self.id} "
            f"email='{self.email}' papel='{self.papel}'>"
        )
