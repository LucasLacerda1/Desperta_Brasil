import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-desperta")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///desperta.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    DEBUG = True

    # Fases seguintes (ja deixar declarado)
    CAMARA_API_URL = os.getenv("CAMARA_API_URL", "https://dadosabertos.camara.leg.br/api/v2")
    CAMARA_TIMEOUT = int(os.getenv("CAMARA_TIMEOUT", "30"))
    TIPOS_ACOMPANHADOS = os.getenv("TIPOS_ACOMPANHADOS", "PL,PLP,PEC,MPV,PDL").split(",")
    # Decisoes 14.2 e 15.3: limites da rotina horaria
    HORARIA_ORCAMENTO_MIN = int(os.getenv("HORARIA_ORCAMENTO_MIN", "20"))
    HORARIA_RECONFERIR_HORAS = int(os.getenv("HORARIA_RECONFERIR_HORAS", "6"))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "eduagarcia/RoBERTaLexPT-base")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
    RAG_TRECHO_TOKENS = 400
    RAG_TRECHO_SOBREPOSICAO = 50
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
    PIPER_VOICE = os.getenv("PIPER_VOICE", "pt_BR-faber-medium")
    AUDIO_DIR = os.getenv("AUDIO_DIR", "instance/audio")


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
