// Tema claro ou escuro. Sem escolha, vale o do aparelho (tokens.css).
// A escolha fica so no navegador da pessoa (localStorage); nada vai para o servidor.
const CHAVE = 'desperta-tema'

// Tema escuro escondido por enquanto (pedido do Lucas e do grupo, 18/11): o site fica so no claro,
// mesmo em aparelho no modo escuro. As cores do escuro continuam em tokens.css; para voltar, true.
export const TEMA_ESCURO_LIGADO = false

export function temaAtual() {
  const escolhido = document.documentElement.dataset.tema
  if (escolhido) return escolhido
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro'
}

export function aplicarTemaSalvo() {
  if (!TEMA_ESCURO_LIGADO) {
    document.documentElement.dataset.tema = 'claro'
    return
  }
  try {
    const salvo = localStorage.getItem(CHAVE)
    if (salvo === 'claro' || salvo === 'escuro') document.documentElement.dataset.tema = salvo
  } catch {
    // navegador sem localStorage: segue o aparelho
  }
}

export function alternarTema() {
  const novo = temaAtual() === 'escuro' ? 'claro' : 'escuro'
  document.documentElement.dataset.tema = novo
  try {
    localStorage.setItem(CHAVE, novo)
  } catch {
    // sem localStorage, vale so nesta visita
  }
  return novo
}
