# Desperta Brasil

Portal de notícias sobre a atividade da Câmara dos Deputados, com dados abertos e IA (Flask + Vue 3).

Fase atual: coletor da API da Câmara. O guia completo do projeto está em `CLAUDE.md`.

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

## Coleta de dados

```bash
flask coletar base                 # legislaturas, partidos, deputados, órgãos e temas (rodar primeiro)
flask coletar horaria              # votações e eventos (ontem e hoje) e proposições (hoje), com limite de 20 minutos
flask coletar proposicoes --inicio 2025-01-01 --fim 2025-03-31 --sigla-tipo PEC
flask coletar relatorio            # colunas que falharam, textos vazios e instabilidade da API
invoke coletar --rotina=semanal    # o mesmo pelo Invoke
```

Carga de validação (amostra da decisão 12.2), que não morre se a sessão fechar:

```bash
nohup invoke carga-validacao > instance/carga.log 2>&1 &
```

Agendamento do RF02, conforme a decisão 12.1 do `CLAUDE.md` (exemplo de `crontab`, com o caminho do projeto ajustado):

```cron
0 * * * *  cd /caminho/Desperta_Brasil && .venv/bin/flask coletar horaria
0 2 * * *  cd /caminho/Desperta_Brasil && .venv/bin/flask coletar diaria
0 4 * * 0  cd /caminho/Desperta_Brasil && .venv/bin/flask coletar semanal
0 4 1 * *  cd /caminho/Desperta_Brasil && .venv/bin/flask coletar mensal
```

Só roda uma coleta por vez: a trava fica em `instance/coletor.lock`. Quem encontra a trava não roda e grava um aviso em `log_sistema`. Trava de um processo que não existe mais, ou com mais de 6 horas, é considerada abandonada: é removida, com um aviso no log.

Cada coleta grava uma linha em `coleta` e os erros em `log_sistema`. Um registro com problema não derruba a coleta: ela termina como `parcial`.

## Problema conhecido

`pytest --cov=desperta.coletor` falha dentro do SQLAlchemy (`TypeError` em `_cache_key_cy`). Use o comando oficial, `invoke test`, que mede com `--cov=desperta`.
