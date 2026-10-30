# ==========================================================
# REGRA DE FUSO HORARIO
# ==========================================================
# Datas da API da Camara (data_hora, data_apresentacao, data_hora_inicio,
# data_registro...): horario de Brasilia, sem fuso, como a API manda.
# Colunas do portal e tecnicas (criado_em, atualizado_em, sincronizado_em,
# publicado_em, iniciado_em, data_hora de log e revisao, ultimo_acesso...):
# UTC, que e o que CURRENT_TIMESTAMP do SQLite grava. No Python, preencher com
# datetime.now(timezone.utc).replace(tzinfo=None).
# Na Fase 4, a API do portal devolve ISO 8601 com fuso: -03:00 nas datas da
# Camara e Z nas do portal.
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from desperta.ext.db import db


# === SincronizacaoMixin (registro principal vindo da API) ===
class SincronizacaoMixin:
    # quando o registro entrou no banco
    criado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    # quando o conteudo mudou de verdade (hash diferente); o coletor preenche, sem onupdate
    atualizado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
    # ultima vez que o registro apareceu numa resposta da API
    sincronizado_em: Mapped[datetime] = mapped_column(
        db.DateTime, nullable=False, server_default=db.func.now(), index=True
    )
    # SHA-256 dos campos gravados, para saber se algo mudou
    hash_origem: Mapped[str] = mapped_column(db.String(64), nullable=False)


# === VinculoSincronizadoMixin (linha filha ou associativa vinda da API) ===
class VinculoSincronizadoMixin:
    sincronizado_em: Mapped[datetime] = mapped_column(db.DateTime, nullable=False, server_default=db.func.now())
