# Front-end do Desperta Brasil (PROTÓTIPO)

> **Isto é um protótipo, não a Fase 5.** Serve para o grupo avaliar o desenho e a navegação
> com dados reais e para a apresentação da disciplina. Na Fase 5 o código pode mudar.

Vue 3 + Vite + Axios + Vue Router, como no TaskFlow, com **Tailwind CSS** (framework de CSS, MIT).
O front chama `/api`, e o Vite repassa
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

Só o tema claro por enquanto: o escuro está escondido (`TEMA_ESCURO_LIGADO` em `src/util/tema.js`).
As cores dele continuam em `src/estilos/tokens.css`; com `true`, volta o botão no cabeçalho.

## Decisões do protótipo

- **Tailwind CSS** (`@tailwindcss/vite`): `src/estilos/principal.css` é a entrada do CSS. As cores do
  Tailwind são só as do Desperta (`bg-fundo`, `text-texto`, `border-linha`...), e cada uma aponta para
  uma variável de `src/estilos/tokens.css`, por isso a mesma classe muda sozinha no tema escuro.
  As peças comuns (`.botao`, `.cartao`, `.tabela`, `.chip`...) são montadas com `@apply`; o layout
  de cada tela (grades, colunas, celular) usa as classes direto no HTML (`grid md:grid-cols-2 lg:grid-cols-3`).
  Tamanhos de letra em px (`text-[14px]`) para não mudar a altura da linha. Sem o "preflight" do
  Tailwind: o reset é o `src/estilos/base.css`.
- **Cores** em `src/estilos/tokens.css`: paleta lápis, cobre e marfim do estudo dos leões da
  Babilônia; verde e vermelho só para votos e avisos. Todo texto passa de 7:1 de contraste (AAA).
- **Fontes e ícones dentro do projeto** (`@fontsource` e `material-symbols`, licenças OFL e
  Apache 2.0): o navegador do visitante não chama o Google.
- **Ícone de cada tema** em `src/temas.js`, porque no banco `tema.icone` ainda é `article` para todos.

## O que é só de mentira aqui

- **Busca por voz** (Whisper): o botão existe e avisa que entra na Fase 5.
- **Aviso de cookies:** guarda a resposta só no navegador; as rotas do visitante ainda não existem.
- **Mínimo para aprovar** (257 para PLP, 308 para PEC, só no Plenário e fora de requerimentos):
  a regra está no front (`SecaoVotacao.vue`). Na Fase 5 deve vir do service de votações.
- Sem testes automáticos e sem lint.
