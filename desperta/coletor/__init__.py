# ==========================================================
# COLETOR DA API DA CAMARA (nao e blueprint)
# ==========================================================
# Regras de normalizacao de todos os modulos deste pacote:
# - texto vazio "" vira None em coluna opcional; em coluna obrigatoria fica "";
# - ids que vem como texto (tema.cod, bloco.id, idLegislatura de bloco) viram int;
# - uri*, links e o envelope "dados" nao vao para o banco: das uri saem apenas ids;
# - valor obrigatorio ausente nao e inventado: a linha falha, vai para log_sistema
#   e a coleta fica parcial (decisao 10.2). Nao afrouxar nullable por conta propria.
from .cli import init_app

__all__ = ["init_app"]
