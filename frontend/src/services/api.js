import axios from 'axios'

// Mesmo endereco do site: em desenvolvimento o Vite repassa /api para o Flask.
const api = axios.create({ baseURL: '/api', withCredentials: true })

// A API responde {"erro": "..."}: devolve so a mensagem.
export function mensagemDeErro(erro) {
  return erro?.response?.data?.erro || 'Não foi possível falar com o servidor.'
}

// Formularios: a API manda {"campos": {campo: mensagem}} para mostrar o erro embaixo de cada campo.
export function errosDosCampos(erro) {
  return erro?.response?.data?.campos || {}
}

export const portal = {
  situacao: () => api.get('/sistema/situacao').then((r) => r.data),
  principal: (porTema = 3) => api.get('/noticias/principal', { params: { por_tema: porTema } }).then((r) => r.data),
  recentes: (params = {}) => api.get('/noticias', { params }).then((r) => r.data),
  noticia: (slug) => api.get(`/noticias/${encodeURIComponent(slug)}`).then((r) => r.data),
  busca: (params) => api.get('/noticias/busca', { params }).then((r) => r.data),
  temas: () => api.get('/proposicoes/temas').then((r) => r.data),
  votacao: (id) => api.get(`/votacoes/${encodeURIComponent(id)}`).then((r) => r.data),
  proposicao: (id) => api.get(`/proposicoes/${id}`).then((r) => r.data),
}

export const equipe = {
  entrar: (email, senha) => api.post('/auth/login', { email, senha }).then((r) => r.data),
  sair: () => api.post('/auth/logout').then((r) => r.data),
  eu: () => api.get('/auth/eu').then((r) => r.data),
  fila: (params) => api.get('/noticias/admin', { params }).then((r) => r.data),
  detalhe: (id) => api.get(`/noticias/admin/${id}`).then((r) => r.data),
  editar: (id, dados) => api.patch(`/noticias/admin/${id}`, dados).then((r) => r.data),
  acao: (id, acao, comentario) => api.post(`/noticias/admin/${id}/${acao}`, { comentario }).then((r) => r.data),
  lote: (ids, acao, comentario) => api.post('/noticias/admin/lote', { ids, acao, comentario }).then((r) => r.data),
  // So admin
  membros: () => api.get('/auth/equipe').then((r) => r.data),
  criarMembro: (dados) => api.post('/auth/equipe', dados).then((r) => r.data),
  editarMembro: (id, dados) => api.patch(`/auth/equipe/${id}`, dados).then((r) => r.data),
  coletas: (params) => api.get('/sistema/coletas', { params }).then((r) => r.data),
  log: (params) => api.get('/sistema/log', { params }).then((r) => r.data),
}
