from flask_cors import CORS

cors = CORS()


def init_app(app):
    # Decisao 10.5: so as origens de CORS_ORIGINS, com o cookie de sessao (supports_credentials).
    # Em desenvolvimento o front-end usa o proxy do Vite e nem passa por aqui.
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )
