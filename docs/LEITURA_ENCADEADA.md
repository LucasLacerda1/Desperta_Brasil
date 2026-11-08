# Leitura encadeada: a Roberta lê a PEC por partes e leva a própria interpretação adiante

Nov 7, 2026 · @Computeiros

A ideia do grupo é a Roberta ler a PEC em pedaços e, a cada pedaço novo, usar a interpretação que ela mesma fez dos anteriores. Dá para fazer **sem treino**, cabe no limite de 512 tokens e entra como um modo novo de leitura nos cinco testes do `ESTUDO_ROBERTA_X_GRUPO.md`. Não muda nada no portal.

## O ponto de partida: ela não escreve

A Roberta só lê (seção "O que é a Roberta" do estudo). A "interpretação" dela não pode ser um texto escrito por ela. Ela tem duas saídas que servem:

- **O vetor do pedaço:** 768 números, a média dos vetores dos tokens.
- **O que ela aponta como mais importante:** a frase mais perto do vetor (como no teste A) e as palavras que mais mexem no vetor quando são tiradas (como no teste E).

A memória que passa de um pedaço para o outro é feita dessas escolhas, **em texto**. Assim ela relê as próprias conclusões na língua que conhece, sem precisar de treino.

## Como funciona

**Os pedaços** são os blocos da planta base: a parte normativa (blocos 1 a 6) e cada parágrafo da justificação (§1 a §7). São 8 pedaços, já separados por linha em branco no `PEC_319_2004.txt`. A PEC tem cerca de 600 palavras, então todos ficam bem abaixo de 400 tokens.

Para cada pedaço, em ordem:

1. **Entrada:** `<s> memória </s></s> pedaço </s>`, montada à mão com os números dos tokens: `[0] + memoria + [2, 2] + pedaco + [2]`. A memória usa até 100 tokens e o pedaço até 400, total de 504 (cabe nos 510). No primeiro pedaço, a memória fica vazia.
2. **Leitura:** uma passada da Roberta. O vetor do pedaço é a média **só dos tokens do pedaço**. A memória entra na atenção, mas fica fora da média, para o vetor dizer "este pedaço lido à luz do que veio antes", e não repetir a memória.
3. **Interpretação do pedaço:**
    - a frase do pedaço mais perto do vetor do pedaço (vetor da frase = média dos tokens dela na mesma passada);
    - as 3 palavras que mais mudam o vetor quando são tiradas (relendo com a mesma memória).
4. **Nova memória:** a frase escolhida entra no fim da memória, e as palavras entram numa linha `Palavras: …` (no máximo 5, as de maior peso). Se passar de 100 tokens, sai a frase da memória mais longe do **vetor acumulado** (média dos vetores dos pedaços lidos até ali). Uma frase com mais de 85 tokens é cortada no fim.

Ao final, a interpretação da PEC é a memória final (texto) mais o vetor acumulado. Quem decide o que fica na memória são os vetores dela, não nós.

## Como saber se ajuda

Os cinco testes rodam em três modos, com a mesma PEC e a mesma interpretação do grupo:

| Modo | O que é | Para quê |
| --- | --- | --- |
| Trechos soltos | Como o portal faz hoje: 400 tokens, 50 de sobreposição, sem memória | Linha de base |
| Encadeada | A mecânica acima | O que queremos testar |
| Encadeada com memória sorteada | Igual, mas a memória vem de frases sorteadas da PEC | Mostra se é a interpretação dela que ajuda, e não só "ter texto a mais" |

Se a encadeada empatar com a de memória sorteada, o ganho vem do texto extra, não da interpretação dela. Como no estudo, comparar **posições**, não o valor da similaridade (o problema do 0,95 a 0,99).

**Ajuste no teste A:** com só 8 pedaços, acertar 5 de 5 por sorte fica fácil (5 × 5 / 8 ≈ 3). Nos dois modos encadeados, a unidade do teste A passa a ser a **frase** (cerca de 20 na PEC, sorteio ≈ 1,25). O grupo marca as 5 frases mais importantes em vez de 5 trechos.

## Riscos

- **Erro que se propaga:** uma frase ruim escolhida no começo segue até o fim. A tabela por pedaço (abaixo) mostra onde isso acontece.
- **Peso do começo:** a parte normativa entra primeiro e tende a ficar na memória. Na PEC isso faz sentido, porque é onde está a mudança, mas fica anotado. Um teste extra, opcional: ler de trás para frente e ver se a interpretação final muda.
- **Custo:** cerca de 600 releituras curtas para o peso das palavras, mais 8 leituras. Na RTX 4050, poucos minutos no máximo (estimativa).

## O que não fazer agora

- **Passar o vetor como um "token falso" de entrada** (`inputs_embeds`): ela nunca viu um vetor de saída na entrada, então sem treino o efeito é imprevisível.
- **Memória treinada:** a versão "de verdade" da ideia são alguns tokens especiais cuja saída vira a entrada do pedaço seguinte, e a rede aprende o que guardar ([Recurrent Memory Transformer](https://arxiv.org/abs/2207.06881), Bulatov et al., NeurIPS 2022; aplicado a um encoder do tipo BERT em [Bulatov et al., 2023](https://arxiv.org/abs/2304.11062)). Precisa de treino e de um objetivo próprio, então só entra depois do treino 1 do estudo e **com a confirmação do grupo**.

## O que muda no código

- **Novo:** `scripts/analise_pec/leitura_encadeada.py`, fora do pacote `desperta`. Carrega o modelo como o `desperta/ia/embeddings.py`, mas com a média própria descrita no passo 2.
- **Texto:** `PEC_319_2004.txt` deste pacote (texto dos artigos + justificação, 8 pedaços separados por linha em branco).
- **Relatório:** uma tabela por pedaço (memória que entrou, frase escolhida, 3 palavras) e os cinco testes nos três modos.
- **Não treinar nada.** A ordem do estudo continua valendo.

## Nota da instalação no projeto (07/11/2026)

- No projeto, `instance/analise_pec/PEC_319_2004.txt` continua sendo a versão com códigos (EMENTA, P1 a P4, J1 a J7), que o `interpretacao_modelo.json` usa para citar trechos. Os 8 pedaços deste plano ficam em `instance/analise_pec/PEC_319_2004_pedacos.txt`. O texto é o mesmo: pedaço 1 = EMENTA + P1 a P4; pedaços 2 a 8 = J1 a J7.
