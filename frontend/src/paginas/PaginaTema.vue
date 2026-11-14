<script setup>
// RF11: noticias de um tema, com data de publicacao e de alteracao.
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mensagemDeErro, portal } from '../services/api.js'
import { iconeDoTema } from '../temas.js'
import NavTemas from '../componentes/NavTemas.vue'
import CartaoNoticia from '../componentes/CartaoNoticia.vue'
import Paginacao from '../componentes/Paginacao.vue'

const rota = useRoute()
const roteador = useRouter()
const cod = computed(() => Number(rota.params.cod))
const pagina = computed(() => Number(rota.query.pagina) || 1)
const tema = ref(null)
const lista = ref({ itens: [], total: 0, paginas: 1 })
const carregando = ref(true)
const erro = ref('')

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const [temas, noticias] = await Promise.all([portal.temas(), portal.recentes({ tema: cod.value, pagina: pagina.value, por_pagina: 12 })])
    tema.value = temas.itens.find((t) => t.cod_tema === cod.value) || null
    lista.value = noticias
    if (tema.value) document.title = `${tema.value.nome} — Desperta Brasil`
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}

watch([cod, pagina], carregar, { immediate: true })
const irPara = (p) => roteador.push({ query: p > 1 ? { pagina: p } : {} })
</script>

<template>
  <NavTemas :atual="cod" />
  <div class="conteudo pagina">
    <p v-if="carregando" class="carregando">Carregando…</p>
    <p v-else-if="erro" class="carregando" role="alert">{{ erro }}</p>
    <template v-else>
      <header class="topo">
        <span class="roda"><span class="icone" aria-hidden="true">{{ iconeDoTema(tema || { cod_tema: cod }) }}</span></span>
        <div>
          <h1 class="serifa">{{ tema?.nome || 'Tema não encontrado' }}</h1>
          <p class="texto-2">{{ lista.total }} {{ lista.total === 1 ? 'notícia publicada' : 'notícias publicadas' }}, da mais recente para a mais antiga</p>
        </div>
      </header>
      <p v-if="!lista.itens.length" class="carregando">Ainda não há notícias publicadas neste tema.</p>
      <div class="grade">
        <div v-for="n in lista.itens" :key="n.id" class="cartao"><CartaoNoticia :noticia="n" /></div>
      </div>
      <Paginacao :pagina="lista.pagina || pagina" :paginas="lista.paginas || 1" @ir="irPara" />
    </template>
  </div>
</template>

<style scoped>
.pagina { display: flex; flex-direction: column; gap: 24px; padding-block: 16px; }
.topo { display: flex; align-items: center; gap: 16px; }
.roda { flex: none; width: 56px; height: 56px; border-radius: 28px; background: var(--superficie); display: flex; align-items: center; justify-content: center; }
.roda .icone { font-size: 30px; color: var(--destaque); }
h1 { margin: 0; font-size: clamp(26px, 4vw, 36px); }
.topo p { margin: 4px 0 0; font-size: 15px; }
.grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }
</style>
