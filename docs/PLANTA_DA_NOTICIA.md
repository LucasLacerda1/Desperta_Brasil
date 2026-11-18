# Planta da notícia do Desperta Brasil

> Decisão 25.18 do `CLAUDE.md` (17/11/2026). Assim como toda PEC segue uma planta (a estrutura que toda PEC tem, `docs/LEITURA_ENCADEADA.md`), toda notícia do portal segue esta planta. Ela vale para quem escreve hoje (o `GeradorFrases`, por regras) e para quem escrever depois (a Roberta escritora, Fase 3b).
>
> O conferidor (`desperta/noticias/planta.py`) mede cada rascunho contra esta planta. **A notícia que passa em tudo é publicada sozinha; a que falha em alguma regra vai para a revisão da equipe**, com a lista do que falhou.

## 1. Os três princípios

1. **Imparcial.** A notícia conta o que aconteceu e quem fez. Não julga, não elogia, não critica. Todo fato é atribuído à Câmara, ao órgão ou ao autor.
2. **Resumida.** O fato vem primeiro, em poucas palavras. O detalhe vem depois, em blocos com título.
3. **Para o brasileiro comum.** Frases curtas, palavras do dia a dia; toda sigla e todo termo da Câmara são explicados.

## 2. Os blocos, nesta ordem

| Bloco | O que entra | Regras |
|---|---|---|
| **Título** | O fato: quem fez o quê, com a sigla da proposição (PL 1234/2024). | De 10 a 120 caracteres; nunca cortado no meio ("…"); sem palavra de opinião. |
| **Parágrafo principal** | Só o fato: quem, o quê, quando. | Até 2 frases e 60 palavras; a sigla do tipo explicada na primeira vez ("o projeto de lei PL 1234/2024"); sem placar, sem situação e sem o que a Câmara não informou; sem palavra de opinião. |
| `## O que propõe` | O objetivo da proposição e a ementa oficial, como fonte; o autor. | A ementa é copiada como a Câmara escreveu e vem marcada como "Ementa oficial". |
| `## Resultado da votação` | Só quando o fato é uma votação: o que foi votado, o resultado e o placar (ou como os votos foram registrados). | Só números da Câmara. |
| `## Onde está na Câmara` | A situação com o nome exato da Câmara e a explicação popular (dicionário aprovado, 25.14), o regime, a apreciação e os últimos passos. | O que a Câmara não informou aparece como "não informado". |
| `## O que a Câmara não informou` | As lacunas, com a prova (endereço da API, campo, valor e data da consulta). | Só o que dá para provar (25.14). |
| `## Atualizações` | Os fatos novos da mesma proposição (notícia viva, 25.16). | A mais recente primeiro; cada uma com a data e o título do fato. |

Fontes, "como a notícia foi feita" (inclusive se foi publicada sozinha ou revisada pela equipe) e as notícias relacionadas vêm da API, fora do texto.

**Boletins e relatórios** (25.5 e 25.17) seguem a mesma regra de título e de parágrafo principal; o corpo é a lista de fatos, cada um com o seu link.

## 3. Palavras que não entram

O título e o parágrafo principal não usam palavras de opinião ou de emoção. A lista fica em `desperta/noticias/planta.py` e o grupo pode aumentar. Exemplos: polêmico, absurdo, histórico, importante, vergonhoso, escândalo, brilhante, péssimo, ótimo, excelente, lamentável, infelizmente, felizmente, finalmente, surpreendente, chocante, polêmica.

Verbos neutros: aprovou, rejeitou, apresentou, votou, mudou, arquivou, enviou. Nunca "conseguiu", "derrubou", "barrou", "emplacou", que dão lado à notícia.

## 4. Quando a notícia vai para a revisão (falta de confiança)

A notícia é publicada sozinha só se:

1. passa em todas as regras dos blocos 2 e 3;
2. está no formato da planta (com os blocos `##`): os rascunhos antigos, de antes de 17/11, ficam para a revisão;
3. nenhuma fonte tem falha grave nos dados da Câmara (contradição ou ocultação, 25.14);
4. a situação da proposição está no dicionário (código conhecido);
5. ninguém da equipe mexeu no rascunho (se mexeu, a equipe já está revisando).

Os **avisos** (frase com mais de 25 palavras fora da ementa oficial, parágrafo principal com mais de 400 caracteres) aparecem na fila, mas não seguram a publicação.

## 5. Como liga

`PUBLICACAO_AUTOMATICA` no `.env`:

- `ensaio` (padrão): o sistema só marca na fila o que publicaria sozinho e conta no log, sem publicar nada. Serve para a equipe conferir antes de ligar.
- `ligada`: publica sozinho o que passa, a cada horária e depois dos boletins. A notícia diz, em "como foi feita", que foi publicada automaticamente, sem revisão da equipe.
- `desligada`: nada é conferido nem publicado sozinho; tudo passa pela equipe, como antes.

A equipe pode arquivar qualquer notícia publicada sozinha, como qualquer outra.
