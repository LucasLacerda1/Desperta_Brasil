import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'inicio', component: () => import('./paginas/PaginaInicial.vue') },
  { path: '/noticia/:slug', name: 'noticia', component: () => import('./paginas/PaginaNoticia.vue') },
  { path: '/tema/:cod', name: 'tema', component: () => import('./paginas/PaginaTema.vue') },
  { path: '/temas', name: 'temas', component: () => import('./paginas/PaginaTemas.vue') },
  { path: '/busca', name: 'busca', component: () => import('./paginas/PaginaBusca.vue') },
  { path: '/como-funciona', name: 'como-funciona', component: () => import('./paginas/PaginaComoFunciona.vue') },
  { path: '/equipe/entrar', name: 'entrar', component: () => import('./paginas/equipe/PaginaEntrar.vue') },
  { path: '/equipe', name: 'fila', component: () => import('./paginas/equipe/PaginaFila.vue') },
  { path: '/equipe/noticia/:id(\\d+)', name: 'editar', component: () => import('./paginas/equipe/PaginaEditar.vue') },
  // So admin (a tela confere o papel; a API tambem)
  { path: '/equipe/membros', name: 'equipe-membros', component: () => import('./paginas/equipe/PaginaEquipe.vue') },
  { path: '/equipe/coletas', name: 'coletas', component: () => import('./paginas/equipe/PaginaColetas.vue') },
  { path: '/equipe/log', name: 'log', component: () => import('./paginas/equipe/PaginaLog.vue') },
  { path: '/:caminho(.*)*', name: 'nao-encontrada', component: () => import('./paginas/NaoEncontrada.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, salvo) {
    return salvo || { top: 0 }
  },
})
