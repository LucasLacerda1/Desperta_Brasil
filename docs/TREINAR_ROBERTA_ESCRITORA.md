# Desperta Brasil — treinar a RoBERTaLexPT para escrever (Fase 3b)

> Para o Claude Code. Coloque em `docs/TREINAR_ROBERTA_ESCRITORA.md` e peça: "Leia docs/TREINAR_ROBERTA_ESCRITORA.md e comece pela etapa 1".
> Escrito em 01/11/2026. A etapa 1 pode começar já; as outras vêm depois dos passos da 16.6 do `CLAUDE.md` (ver 19.4). Decisão do grupo: a própria RoBERTaLexPT deve aprender a escrever as notícias, em vez de usar um modelo de linguagem pronto.

## 0. O que é possível e o que não é

A RoBERTaLexPT-base é um **encoder**: lê texto e gera vetores. Ela não tem a parte que escreve palavra por palavra. Para ela escrever, é preciso montar um modelo **encoder-decoder** em que:

- o **encoder** é a RoBERTaLexPT (já sabe português jurídico);
- o **decoder** também começa com os pesos da RoBERTaLexPT, mais camadas novas de "atenção cruzada" que nascem sem treino;
- o conjunto é treinado com pares "dados da Câmara → texto de notícia".

Essa técnica é conhecida como *warm-start* (artigo de Rothe, Narayan e Severyn, 2020, "Leveraging Pre-trained Checkpoints for Sequence Generation Tasks", que fez o BERT2BERT e o RoBERTa2RoBERTa). No Hugging Face ela é feita com `EncoderDecoderModel.from_encoder_decoder_pretrained(...)`. O modelo resultante tem cerca de 250 a 280 milhões de parâmetros.

**Limites que o grupo aceitou:**
- O treino precisa de **placa de vídeo (GPU)**. No processador do PC levaria semanas. **Usar a GPU principal do PC do Lucas, a NVIDIA RTX 4050** (seção 3.0 e seção 20 do `CLAUDE.md`). Google Colab ou Kaggle só se a 4050 não der conta.
- O modelo aprende só o que os exemplos mostram. São necessários **milhares de pares** de exemplo.
- Modelos desse tamanho escrevem bem textos **curtos**. Por isso a "Roberta escritora" vai escrever **título e resumo** (2 ou 3 frases, os campos `titulo` e `resumo` de `noticia`). O `corpo` da notícia é montado pelo código com os dados do banco (seções 1 e 5).
- Pode inventar fatos. Por isso toda notícia continua entrando como `rascunho` e passa pelo editor (RF06), e a avaliação (seção 4) conta erros de fato.

**Plano B obrigatório:** antes do treino, implementar o `GeradorFrases` (seção 1), que escreve com frases prontas. O MVP sai com ele se a Roberta escritora não ficar boa a tempo. A troca é só de configuração, porque `desperta/ia/gerador.py` já tem a interface.

## 1. Etapa 1 — `GeradorFrases` (plano B, no `fase-3-rag`)

Em `desperta/ia/gerador.py`, uma classe `GeradorFrases` que segue a mesma interface do `GeradorFalso`:
- Recebe os trechos recuperados pelo RAG e os registros de origem (proposição, votação, tramitação).
- Monta `titulo`, `resumo` e `corpo` com modelos de frase em português simples. Exemplos:
  - Votação aprovada: "Câmara aprova {tipo_extenso} que {ementa_simplificada}" / "O Plenário aprovou nesta {dia_semana} o {sigla} {numero}/{ano}… Foram {sim} votos a favor e {nao} contra."
  - Proposição nova: "Projeto propõe {ementa_simplificada}" / "O {sigla} {numero}/{ano}, de autoria de {autor}, foi apresentado em {data}…"
  - Mudança de situação: "{sigla} {numero}/{ano} avança na Câmara" / "A proposta foi {situacao_minuscula} na {orgao}…"
- `ementa_simplificada`: só regras simples (tirar "Altera a Lei nº…", "e dá outras providências", começo com verbo no presente). Sem IA.
- Nunca escreve um número, nome ou data que não esteja nos registros.
- Grava `geracao_ia` (`modelo_geracao = "frases-v1"`), `geracao_trecho` e `noticia_fonte`, e a notícia como `rascunho`, como manda a 6.1 do `CLAUDE.md`.
- `GERADOR` em `Config` (variável de ambiente): `falso`, `frases` ou `roberta`. Padrão: `frases`.
- Testes para os três modelos de frase e para "nunca inventa": todo número do texto precisa existir nos dados de entrada.

## 2. Etapa 2 — dados de treino (pares)

