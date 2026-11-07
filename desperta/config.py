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
    # Decisao 21.2: modelos em pastas simples; so a RoBERTaLexPT-base pode ficar no pendrive
    MODELOS_DIR = os.getenv("MODELOS_DIR", "instance/modelos")
    ROBERTA_DIR_PADRAO = os.path.join(MODELOS_DIR, "roberta-lexpt-base")
    ROBERTA_DIR = os.getenv("ROBERTA_DIR", ROBERTA_DIR_PADRAO)
    ROBERTA_ESCRITORA_DIR = os.getenv("ROBERTA_ESCRITORA_DIR", os.path.join(MODELOS_DIR, "roberta-escritora"))
    HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE", "0")
    # Decisao 20.2: auto usa a RTX 4050 se existir; cuda exige a placa; cpu nunca a usa
    IA_DISPOSITIVO = os.getenv("IA_DISPOSITIVO", "auto")
    # Decisao 17.2: falso, frases ou roberta
    GERADOR = os.getenv("GERADOR", "frases")
    # Item 4 da 22.10: flask ia gerar-novos olha os fatos destes ultimos dias
    GERACAO_JANELA_DIAS = int(os.getenv("GERACAO_JANELA_DIAS", "3"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
    # Decisao 16.1: busca hibrida com RRF e experimento de centralizacao (descartado na 19.1)
    RAG_CANDIDATOS = int(os.getenv("RAG_CANDIDATOS", "50"))
    RAG_RRF_K = int(os.getenv("RAG_RRF_K", "60"))
    RAG_CENTRALIZAR = os.getenv("RAG_CENTRALIZAR", "0") == "1"
    # Decisao 19.2: peso da lista vetorial no modo hibrida_peso (a de palavras pesa 1,0)
    RAG_PESO_VETOR = float(os.getenv("RAG_PESO_VETOR", "0.5"))
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
