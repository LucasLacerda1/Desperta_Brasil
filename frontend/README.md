# Front-end do Desperta Brasil (PROTÓTIPO)

> **Isto é um protótipo, não a Fase 5.** Serve para o grupo avaliar o desenho e a navegação
> com dados reais. Na Fase 5 o código pode mudar inteiro. Fica só na branch `prototipo-front`.

Vue 3 + Vite + Axios + Vue Router, como no TaskFlow. O front chama `/api`, e o Vite repassa
para o Flask em `http://localhost:5000` (sem CORS em desenvolvimento).

## Como rodar

Precisa do Node.js 20 ou mais novo (`sudo apt install nodejs npm`).

Em um terminal, a API com a **cópia** do banco feita para o protótipo (o banco real não é usado):

```bash
DATABASE_URL=sqlite:///$PWD/instance/desperta-prototipo.db flask --app app.py run
```

Em outro terminal, o front:

```bash
cd frontend
npm install     # só na primeira vez
npm run dev
```

Abra `http://localhost:5173`.

- **Área da equipe:** `http://localhost:5173/equipe`, com `prototipo@desperta.local` e a senha
  `prototipo123` (esse usuário existe só na cópia do banco).
- **Banco do protótipo:** `instance/desperta-prototipo.db` é uma cópia do banco real de 14/11/2026,
  com 37 notícias publicadas para as páginas terem o que mostrar. Fica fora do git.

## O que tem

| Endereço | Tela |
|---|---|
| `/` | Página inicial: manchete, últimas publicadas, notícias por tema, "como cada notícia é feita" |
| `/noticia/<slug>` | Notícia: texto, votação (barra, partidos, orientações, voto de cada deputado), andamento, "como foi feita" |
| `/tema/<cod>` e `/temas` | Notícias de um tema e a lista dos 32 temas |
| `/busca?q=` | Busca com filtro por dia, mês, ano e tema |
| `/equipe/entrar` e `/equipe` | Login e fila de revisão (editar, aprovar, publicar, rejeitar, arquivar, em lote) |

Tema claro e escuro: segue o aparelho; o botão no cabeçalho troca (a escolha fica só no navegador).

## Decisões do protótipo

- **Cores** em `src/estilos/tokens.css`: paleta lápis, cobre e marfim; verde e vermelho só para
  votos e avisos. Todo texto passa de 4,5:1 de contraste.
- **Fontes e ícones dentro do projeto** (`@fontsource` e `material-symbols`, licenças OFL e
  Apache 2.0): o navegador do visitante não chama o Google.
- **Ícone de cada tema** em `src/temas.js`, porque no banco `tema.icone` ainda é `article` para todos.

## O que é só de mentira aqui

- **Ouvir** (Piper) e **busca por voz** (Whisper): os botões existem e avisam que entram na Fase 5.
- **Aviso de cookies:** guarda a resposta só no navegador; as rotas do visitante ainda não existem.
- **Mínimo para aprovar** (257 para PLP, 308 para PEC, só no Plenário e fora de requerimentos):
  a regra está no front (`SecaoVotacao.vue`). Na Fase 5 deve vir do service de votações.
- **Equipe, Coletas e Log** (só admin): aparecem apagados no menu.
- Sem testes automáticos e sem lint.
