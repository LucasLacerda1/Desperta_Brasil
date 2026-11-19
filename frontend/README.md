# Front-end do Desperta Brasil

Vue 3 + Vite + Axios + Vue Router, como no TaskFlow, com **Tailwind CSS** (framework de CSS, MIT).
O front chama `/api`, e o Vite repassa para o Flask em `http://localhost:5000` (sem CORS em desenvolvimento).

## Como rodar

Precisa do Node.js 20.19 ou mais novo. O front só mostra dados com a API Flask rodando, então são dois terminais.
Os comandos são os mesmos no Linux, no macOS e no Windows.

**Terminal 1, a API**, na pasta do projeto (a pasta `DespertaBrasil` do zip), com o `.venv` ativo e o back-end
instalado como no `README.md` da raiz:

```bash
flask run
```

**Terminal 2, o site**, dentro da pasta `frontend`:

```bash
cd frontend
npm install     # só na primeira vez
npm run dev
```

Abra `http://localhost:5173`.

- **Área da equipe:** `http://localhost:5173/equipe`. Com o banco de exemplo do zip (`instance/desperta.db`),
  entre com `equipe@desperta.local` e a senha `desperta123`. Num banco novo, crie o primeiro admin com
  `flask equipe criar-admin`.
- **Versão para publicar:** `npm run build` gera o site pronto em `frontend/dist`.

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

## Decisões do front-end

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
- **Ícone de cada tema** em `src/temas.js`.

## O que ainda não está pronto

- **Busca por voz** (Whisper): o botão existe e avisa que ainda não está disponível.
- **Aviso de cookies:** guarda a resposta só no navegador; as rotas do visitante ainda não existem.
- **Mínimo para aprovar** (257 para PLP, 308 para PEC, só no Plenário e fora de requerimentos):
  a regra está no front (`SecaoVotacao.vue`); o ideal é vir do service de votações.
- Sem testes automáticos do front-end (os 929 testes são do back-end, com o pytest).
