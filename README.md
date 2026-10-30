# Desperta Brasil

Portal de notícias sobre a atividade da Câmara dos Deputados, com dados abertos e IA (Flask + Vue 3).

Fase atual: banco de dados (32 tabelas). O guia completo do projeto está em `CLAUDE.md`.

## Como instalar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install invoke
invoke install
cp .env.example .env
```

## Como rodar

```bash
invoke initdb   # cria as 32 tabelas em instance/desperta.db
invoke run      # API em http://localhost:5000/api/health
invoke test     # testes automatizados
invoke lint     # verificacao de estilo
```

`flask drop-db` apaga todas as tabelas.
