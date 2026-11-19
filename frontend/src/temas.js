// Icone Material Symbols de cada tema oficial da Camara (cod_tema).
// Se o banco ainda tiver "article" em tema.icone (temas coletados antes da decisao 25.2), vale esta lista.
const ICONES = {
  34: 'domain', // Administracao Publica
  35: 'theater_comedy', // Arte, Cultura e Religiao
  37: 'cell_tower', // Comunicacoes
  39: 'sports_soccer', // Esporte e Lazer
  40: 'payments', // Economia
  41: 'location_city', // Cidades e Desenvolvimento Urbano
  42: 'handshake', // Direito Civil e Processual Civil
  43: 'gavel', // Direito Penal e Processual Penal
  44: 'diversity_3', // Direitos Humanos e Minorias
  46: 'school', // Educacao
  48: 'eco', // Meio Ambiente e Desenvolvimento Sustentavel
  51: 'landscape', // Estrutura Fundiaria
  52: 'elderly', // Previdencia e Assistencia Social
  53: 'account_balance', // Processo Legislativo e Atuacao Parlamentar
  54: 'bolt', // Energia, Recursos Hidricos e Minerais
  55: 'public', // Relacoes Internacionais e Comercio Exterior
  56: 'medical_services', // Saude
  57: 'shield', // Defesa e Seguranca
  58: 'work', // Trabalho e Emprego
  60: 'luggage', // Turismo
  61: 'directions_bus', // Viacao, Transporte e Mobilidade
  62: 'science', // Ciencia, Tecnologia e Inovacao
  64: 'agriculture', // Agricultura, Pecuaria, Pesca e Extrativismo
  66: 'factory', // Industria, Comercio e Servicos
  67: 'shopping_cart', // Direito e Defesa do Consumidor
  68: 'menu_book', // Direito Constitucional
  70: 'savings', // Financas Publicas e Orcamento
  72: 'celebration', // Homenagens e Datas Comemorativas
  74: 'how_to_vote', // Politica, Partidos e Eleicoes
  76: 'balance', // Direito e Justica
  85: 'calculate', // Ciencias Exatas e da Terra
  86: 'groups', // Ciencias Sociais e Humanas
}

export function iconeDoTema(tema) {
  if (!tema) return 'article'
  if (tema.icone && tema.icone !== 'article') return tema.icone
  return ICONES[tema.cod_tema] || 'article'
}
