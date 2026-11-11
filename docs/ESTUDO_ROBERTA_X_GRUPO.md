# Roberta x grupo: como a rede lê uma PEC

Nov 3, 2026 · @Computeiros

## O que é a Roberta, em resumo

A RoBERTaLexPT-base é uma rede neural que **lê** português jurídico e transforma texto em números, mas **não escreve** texto sozinha. Ela foi feita por Eduardo Garcia e colegas (UFG e UFRPE) e publicada no congresso PROPOR 2024.

- **Tipo de rede:** só encoder (a metade "leitora" de um Transformer), arquitetura RoBERTa-base.
- **Tamanho:** 12 camadas, 12 cabeças de atenção, vetores de 768 números, cerca de **124,7 milhões de parâmetros** (pesos).
- **O que ela aprendeu:** a adivinhar palavras escondidas ("preencher lacunas"). Em cada frase do treino, 15% dos pedaços eram escondidos e ela tinha que acertar quais eram.
- **Com que textos:** cerca de 65 bilhões de tokens vistos no treino, de dois conjuntos. O **LegalPT** (125 GiB de decisões do STF, STJ, TCU, tribunais estaduais, debates do Parlamento de Portugal e mais) e o **CrawlPT** (português geral da internet: brWaC, CC100 e OSCAR). Metade dos documentos jurídicos era repetida e foi removida antes do treino.
- **Onde ela é boa:** classificar frases jurídicas e achar nomes de pessoas, leis, órgãos e datas em textos legais. No teste PortuLex ela fez 85,41 de média, mais que modelos bem maiores como o BERTimbau-large (84,60).
- **Onde ela não foi testada:** comparar o sentido de duas frases. O artigo não mede isso. É por isso que, no nosso portal, a similaridade dá 0,95 a 0,99 para quase tudo (relatório da Fase 3, parte 1).
- **Licença:** CC-BY-4.0. Podemos usar, treinar e modificar, desde que citemos os autores.

## Como a Roberta lê um texto, parte por parte

A Roberta lê em **pedaços de palavra** (subpalavras), não em palavras inteiras nem letra por letra, e lê no máximo **512 tokens de uma vez**. O caminho dentro do código tem cinco partes.

### A versão que o projeto usa

