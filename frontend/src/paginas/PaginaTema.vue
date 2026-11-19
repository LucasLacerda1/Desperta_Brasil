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
  <div class="conteudo flex flex-col gap-6 py-4">
    <p v-if="carregando" class="carregando">Carregando…</p>
    <p v-else-if="erro" class="carregando" role="alert">{{ erro }}</p>
    <template v-else>
      <header class="flex items-center gap-4">
        <span class="flex size-14 flex-none items-center justify-center rounded-full bg-superficie">
          <span class="icone text-[30px] text-destaque" aria-hidden="true">{{ iconeDoTema(tema || { cod_tema: cod }) }}</span>
        </span>
        <div>
          <h1 class="serifa m-0 text-[clamp(26px,4vw,36px)]">{{ tema?.nome || 'Tema não encontrado' }}</h1>
          <p class="texto-2 mt-1 mb-0 text-[15px]">{{ lista.total }} {{ lista.total === 1 ? 'notícia publicada' : 'notícias publicadas' }}, da mais recente para a mais antiga</p>
        </div>
      </header>
      <p v-if="!lista.itens.length" class="carregando">Ainda não há notícias publicadas neste tema.</p>
      <div class="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        <div v-for="n in lista.itens" :key="n.id" class="cartao"><CartaoNoticia :noticia="n" /></div>
      </div>
      <Paginacao :pagina="lista.pagina || pagina" :paginas="lista.paginas || 1" @ir="irPara" />
    </template>
  </div>
</template>
