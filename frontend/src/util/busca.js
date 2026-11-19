// Filtros da busca (RF12), usados no painel do cabecalho e na pagina de busca.
export const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
const anoAtual = new Date().getFullYear()
export const ANOS = [anoAtual, anoAtual - 1, anoAtual - 2]
export const CAMPOS_DO_FILTRO = ['dia', 'mes', 'ano', 'tema']
