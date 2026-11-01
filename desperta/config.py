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
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "eduagarcia/RoBERTaLexPT-base")
    # Decisao 16.7: o modelo fica dentro do projeto (fora do git) e roda sem internet depois do download
    HF_HOME = os.getenv("HF_HOME", "instance/modelos")
    HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE", "0")
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
    # Decisao 16.1: busca hibrida com RRF e experimento de centralizacao
    RAG_CANDIDATOS = int(os.getenv("RAG_CANDIDATOS", "50"))
    RAG_RRF_K = int(os.getenv("RAG_RRF_K", "60"))
    RAG_CENTRALIZAR = os.getenv("RAG_CENTRALIZAR", "0") == "1"
    # Decisao 16.3: so as tramitacoes recentes viram trecho
    RAG_TRAMITACAO_DIAS = int(os.getenv("RAG_TRAMITACAO_DIAS", "90"))
    RAG_TRECHO_TOKENS = 400
    RAG_TRECHO_SOBREPOSICAO = 50
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
    PIPER_VOICE = os.getenv("PIPER_VOICE", "pt_BR-faber-medium")
    AUDIO_DIR = os.getenv("AUDIO_DIR", "instance/audio")


class TestConfig(Config):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