### 2.1 De onde vêm os textos de notícia
A fonte natural é a **Agência Câmara de Notícias** (`camara.leg.br/noticias`), que escreve notícias sobre as proposições em linguagem simples.
- **Antes de coletar,** conferir e registrar no relatório: o `robots.txt` do site e os termos de uso/reprodução da Agência Câmara. Se não for permitido coletar ou usar para treino, **parar e avisar o grupo**. Não contornar bloqueios.
- Coletar devagar (no máximo 1 página a cada 2 segundos), com um `User-Agent` que identifique o projeto acadêmico.
- Os textos da Agência servem **só para treino**. Nunca publicar no portal nem guardar no banco do portal.

### 2.2 Como montar cada par
- **Ligar notícia a proposição:** procurar no texto padrões como `PL 1234/2024`, `PEC 45/2019`, `projeto de lei 1234/24`. Se a notícia cita mais de uma, usar a primeira citada no título ou no primeiro parágrafo.
- **Entrada (o que a Roberta lê):** texto montado do banco, até 512 tokens, sempre na mesma ordem: tipo e número, ementa, autor principal, situação, últimas tramitações (data, órgão, despacho curto) e, se houver votação perto da data da notícia, o resultado e o placar.
- **Saída (o que a Roberta aprende a escrever):** título da notícia + primeiro parágrafo (o lide), até 128 tokens.
- **Data:** só usar tramitações e votações **até a data da notícia**, para o modelo não "ver o futuro".
- Descartar pares em que a proposição não está no banco ou cuja entrada fica com menos de 30 tokens.

### 2.3 Volume e onde guardar
- Meta: **pelo menos 5.000 pares**; 10.000 a 20.000 é melhor. Se ficar abaixo de 2.000, parar e avisar o grupo antes de treinar.
- Para ter os dados de entrada das notícias antigas, pode ser preciso coletar proposições de anos anteriores com o coletor (só os 5 tipos acompanhados).
- Guardar em `instance/dataset/pares.jsonl` (fora do git), com `{"id", "url_noticia", "data", "proposicao_id", "entrada", "saida"}`.
- Separar por **data**: os 80% mais antigos para treino, 10% para validação e os 10% mais recentes para teste.
- Código da coleta em `scripts/dataset/` (fora do pacote `desperta`, não roda no portal), com comando `invoke dataset`.

## 3. Etapa 3 — treino (na RTX 4050)

### 3.0 Qual GPU usar
- **A GPU do treino é a principal do PC: NVIDIA GeForce RTX 4050.** O notebook tem uma GPU integrada também; ela **não** deve ser usada.
- Antes de treinar, conferir e anotar no relatório: `nvidia-smi` mostra a RTX 4050; `torch.cuda.is_available()` é `True`; `torch.cuda.get_device_name(0)` contém `4050`; memória total de vídeo (`torch.cuda.get_device_properties(0).total_memory`).
- O script **para com erro** se a GPU não for a 4050 ou se o CUDA não estiver disponível. Nunca cair para o processador sem avisar.
- Usar `CUDA_VISIBLE_DEVICES=0` e `device = torch.device("cuda:0")`. No Ubuntu, se `nvidia-smi` não achar a placa, o driver da NVIDIA ou o modo da placa (`prime-select`) precisa de ajuste: **parar e avisar o Lucas**, sem mexer no driver por conta própria.
- O `.venv` hoje tem o PyTorch só para CPU (16.5). Trocar pelo PyTorch com CUDA (decisão 20.2) e registrar no README o comando usado.

### 3.1 Ajustes para caber na memória
A RTX 4050 de notebook costuma ter **6 GB** de memória de vídeo. Conferir o valor real. Com 6 GB:
- `fp16=True` (ou `bf16=True`, que a 4050 suporta), `gradient_checkpointing=True`;
- lote de 4 com `gradient_accumulation_steps=4` (lote efetivo de 16); se faltar memória, lote 2 com acumulação 8;
- entrada até 512 tokens e saída até 128;
- se ainda faltar memória, trocar o otimizador para `adafactor` (do próprio Transformers). Não usar biblioteca fechada.
- Anotar o pico de memória (`torch.cuda.max_memory_allocated()`).

### 3.2 O treino
- O PC fica ligado na tomada, sem suspensão, com boa ventilação. O treino salva checkpoint a cada época e pode continuar de onde parou (`resume_from_checkpoint`).