O projeto usa a versão atual da branch `main` de `eduagarcia/RoBERTaLexPT-base`, commit [9dea308](https://huggingface.co/eduagarcia/RoBERTaLexPT-base/commits/main) ("Adding safetensors variant", maio de 2024). O código não fixa outra versão e exige o `model.safetensors`, que só existe a partir desse commit. Os pesos são os do treino de 62.500 passos (commit f7d589f, "rollback to 62500 steps").

| Arquivo da versão | Tamanho | O que diz sobre os tokens |
| --- | --- | --- |
| `vocab.json` | 964 kB | A lista de tokens e o número de cada um |
| `merges.txt` | 522 kB | As regras de junção do BPE, em ordem |
| `tokenizer_config.json` | 1,2 kB | `RobertaTokenizer`, limite de 512, `add_prefix_space: false` |
| `special_tokens_map.json` | 772 bytes | Os 7 tokens especiais |
| `config.json` | 642 bytes | Vocabulário de 50.265 e 514 posições |

Não há `tokenizer.json` nessa versão: o Transformers monta o tokenizador a partir do `vocab.json` e do `merges.txt`.

### 1. Tokenizador: corta o texto em tokens

- **Tipo de token:** BPE em bytes (*byte-level BPE*), o mesmo método do RoBERTa original. A classe é a `RobertaTokenizer`.
- **Vocabulário:** 50.265 tokens, aprendidos nos próprios textos jurídicos e gerais. Palavra comum vira 1 token; palavra rara é quebrada em pedaços.
- **Nada fica "desconhecido":** no pior caso, ela cai para bytes. Uma letra com acento ocupa 2 bytes, por isso palavras raras com ç e ã podem virar mais pedaços.
- **O espaço faz parte do token:** "lei" no início da frase e " lei" depois de um espaço são tokens diferentes. Nos arquivos, o espaço aparece como `Ġ`.
- **Maiúscula importa:** "Congresso" e "congresso" são tokens diferentes.
- **Tokens especiais:** `<s>` (nº 0, início), `<pad>` (nº 1, enchimento), `</s>` (nº 2, fim), `<unk>` (nº 3) e `<mask>` (a lacuna).

Tokens conferidos no `vocab.json` dessa versão. Cada palavra abaixo é **um token só**, com o espaço antes:

| Token no vocab.json | Como se lê | Número |
| --- | --- | --- |
| `<s>` | início | 0 |
| `<pad>` | enchimento | 1 |
| `</s>` | fim | 2 |
| `<unk>` | desconhecido | 3 |
| `Ġart` | " art" | 85 |
| `ĠLei` | " Lei" | 96 |
| `ĠFederal` | " Federal" | 159 |
| `Ġlei` | " lei" | 329 |
| `ĠNacional` | " Nacional" | 427 |
| `ĠConstituiÃ§Ã£o` | " Constituição" | 618 |
| `ĠCongresso` | " Congresso" | 2369 |

Duas coisas aparecem nessa tabela. "Lei" e "lei" têm números diferentes, porque maiúscula importa. E "ção" aparece como `Ã§Ã£o` porque o arquivo guarda os bytes de cada letra acentuada. O número do `<mask>` e o corte de palavras mais raras, como "demarcação" e "indígenas", não consegui conferir: a página do `vocab.json` só abriu até o token 2998.

### 2. Quantos tokens ela lê

- **Limite:** 512 tokens por vez. A configuração tem 514 posições, mas o RoBERTa reserva 2. Tirando `<s>` e `</s>`, sobram **510 tokens de texto**.
- **Em palavras:** estimativa de 1,3 a 1,6 tokens por palavra em português, ou seja, cerca de 300 a 380 palavras por vez. É uma estimativa: a documentação não traz essa conta.
- **Texto maior:** é cortado. No nosso `desperta/ia/embeddings.py`, o texto é dividido em trechos de até 400 tokens com 50 de sobreposição. Uma PEC inteira (texto + justificação) vira vários trechos.

### 3. Embeddings de entrada: token vira vetor

Cada token vira um vetor de 768 números, tirado de uma tabela de 50.265 linhas. A posição do token na frase tem o seu próprio vetor, que é somado ao do token. Depois vem uma normalização (LayerNorm). A Roberta não usa "frase A / frase B" como o BERT.

### 4. As 12 camadas: cada token olha para os outros

Cada camada faz duas coisas:

1. **Atenção com 12 cabeças:** cada token olha para todos os outros, para a esquerda e para a direita, e mistura o que for útil. É assim que "terras" perto de "indígenas" ganha outro sentido.
2. **Rede feed-forward:** cada vetor passa por 768 → 3.072 → 768 números, com a função GELU.

As duas partes somam o resultado ao que entrou (ligação residual) e normalizam de novo.

### 5. Saída: o que sai do outro lado

- **Um vetor de 768 números por token**, que já depende do contexto (`last_hidden_state`). É o que o portal usa.
- **No portal:** fazemos a média dos vetores de todos os tokens do trecho e normalizamos (`embeddings.py`). Sai 1 vetor por trecho, guardado no sqlite-vec.
- **Cabeça de lacunas:** transforma o vetor de um `<mask>` em 50.265 notas, uma para cada token do vocabulário. A maior nota é o palpite. Ela reaproveita a tabela da parte 3.

### Onde ficam os 124,7 milhões de parâmetros

| Parte | Parâmetros | % |
| --- | --- | --- |
| Tabela de tokens (50.265 × 768) | 38,6 milhões | 31% |
| Posições e normalização | 0,4 milhão | 0,3% |
| 12 camadas (7,09 milhões cada) | 85,1 milhões | 68% |
| Cabeça de lacunas (sem contar a tabela reaproveitada) | 0,6 milhão | 0,5% |
| **Total** | **124,7 milhões** |  |

Conta feita a partir do `config.json` do modelo, e bate com os 124,7 milhões do Hugging Face.

## Que treinos dá para fazer

Para esta análise, recomendo medir a Roberta **sem treino** primeiro e depois **continuar o treino de lacunas com textos da Câmara**, repetindo a mesma análise para ver o antes e o depois. É o treino mais barato, não precisa de rótulos e cabe na RTX 4050.

| Treino | O que ensina | Do que precisa | Custo na RTX 4050 | Para esta análise |
| --- | --- | --- | --- | --- |
| 0. Nenhum (linha de base) | Nada: mede como ela lê hoje | Só a PEC | Minutos | **Sempre primeiro** |
| 1. Continuar o treino de lacunas | Vocabulário e jeito de escrever da Câmara (PEC, CCJC, "dá nova redação") | Textos sem rótulo: ementas e inteiros teores do banco | Algumas horas (estimativa) | **Recomendado** |
| 2. Treino de semelhança (contrastivo) | Aproximar textos que dizem a mesma coisa, o que ataca o problema do 0,95 a 0,99 | Centenas a milhares de pares (ex.: ementa e explicação simples) | 1 a 3 horas (estimativa) | Opcional, depois do 1 |
| 3. Classificar temas | Dar o tema oficial a partir do texto | Temas de `proposicao_tema` | Cerca de 1 hora (estimativa) | Fora do MVP (seção 8 do guia); só como experimento |
| 4. Roberta escritora | Escrever título e resumo | 5.000 pares ou mais | Muitas horas | Já é a Fase 3b, não entra aqui |

Cuidados que valem para qualquer treino:

- **A PEC escolhida fica fora do treino.** Senão a Roberta "decora" a resposta e a comparação perde o sentido.
- **O modelo treinado é uma cópia.** A RoBERTaLexPT original no `ROBERTA_DIR` não muda, e o portal continua usando ela até o grupo decidir.
- **O treino 2 mexe numa decisão do guia:** a 19.2 diz para só treinar para busca se nenhuma opção passar de 70%. Aqui ele seria só um experimento, sem entrar no portal.
- **Os tempos são estimativas.** O valor real depende da memória da 4050 e da quantidade de texto; anoto no relatório.

## Como comparar a leitura da Roberta com a do grupo

A proposta são **cinco testes** sobre a mesma PEC, cada um com uma nota que dá para comparar com a do grupo, com um sorteio e com a busca por palavras. A Roberta não tem opinião: o que medimos é o que fica perto do quê nos vetores dela e quais palavras ela acha prováveis.

| Teste | Pergunta | Como a Roberta responde | Com o que comparamos | Nota |
| --- | --- | --- | --- | --- |
| A. Trechos centrais | Quais partes da PEC são as mais importantes? | Ordena os trechos pela proximidade com o vetor da PEC inteira | Os 5 trechos que o grupo marcou | Quantos dos 5 do grupo estão nos 5 dela (sorteio dá cerca de 5 × 5 / nº de trechos) |
| B. Resumo → texto | Cada frase do nosso resumo fala de qual parte da PEC? | Acha o trecho mais próximo de cada frase | O trecho que o grupo diz ser o certo; e a busca por palavras (FTS5) | % de frases ligadas ao trecho certo |
| C. Resumo → PEC certa | Lendo só o nosso resumo, ela acha a PEC certa entre outras? | Compara o resumo com a PEC escolhida e com 20 a 50 outras PECs do banco | A posição da PEC certa | Posição (1º é o ideal) |
| D. Temas | De que assunto a PEC trata? | Compara a PEC com o nome de cada tema oficial | Os temas do grupo e os temas oficiais da Câmara (`proposicao_tema`) | Quantos temas coincidem nos 3 primeiros |
| E. Lacunas e palavras-chave | Ela entende o contexto? Que palavras pesam mais? | Escondemos 10 palavras-chave (`<mask>`) e vemos os 5 palpites; tiramos cada palavra e medimos quanto o vetor muda | As 10 palavras-chave do grupo | % de palavras acertadas nos 5 palpites; palavras em comum |

Como ler os resultados sem se enganar:

- **Usar posições, não o valor da similaridade.** Como os valores ficam entre 0,95 e 0,99, só a ordem diz alguma coisa.
- **Sempre ter um adversário:** o sorteio mostra o que seria acertar por sorte, e a busca por palavras mostra se a Roberta acrescenta algo além de palavras iguais.
- **Medir o grupo também:** se 2 ou 3 pessoas preencherem a interpretação separadas, dá para ver quanto elas concordam entre si. Esse é o teto: não dá para cobrar da Roberta mais do que as pessoas concordam.
- **Antes e depois do treino:** os cinco testes rodam na Roberta original e na Roberta treinada (seção anterior), com a mesma PEC e a mesma interpretação do grupo.

O código fica em `scripts/analise_pec/`, fora do pacote `desperta`, e não muda nada no portal. Ele lê a PEC e as outras proposições do banco, roda na RTX 4050 e gera um relatório com uma tabela por teste. O banco só guarda a ementa e o link do inteiro teor, então o texto completo da PEC vem do PDF da Câmara (o script baixa, ou o grupo cola o texto num arquivo).

## Qual PEC e o que o grupo entrega

Sugiro a **PEC 319/2004** (demarcação de terras indígenas pelo Congresso), porque já está no banco, é curta e tem um assunto fácil de explicar. Ela aparece no `tests/dados/consultas_busca.json` junto com a **PEC 275/2004**, que trata do mesmo assunto. Isso permite um teste a mais: ver se a Roberta separa duas PECs quase iguais.

O grupo pode escolher outra. Se ela não estiver no banco, o coletor busca antes.

### A interpretação do grupo

Escrever **antes de ver qualquer resultado da Roberta**, num arquivo `interpretacao_grupo.json` (eu preparo o modelo do arquivo):

1. **Resumo** em 3 a 5 frases, em linguagem simples.
2. **Os 5 trechos mais importantes** do texto da PEC, em ordem.
3. **Até 3 temas**, da lista oficial de temas da Câmara.
4. **10 palavras-chave** que aparecem no texto.
5. **Para cada frase do resumo,** o trecho da PEC de onde ela veio.

Se 2 ou 3 pessoas fizerem isso separadas, dá para medir quanto o grupo concorda (seção anterior).

### Ordem

1. O grupo escolhe a PEC e preenche a interpretação.
2. Eu escrevo o `scripts/analise_pec/` numa branch nova a partir da `fase-3-rag`.
3. O Lucas roda no PC (este ambiente não consegue baixar o modelo do Hugging Face).
4. Relatório com os cinco testes na Roberta original.
5. **O grupo confirma o treino.**
6. Treino na RTX 4050, cinco testes de novo, relatório do antes e depois.

## Fontes estudadas

- [Ficha do modelo no Hugging Face](https://huggingface.co/eduagarcia/RoBERTaLexPT-base): arquitetura, dados, hiperparâmetros, notas no PortuLex e licença.
- [config.json](https://huggingface.co/eduagarcia/RoBERTaLexPT-base/raw/main/config.json) e [tokenizer\_config.json](https://huggingface.co/eduagarcia/RoBERTaLexPT-base/raw/main/tokenizer_config.json): vocabulário, posições e tokens especiais.
- [Artigo PROPOR 2024](https://aclanthology.org/2024.propor-1.38/) (Garcia et al., p. 374–383): corpora, deduplicação, treino e resultados.
- [Dissertação de mestrado de Eduardo Garcia](https://repositorio.bc.ufg.br/tede/items/4db45f23-2e31-4a24-b80a-6f4dfdf5b5d3) (UFG, 2024).
- [Repositório dos autores](https://github.com/eduagarcia/roberta-legal-portuguese): só o README foi lido; ele não mostra scripts de treino.
- [Documentação do RoBERTa no Transformers](https://huggingface.co/docs/transformers/main/en/model_doc/roberta): classes, tokenizador e uso como decoder.
- Código do projeto: `desperta/ia/embeddings.py` (branch `fase-3-rag`), `CLAUDE.md` (seções 16 a 21) e `docs/TREINAR_ROBERTA_ESCRITORA.md`.
