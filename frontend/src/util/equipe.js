// Status da fila de revisao (RF16), na ordem do fluxo: rascunho -> em_revisao -> publicada.
export const STATUS_DA_FILA = [
  { valor: 'rascunho', nome: 'Fila de revisão', icone: 'inbox' },
  { valor: 'em_revisao', nome: 'Aprovadas, a publicar', icone: 'task_alt' },
  { valor: 'publicada', nome: 'Publicadas', icone: 'public' },
  { valor: 'rejeitada', nome: 'Rejeitadas', icone: 'block' },
  { valor: 'arquivada', nome: 'Arquivadas', icone: 'inventory_2' },
]

export function nomeDoStatus(valor) {
  return STATUS_DA_FILA.find((s) => s.valor === valor)?.nome || valor
}
