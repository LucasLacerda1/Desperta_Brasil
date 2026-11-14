// Tema claro ou escuro. Sem escolha, vale o do aparelho (tokens.css).
// A escolha fica so no navegador da pessoa (localStorage); nada vai para o servidor.
const CHAVE = 'desperta-tema'

export function temaAtual() {
  const escolhido = document.documentElement.dataset.tema
  if (escolhido) return escolhido
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro'
}

export function aplicarTemaSalvo() {
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