- Um script `scripts/treino/treinar_roberta_escritora.py` (com `invoke treinar`), que roda no PC do Lucas na RTX 4050 e também em Colab/Kaggle sem mudar o código. Ele:
  1. instala `transformers`, `datasets`, `evaluate` e `rouge_score`;
  2. carrega `instance/dataset/pares.jsonl`;
  3. monta o modelo: `EncoderDecoderModel.from_encoder_decoder_pretrained("eduagarcia/RoBERTaLexPT-base", "eduagarcia/RoBERTaLexPT-base", tie_encoder_decoder=True)`; configura `decoder_start_token_id`, `eos_token_id` e `pad_token_id` com o tokenizer da RoBERTaLexPT;
  4. treina com `Seq2SeqTrainer` na RTX 4050, com os ajustes de 3.1, taxa de aprendizado em torno de 5e-5, 5 a 10 épocas, avaliação por época e parada antecipada pela perda de validação;
  5. gera com `num_beams=4`, `max_new_tokens=128`, `no_repeat_ngram_size=3`;
  6. salva os checkpoints no disco do PC (`instance/treino/`) e o melhor modelo e o tokenizer em `ROBERTA_ESCRITORA_DIR` (padrão `<MODELOS_DIR>/roberta-escritora/`), no PC. A RoBERTaLexPT-base de partida é lida de `ROBERTA_DIR`, que fica no pendrive (seção 21 do `CLAUDE.md`).
- Começar com um treino curto (1 época em 1.000 pares) para conferir se tudo roda, antes do treino longo.
- Anotar no relatório: nome da GPU (precisa ser a RTX 4050), memória de vídeo, pico de memória, horas de treino e perda final.

## 4. Etapa 4 — avaliação

1. **ROUGE-L** no conjunto de teste, comparado com o texto da Agência Câmara. Comparar também com o `GeradorFrases` nos mesmos casos.
2. **Erros de fato (o mais importante):** sortear 50 casos do teste e conferir, um por um, se o texto gerado tem número, nome, data, partido ou resultado que **não está na entrada**. O Claude Code faz a conferência automática (todo número e nome próprio do texto precisa existir na entrada) e marca os suspeitos; o grupo confere à mão.
3. Ler 20 textos e dar nota de 1 a 5 para clareza (feito pelo grupo).

**Critério para a Roberta escritora entrar no portal:** no máximo 2 erros de fato em 50 casos, e clareza média de pelo menos 4,0. Se não passar, o portal fica com o `GeradorFrases`, e a Roberta escritora continua como experimento.

## 5. Etapa 5 — integração (só se passar na avaliação)

- `GeradorRoberta` em `desperta/ia/gerador.py`, com a mesma interface: recebe os dados, monta a entrada no **mesmo formato do treino** (seção 2.2), gera `titulo` e `resumo`; o `corpo` vem do `GeradorFrases`.
- Modelo em `ROBERTA_ESCRITORA_DIR` (padrão `<MODELOS_DIR>/roberta-escritora/`, no PC, fora do git; seção 21 do `CLAUDE.md`), carregado só no módulo de IA, nunca na API Flask (6.1 do `CLAUDE.md`). Ele não depende do pendrive.
- Usa a RTX 4050 quando houver (`IA_DISPOSITIVO`, seção 20 do `CLAUDE.md`) e precisa funcionar também no processador, para um servidor sem placa. Medir o tempo por notícia nos dois.
- Depois de gerar, rodar a conferência automática de fatos da seção 4; se achar número ou nome fora da entrada, gravar a notícia como `rascunho` com um aviso no `noticia_revisao.comentario` para o editor.
- `geracao_ia.modelo_geracao = "roberta-escritora-v1"` e `versao_prompt` com a versão do formato de entrada.
- Créditos: a RoBERTaLexPT tem licença CC-BY-4.0, que permite modificar com atribuição. Citar os autores (Garcia et al., PROPOR 2024) no README e na página "Sobre" do portal.

## 6. Ordem e o que não fazer

Ordem: etapa 1 (plano B) → etapa 2 (dados, numa branch `fase-3b-roberta-escritora`; relatório com volume e licença) → **o grupo confirma** → etapa 3 (treino na RTX 4050 do PC do Lucas) → etapa 4 → etapa 5 se passar.

Não fazer:
- Não treinar no processador nem na GPU integrada: só na RTX 4050.
- Não criar tabelas novas para o dataset: ele fica em arquivo.
- Não publicar nada sem passar pelo editor.
- Não coletar a Agência Câmara se os termos não permitirem.
- Não apagar o `GeradorFrases` depois: ele é a garantia do MVP.

## 7. Relatório de cada etapa

Ao fim de cada etapa, entregar um relatório curto com o que foi feito, números (pares, tempos, ROUGE, erros de fato), o que deu errado e o que o grupo precisa decidir.
