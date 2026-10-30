from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from desperta.ext.db import db

if TYPE_CHECKING:
    from desperta.auth.models import Administrador

LOG_NIVEIS = ("info", "aviso", "erro")
LOG_MODULOS = ("coletor", "IA", "admin")
COLETA_STATUS = ("ok", "parcial", "erro")
COLETA_TIPOS = ("incremental", "completa", "detalhe")


# === LogSistema (acoes do coletor, da IA e dos administradores) ===
class LogSistema(db.Model):
    __tablename__ = "log_sistema"
    __table_args__ = (
        db.CheckConstraint(f"nivel IN {LOG_NIVEIS}", name="nivel"),
        db.CheckConstraint(f"modulo IN {LOG_MODULOS}", name="modulo"),
        db.Index("ix_log_sistema_modulo_data_hora", "modulo", "data_hora"),
    )

    # ======================================================
    # REGISTRO
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    data_hora: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now(), index=True)
    nivel: Mapped[str] = mapped_column(db.String(10), nullable=False, index=True)
    modulo: Mapped[str] = mapped_column(db.String(20), nullable=False)
    acao: Mapped[str] = mapped_column(db.String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(db.Text, nullable=False)

    # ======================================================
    # ORIGEM
    # ======================================================
    admin_id: Mapped[Optional[int]] = mapped_column(
        db.Integer, db.ForeignKey("administrador.id"), nullable=True, index=True
    )
    coleta_id: Mapped[Optional[int]] = mapped_column(db.Integer, db.ForeignKey("coleta.id"), nullable=True, index=True)
    # Nome da tabela e id da linha (numero ou id de votacao)
    entidade: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True)
    entidade_id: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True)

    # ------------------------------------------------------
    # ADMINISTRADOR
    # ------------------------------------------------------
    administrador: Mapped[Optional["Administrador"]] = relationship(
        "Administrador",
        back_populates="logs"
    )

    # ------------------------------------------------------
    # COLETA
    # ------------------------------------------------------
    coleta: Mapped[Optional["Coleta"]] = relationship(
        "Coleta",
        back_populates="logs"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<LogSistema id={self.id} "
            f"nivel='{self.nivel}' acao='{self.acao}'>"
        )


# === Coleta (cada chamada do coletor) ===
class Coleta(db.Model):
    __tablename__ = "coleta"
    __table_args__ = (
        db.CheckConstraint(f"status IN {COLETA_STATUS}", name="status"),
        db.CheckConstraint(f"tipo IN {COLETA_TIPOS}", name="tipo"),
        db.Index("ix_coleta_recurso_status_finalizado", "recurso", "status", "finalizado_em"),
    )

    # ======================================================
    # CHAMADA
    # ======================================================
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    # Nome logico: proposicoes, votacoes, eventos, deputados, partidos, orgaos, orgao_membros,
    # mesa, liderancas, blocos, frentes, temas, legislaturas
    recurso: Mapped[str] = mapped_column(db.String(50), nullable=False)
    tipo: Mapped[str] = mapped_column(db.String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(db.String(255), nullable=False)
    # JSON
    parametros: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    # Janela de datas pedida a API
    data_inicio_ref: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)
    data_fim_ref: Mapped[Optional[date]] = mapped_column(db.Date, nullable=True)
    iniciado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    finalizado_em: Mapped[Optional[datetime]] = mapped_column(db.DateTime, nullable=True)

    # ======================================================
    # RESULTADO
    # ======================================================
    total_itens: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    itens_novos: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    itens_atualizados: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(db.String(20), nullable=False)
    mensagem_erro: Mapped[Optional[str]] = mapped_column(db.Text, nullable=True)
    # Chamadas HTTP e respostas 429/5xx, inclusive as que deram certo depois de nova tentativa
    requisicoes: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    erros_http: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)

    # ------------------------------------------------------
    # LOGS
    # ------------------------------------------------------
    logs: Mapped[List["LogSistema"]] = relationship(
        "LogSistema",
        back_populates="coleta"
    )

    # ======================================================
    # REPRESENTACAO
    # ======================================================
    def __repr__(self) -> str:
        return (
            f"<Coleta id={self.id} "
            f"endpoint='{self.endpoint}' status='{self.status}'>"
        )
