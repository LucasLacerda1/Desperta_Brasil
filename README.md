# Desperta Brasil

Portal de notícias sobre a atividade da Câmara dos Deputados, com dados abertos e IA (Flask + Vue 3).

Fase atual: ajuste físico do banco (`docs/AJUSTE_BANCO_SISTEMA.md`). O guia completo do projeto está em `CLAUDE.md`.

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
invoke migrate  # cria ou atualiza o banco em instance/desperta.db (flask db upgrade)
invoke run      # API em http://localhost:5000/api/health
invoke test     # testes automatizados
invoke lint     # verificacao de estilo
```

`invoke initdb` (`flask init-db`) cria o banco sem migrações e serve só para desenvolvimento e testes. `flask drop-db` apaga todas as tabelas.

Toda mudança no esquema é uma migração: `flask db migrate -m "descricao"`, revisão do arquivo gerado e `flask db upgrade`.
