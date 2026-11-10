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

### Agendamento (RF02)

As rotinas rodam sozinhas por timers de usuário do `systemd` (decisão 23.11 do `CLAUDE.md`). Cada timer chama `flask coletar agendada <rotina>`, que faz a coleta e, sob a mesma trava, indexa o que mudou (`flask ia indexar`) e escreve os rascunhos novos (`flask ia gerar-novos`).

| Rotina | Quando | Se outra coleta estiver rodando | PC desligado na hora |
|---|---|---|---|
| `horaria` | de hora em hora, no minuto 5 | não roda (fica para a hora seguinte) | não recupera |
| `diaria` | todo dia, 3h30 | espera até 3 horas | roda quando o PC ligar |
| `semanal` | domingo, 4h30 | espera até 3 horas | roda quando o PC ligar |
| `mensal` | dia 1, 5h30 | espera até 3 horas | roda quando o PC ligar |

```bash
invoke agendar        # grava os arquivos em ~/.config/systemd/user e liga os 4 timers
invoke agenda         # próximas execuções
invoke desagendar     # desliga os timers (a coleta em andamento continua até o fim)
tail -f instance/agendador.log                        # o que cada execução fez
flask coletar agendada horaria --sem-ia               # o mesmo à mão, só a coleta
python scripts/agendador/agendador.py mostrar         # os arquivos do systemd, sem instalar
```

