from .cli import init_app as init_cli
from .routes import bp


def init_app(app):
    app.register_blueprint(bp, url_prefix="/api/ia")
    init_cli(app)
