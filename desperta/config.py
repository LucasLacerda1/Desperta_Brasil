import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-desperta")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///desperta.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    DEBUG = True

    # Decisao 10.5: CORS so para o front-end conhecido, com o cookie de sessao
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Em producao (HTTPS), SESSION_COOKIE_SECURE=1
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    # Login da equipe: a sessao dura um turno de trabalho
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSAO_HORAS", "8")))
    # RNF10: depois destas falhas na janela, o login responde 429 (por e-mail e, x4, por IP)
    LOGIN_TENTATIVAS = int(os.getenv("LOGIN_TENTATIVAS", "5"))
    LOGIN_JANELA_MIN = int(os.getenv("LOGIN_JANELA_MIN", "15"))
    # Limite de requisicoes por endereco (IP) nas rotas da API (RNF10, decisao 25.4); 0 desliga
    LIMITE_JANELA_S = int(os.getenv("LIMITE_JANELA_S", "60"))
    LIMITE_GERAL = int(os.getenv("LIMITE_GERAL", "600"))
    LIMITE_BUSCA = int(os.getenv("LIMITE_BUSCA", "60"))
    # RNF05: sem coleta concluida ha mais que isto, o portal avisa que os dados podem estar desatualizados
    AVISO_DESATUALIZADO_HORAS = int(os.getenv("AVISO_DESATUALIZADO_HORAS", "6"))

    # Fases seguintes (ja deixar declarado)
    CAMARA_API_URL = os.getenv("CAMARA_API_URL", "https://dadosabertos.camara.leg.br/api/v2")
    CAMARA_TIMEOUT = int(os.getenv("CAMARA_TIMEOUT", "30"))
    TIPOS_ACOMPANHADOS = os.getenv("TIPOS_ACOMPANHADOS", "PL,PLP,PEC,MPV,PDL").split(",")
    # Decisoes 14.2 e 15.3: limites da rotina horaria
    HORARIA_ORCAMENTO_MIN = int(os.getenv("HORARIA_ORCAMENTO_MIN", "20"))
    HORARIA_RECONFERIR_HORAS = int(os.getenv("HORARIA_RECONFERIR_HORAS", "6"))
    # Decisao 25.8: item que deu 404 na Camara so e pedido de novo depois disto (0 desliga)
    COLETOR_AUSENTE_HORAS = int(os.getenv("COLETOR_AUSENTE_HORAS", "24"))
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "eduagarcia/RoBERTaLexPT-base")
    # Decisao 21.2: modelos em pastas simples; so a RoBERTaLexPT-base pode ficar no pendrive
    MODELOS_DIR = os.getenv("MODELOS_DIR", "instance/modelos")
    ROBERTA_DIR_PADRAO = os.path.join(MODELOS_DIR, "roberta-lexpt-base")
    ROBERTA_DIR = os.getenv("ROBERTA_DIR", ROBERTA_DIR_PADRAO)
    ROBERTA_ESCRITORA_DIR = os.getenv("ROBERTA_ESCRITORA_DIR", os.path.join(MODELOS_DIR, "roberta-escritora"))
    # Decisao 25.10: o e5 (multilingual-e5-base, MIT) indexa ao lado da RoBERTaLexPT e fica no disco do PC
    E5_MODEL = os.getenv("E5_MODEL", "intfloat/multilingual-e5-base")
    E5_DIR = os.getenv("E5_DIR", os.path.join(MODELOS_DIR, "multilingual-e5-base"))
    # Qual dos dois modelos a escrita dos rascunhos usa na busca: e5 ou roberta
    RAG_MODELO = os.getenv("RAG_MODELO", "e5")
    HF_HUB_OFFLINE = os.getenv("HF_HUB_OFFLINE", "0")
    # Decisao 20.2: auto usa a RTX 4050 se existir; cuda exige a placa; cpu nunca a usa
    IA_DISPOSITIVO = os.getenv("IA_DISPOSITIVO", "auto")
    # Decisao 17.2: falso, frases ou roberta
    GERADOR = os.getenv("GERADOR", "frases")
    # Item 4 da 22.10: flask ia gerar-novos olha os fatos destes ultimos dias
    GERACAO_JANELA_DIAS = int(os.getenv("GERACAO_JANELA_DIAS", "3"))
    RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
    # Decisao 16.1: busca hibrida com RRF
    RAG_CANDIDATOS = int(os.getenv("RAG_CANDIDATOS", "50"))
    RAG_RRF_K = int(os.getenv("RAG_RRF_K", "60"))
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
    # Os testes nunca carregam o e5 de verdade (1,1 GB), mesmo que ele esteja na pasta do projeto
    E5_DIR = os.path.join("instance", "modelos-de-teste", "multilingual-e5-base")