Os caminhos dos arquivos do `systemd` vêm da pasta do projeto e do Python do `.venv`, então o mesmo comando serve no servidor (21.4). Os timers de usuário só rodam com o usuário logado; para rodar sem login (servidor), use `loginctl enable-linger <usuario>`. Sem a RoBERTaLexPT (pendrive fora), a coleta e os rascunhos continuam, só com a busca por palavras, e a indexação fica para a próxima vez (21.3).

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
flask ia gerar-novos --simular     # o que seria gerado com os fatos dos últimos dias, sem gravar nada
flask ia gerar-novos               # um rascunho para cada fato novo; --dias 7, --limite 50, --refazer-erros
```

Depois do download, use `HF_HUB_OFFLINE=1` no `.env`: o modelo roda sem internet. Sem as dependências de IA, os testes de `tests/test_ia.py` são pulados. Depois de cada coleta, rode `flask ia indexar`.

A RoBERTaLexPT-base fica em `ROBERTA_DIR`, numa pasta simples, sem os links do cache do Hugging Face. Sem essa pasta (pendrive desconectado), `indexar`, `buscar` e `medir-busca` param com uma mensagem clara e um aviso no log, e `gerar` usa só a busca por palavras. O coletor, a API e os testes não dependem dela.

`IA_DISPOSITIVO` escolhe onde o modelo roda: `auto` (a placa NVIDIA se existir, senão o processador), `cuda` (para com erro sem a placa) ou `cpu`. O dispositivo de cada execução fica em `log_sistema`.

A busca é híbrida: junta o índice vetorial (`vec_trecho`) e o de palavras (`trecho_fts`) por Reciprocal Rank Fusion. O modo `hibrida_peso` faz o mesmo com a lista vetorial pesando `RAG_PESO_VETOR` (padrão: 0,5). Os índices não são modelos SQLAlchemy nem contam entre as 32 tabelas. Só as tramitações dos últimos `RAG_TRAMITACAO_DIAS` dias (padrão: 90) viram trecho.

Em `tests/dados/consultas_busca.json`, cada consulta pode ter a lista `fora_do_assunto`, com as proposições marcadas à mão, e o `medir-busca` conta quantas aparecem nos 8 primeiros.

As notícias são escritas pelo `GERADOR` (padrão: `frases`). O `GeradorFrases` usa frases prontas, sem IA: todo número, nome e data vem dos registros do banco. Votação de requerimento ou de redação final não vira "Câmara aprova projeto". Toda notícia entra como `rascunho`, e cada execução grava `geracao_ia`, mesmo com erro. Proposição sem tema não gera notícia, porque `noticia.cod_tema` é obrigatório.

O `gerar-novos` (item 4 da 22.10) procura os fatos dos últimos `GERACAO_JANELA_DIAS` dias (padrão: 3) e escreve um rascunho para cada: toda votação, no Plenário ou em comissão, que afeta um tipo acompanhado; toda mudança de situação depois do dia da apresentação; e toda proposição nova dos tipos acompanhados. Votações vêm primeiro. Ele pula o que já tem geração (inclusive notícia rejeitada pela equipe e geração com erro, que só volta com `--refazer-erros`), a proposição sem tema e o que ainda está pendente na coleta, que entra na próxima execução. Rodar de novo não duplica nada, e cada execução deixa um resumo em `log_sistema` (`acao = gerar_novos`). Rode depois da coleta e do `flask ia indexar`; `invoke gerar-novos` faz o mesmo.

Para medir a centralização dos embeddings:

```bash
flask ia centralizar
RAG_CENTRALIZAR=1 flask ia reconstruir
RAG_CENTRALIZAR=1 flask ia medir-busca
flask ia reconstruir               # volta ao índice sem centralização
```

## Análise da PEC com a Roberta original (estudo, fora do portal)

```bash
python scripts/analise_pec/rodar.py --rodada base        # cada frase lida sozinha
python scripts/analise_pec/rodar.py --rodada encadeada   # leitura encadeada (docs/LEITURA_ENCADEADA.md)
python scripts/analise_pec/rodar.py --rodada contexto    # + contexto inicial
python scripts/analise_pec/rodar.py --rodada planta      # + bloco da planta (leitura prévia)
python scripts/analise_pec/rodar.py --rodada controle --camadas nada --sementes 5
python scripts/analise_pec/rodar.py --rodada votacao --leituras 1000   # média de 1.000 leituras com dropout ligado
python scripts/analise_pec/rodar.py --rodada rag        # contexto = trechos de outras proposições achados pela busca híbrida
python scripts/analise_pec/rodar.py --rodada rag --whitening   # qualquer rodada pode comparar os vetores depois do whitening (calculado sobre os trechos do RAG)
python scripts/analise_pec/repeticoes.py --vezes 1000          # as rodadas repetidas com dropout: média e intervalo de 95% (cerca de 6 h na RTX 4050; --continuar retoma)
python scripts/analise_pec/repeticoes.py --vezes 1000 --consenso lucas caio rhuan   # idem, com nota também contra as frases de pelo menos 2 dos 3 (--minimo)
invoke analise-pec --rodada base                         # o mesmo pelo Invoke
python scripts/analise_pec/experimentos.py               # grade: camadas x leituras x centralização x métodos, com correlações
```

Lê `instance/analise_pec/` (frases, planta e as interpretações `interpretacao_<PEC>_<nome>.json`), usa a RoBERTaLexPT de `ROBERTA_DIR` e grava `resultado.json` e `relatorio.md` em `instance/analise_pec/rodadas/<data>_<rodada>/`. Não treina nada e não grava no banco. As notas dos testes ficam em `scripts/analise_pec/avaliacao.py`, testadas sem o modelo em `tests/test_analise_pec.py`.

## Tema pelo protótipo (estudo, fora do portal)

```bash
python scripts/temas_prototipo/avaliar.py
python scripts/temas_prototipo/aprofundado.py   # bateria: intervalos de confiança, validação no tempo, robustez e confiança
```

Avalia, nas proposições com tema oficial, se o tema sai certo comparando a ementa com o protótipo de cada tema (a média das ementas do tema), montado sem a proposição avaliada. Compara a RoBERTaLexPT original, centralizada e com whitening (Su et al., 2021), a busca por palavras (TF-IDF com pares de palavras), os vizinhos mais parecidos (kNN, 25 vizinhos) e a junção dessas leituras, contra o acaso e os temas mais comuns. A melhor forma (vizinhos e protótipos, com a Roberta e as palavras) acerta o tema em 87,9% das proposições no 1º lugar e em 96,9% entre os 3 primeiros. Também lista temas sugeridos para as proposições acompanhadas sem tema, sem gravar nada no banco. Resultado em `instance/analise_temas/<data>/`. As contas ficam em `scripts/temas_prototipo/prototipos.py`, testadas em `tests/test_temas_prototipo.py`.

## Verificação e testes de persistência do banco

```bash
flask banco verificar --relatorio instance/verificacao-banco.md            # só lê: estrutura, integridade e coerência
flask banco testar-persistencia --relatorio instance/persistencia.md       # grava e relê numa cópia; o banco original não muda
invoke verificar-banco                                                     # o mesmo pelo Invoke
invoke testar-persistencia
```

A verificação confere integridade do arquivo, chaves estrangeiras, as 32 tabelas, a versão do esquema, o modo WAL, os votos gravados contra o placar escrito pela Câmara, as referências sem FK (`trecho_rag`, `noticia_fonte`), os índices de busca, os embeddings, as datas de início e fim, os hashes e as coletas interrompidas.

Os testes de persistência rodam numa cópia, feita pelo backup do SQLite: ida e volta (gravar, fechar, reabrir e ler igual), upsert sem duplicar com dados reais, atualização no lugar, erro num registro sem derrubar os outros, restrições e cascata. A cópia é apagada no fim, a não ser com `--manter-copia`.

## Ver o banco no navegador (só desenvolvimento)

O Datasette (licença Apache 2.0) abre o banco no navegador, em **modo só leitura**: dá para navegar por todas as tabelas, filtrar, ordenar e rodar consultas `SELECT`. Não faz parte do portal.

```bash
pip install -e ".[ver]"                                   # uma vez
invoke ver-banco                                          # abre http://127.0.0.1:8001 com instance/desperta.db
invoke ver-banco --banco instance/desperta-amostra.db     # a amostra de 15 MB
```

A **visão geral** (`http://127.0.0.1:8001/visao-geral`) mostra numa página só os números principais, o período dos dados, as proposições por tipo e tema, a situação das votações, o que a Câmara não informou, as coletas e os erros do log; cada número é consultado na hora, pelo complemento `datasette-template-sql`. A página fica em `scripts/ver_banco/templates/pages/visao-geral.html`.

A página do banco tem um menu com **busca rápida** (proposição e votação pelo id, deputado pelo nome, palavra na ementa ou no despacho e palavras no que a Roberta lê), as **tabelas agrupadas por assunto** e **15 consultas prontas** (contagem das tabelas, votações secretas, situação das votações, placar por partido, uma proposição completa, votações de uma proposição, votos de um deputado, proposições por tema, campos não informados pela Câmara, pendentes, últimas coletas, erros do log, o que a Roberta lê e uma amostra do índice vetorial). Nas tabelas, os ids ligados aparecem com o nome (deputado, partido, órgão, tema), há filtros rápidos no topo, a ordem padrão é do mais recente e as colunas principais têm explicação. A configuração é montada por `scripts/ver_banco/montar_metadata.py`, que o `invoke ver-banco` roda antes de abrir. Com a parte de IA instalada, a extensão sqlite-vec é carregada sozinha.

## Problema conhecido

`pytest --cov=desperta.coletor` falha dentro do SQLAlchemy (`TypeError` em `_cache_key_cy`). Use o comando oficial, `invoke test`, que mede com `--cov=desperta`.
