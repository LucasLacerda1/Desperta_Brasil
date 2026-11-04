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
flask coletar horaria              # proposições, eventos e votações desde a última janela concluída
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

## RAG (Fase 3)

A RoBERTaLexPT roda só neste módulo; a API Flask não carrega o modelo. Precisa das dependências de IA:

```bash
# Com a RTX 4050 do PC do Lucas (driver 595, CUDA 13.2); o .venv fica com cerca de 5,7 GB.
# Com outra placa NVIDIA, use o comando que https://pytorch.org/get-started/locally/ indicar para o seu driver.
pip install "torch==2.15.0+cu132" --index-url https://download.pytorch.org/whl/cu132 --extra-index-url https://pypi.org/simple
# Sem placa da NVIDIA; o .venv fica com cerca de 1,3 GB
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[ia]"
```

```bash
flask ia baixar-modelo             # baixa a RoBERTaLexPT uma vez para ROBERTA_DIR (cerca de 500 MB)
flask ia mover-roberta --para /media/<usuario>/DESPERTA/roberta-lexpt-base   # copia e confere; não apaga a antiga
flask ia indexar                   # trechos e embeddings do que é novo ou mudou; pode parar e rodar de novo
flask ia indexar --tipo votacao    # só um tipo; --limite 500 para no máximo 500 trechos novos
flask ia buscar "reforma tributária" --tipo proposicao --inicio 2025-01-01 --fim 2025-12-31
flask ia medir-busca               # acertos de cada modo nas consultas de tests/dados/consultas_busca.json
flask ia reconstruir               # refaz os índices a partir de trecho_rag
flask ia gerar nova 2459654        # rascunho de uma proposição nova; também: situacao <id> e votacao <id>
```

Depois do download, use `HF_HUB_OFFLINE=1` no `.env`: o modelo roda sem internet. Sem as dependências de IA, os testes de `tests/test_ia.py` são pulados. Depois de cada coleta, rode `flask ia indexar`.

A RoBERTaLexPT-base fica em `ROBERTA_DIR`, numa pasta simples, sem os links do cache do Hugging Face. Sem essa pasta (pendrive desconectado), `indexar`, `buscar` e `medir-busca` param com uma mensagem clara e um aviso no log, e `gerar` usa só a busca por palavras. O coletor, a API e os testes não dependem dela.

`IA_DISPOSITIVO` escolhe onde o modelo roda: `auto` (a placa NVIDIA se existir, senão o processador), `cuda` (para com erro sem a placa) ou `cpu`. O dispositivo de cada execução fica em `log_sistema`.

A busca é híbrida: junta o índice vetorial (`vec_trecho`) e o de palavras (`trecho_fts`) por Reciprocal Rank Fusion. O modo `hibrida_peso` faz o mesmo com a lista vetorial pesando `RAG_PESO_VETOR` (padrão: 0,5). Os índices não são modelos SQLAlchemy nem contam entre as 32 tabelas. Só as tramitações dos últimos `RAG_TRAMITACAO_DIAS` dias (padrão: 90) viram trecho.

Em `tests/dados/consultas_busca.json`, cada consulta pode ter a lista `fora_do_assunto`, com as proposições marcadas à mão, e o `medir-busca` conta quantas aparecem nos 8 primeiros.

As notícias são escritas pelo `GERADOR` (padrão: `frases`). O `GeradorFrases` usa frases prontas, sem IA: todo número, nome e data vem dos registros do banco. Votação de requerimento ou de redação final não vira "Câmara aprova projeto". Toda notícia entra como `rascunho`, e cada execução grava `geracao_ia`, mesmo com erro. Proposição sem tema não gera notícia, porque `noticia.cod_tema` é obrigatório.

Para medir a centralização dos embeddings:

```bash
flask ia centralizar
RAG_CENTRALIZAR=1 flask ia reconstruir
RAG_CENTRALIZAR=1 flask ia medir-busca
flask ia reconstruir               # volta ao índice sem centralização
```

## Problema conhecido

`pytest --cov=desperta.coletor` falha dentro do SQLAlchemy (`TypeError` em `_cache_key_cy`). Use o comando oficial, `invoke test`, que mede com `--cov=desperta`.
