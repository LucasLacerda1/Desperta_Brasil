// Datas sempre no horario de Brasilia, como o portal mostra (a API manda UTC ou -03:00).
const FUSO = 'America/Sao_Paulo'

const fmtData = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, day: '2-digit', month: '2-digit', year: 'numeric' })
const fmtHora = new Intl.DateTimeFormat('pt-BR', { timeZone: FUSO, hour: '2-digit', minute: '2-digit', hour12: false })

function comoData(valor) {
  if (!valor) return null
  // "2026-10-14" (so o dia): meio-dia em Brasilia, para nao cair no dia anterior
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) return new Date(`${valor}T12:00:00-03:00`)
  // "13/11/2026" (data das atualizacoes da noticia viva, ja no formato brasileiro): dia/mes/ano.
  // Sem isto o navegador le como mes/dia (12/11 vira 11 de dezembro; 13/11 fica invalida).
  const br = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(valor)
  if (br) return new Date(`${br[3]}-${br[2]}-${br[1]}T12:00:00-03:00`)
  const data = new Date(valor)
  return Number.isNaN(data.getTime()) ? null : data
}

export function data(valor) {
  const d = comoData(valor)
  return d ? fmtData.format(d) : ''
}

export function hora(valor) {
  const d = comoData(valor)
  if (!d) return ''
  return fmtHora.format(d).replace(':', 'h')
}

export function dataHora(valor) {
  const d = comoData(valor)
  return d ? `${data(valor)}, ${hora(valor)}` : ''
}

export function ehHoje(valor) {
  const d = comoData(valor)
  return !!d && fmtData.format(d) === fmtData.format(new Date())
}

// "hoje, às 17h05" ou "13/11/2026, às 17h05"
export function quando(valor) {
  if (!comoData(valor)) return ''
  return `${ehHoje(valor) ? 'hoje' : data(valor)}, às ${hora(valor)}`
}
