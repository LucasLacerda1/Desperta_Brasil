from flask import Flask

from .auth import init_app as init_auth
from .coletor import init_app as init_coletor
from .config import Config
from .ext.cli import init_app as init_cli
from .ext.cors import init_app as init_cors
from .ext.db import init_app as init_db
from .ext.db import register_models
from .ia import init_app as init_ia
from .noticias import init_app as init_noticias
from .orgaos import init_app as init_orgaos
from .parlamentares import init_app as init_parlamentares
from .proposicoes import init_app as init_proposicoes
from .sistema import init_app as init_sistema
from .visitantes import init_app as init_visitantes
from .votacoes import init_app as init_votacoes


# ==========================================================
# CARREGAMENTO CENTRALIZADO DE AMBIENTE
# ==========================================================
def create_app(config_class=Config):
    app = Flask(__name__)

    app.config.from_object(config_class)

    # ----------------------------------------------------------
    # Inicializacao das extensoes
    # ----------------------------------------------------------
    init_db(app)
    init_cors(app)
    init_cli(app)
    init_coletor(app)

    # ----------------------------------------------------------
    # Registro dos modelos no metadata do SQLAlchemy
    # ----------------------------------------------------------
    register_models()

    # ----------------------------------------------------------
    # Registro dos modulos de dominio
    # ----------------------------------------------------------
    init_auth(app)
    init_proposicoes(app)
    init_votacoes(app)
    init_parlamentares(app)
    init_orgaos(app)
    init_noticias(app)
    init_ia(app)
    init_sistema(app)
    init_visitantes(app)

    # ----------------------------------------------------------
    # Verificacao de saude da API
    # ----------------------------------------------------------
    @app.route("/api/health")
    def health():
        return {"status": "ok", "message": "Desperta Brasil API is running"}

    return app
