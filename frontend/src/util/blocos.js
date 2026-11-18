// Le o texto de uma secao da noticia (escrito pelo GeradorFrases, planta 25.14) e devolve blocos
// para a pagina mostrar no jeito de newsletter. O texto gravado no banco nao muda: so a forma de mostrar.
//
//   "Situacao: X. Regime: Y."             -> ficha  [{ rotulo, valor }]
//   "Em 12/08/2026, em MESA: Remessa..."   -> passos [{ data, orgao, texto }]
//   "### 12/11/2026: titulo"               -> sub (atualizacao da noticia viva)
//   linhas com "- "                         -> lista
//   o resto                                 -> p

// Rotulo curto, sem numero nem virgula: "Situação", "Regime de tramitação", "Ementa oficial"
const ROTULO = /^([A-ZÀ-Ú][A-Za-zÀ-ÿ ]{1,28}):\s+(.+)$/
const PASSO = /^Em (\d{2}\/\d{2}\/\d{4}), em ([^:]+):\s*(.+)$/
// Frases seguidas no mesmo paragrafo: "Regime: X. Apreciação: Y." vira duas
const ENTRE_ROTULOS = /\.\s+(?=[A-ZÀ-Ú][A-Za-zÀ-ÿ ]{1,28}:\s)/

function semAspas(valor) {
  return valor.replace(/^"([^"]+)"/, '$1')
}

export function lerSecao(texto) {
  const saida = []
  const ultimo = () => saida[saida.length - 1]
  const juntar = (tipo, item) => {
    if (ultimo()?.tipo === tipo) ultimo().itens.push(item)
    else saida.push({ tipo, itens: [item] })
  }

  for (const parte of (texto || '').split(/\n\s*\n/)) {
    const linhas = parte.split('\n').map((l) => l.trim()).filter(Boolean)
    if (!linhas.length) continue
    if (linhas[0].startsWith('### ')) {
      saida.push({ tipo: 'sub', texto: linhas.shift().slice(4) })
      if (!linhas.length) continue
    }
    if (linhas.every((l) => l.startsWith('- '))) {
      saida.push({ tipo: 'lista', itens: linhas.map((l) => l.slice(2)) })
      continue
    }
    const soltas = []
    for (const linha of linhas) {
      const passo = PASSO.exec(linha)
      if (passo) {
        juntar('passos', { data: passo[1], orgao: passo[2].trim(), texto: passo[3] })
        continue
      }
      // "Últimos passos:" so anuncia a lista que vem embaixo
      if (/^[A-ZÀ-Ú][A-Za-zÀ-ÿ ]{1,28}:$/.test(linha)) continue
      const frases = linha.split(ENTRE_ROTULOS).map((f, i, todas) => (i < todas.length - 1 ? `${f}.` : f))
      if (frases.every((f) => ROTULO.test(f))) {
        for (const f of frases) {
          const [, rotulo, valor] = ROTULO.exec(f)
          juntar('ficha', { rotulo, valor: semAspas(valor).replace(/\.$/, '') })
        }
      } else {
        soltas.push(linha)
      }
    }
    if (soltas.length) saida.push({ tipo: 'p', texto: soltas.join('\n') })
  }
  return saida
}

// Icone de cada parte da planta da noticia
const ICONES = {
  'O que propõe': 'description',
  'Resultado da votação': 'how_to_vote',
  'Onde está na Câmara': 'location_on',
  'O que a Câmara não informou': 'report',
  Atualizações: 'update',
}
export function iconeDaSecao(titulo) {
  return ICONES[titulo] || 'article'
}
