<script setup>
// Os 32 temas oficiais da Camara, com quantas noticias publicadas cada um tem.
import { onMounted, ref } from 'vue'
import { mensagemDeErro, portal } from '../services/api.js'
import { iconeDoTema } from '../temas.js'

const temas = ref([])
const erro = ref('')
onMounted(async () => {
  document.title = 'Temas — Desperta Brasil'
  try {
    temas.value = (await portal.temas()).itens
  } catch (e) {
    erro.value = mensagemDeErro(e)
  }
})
</script>

<template>
  <div class="conteudo pt-7 pb-4">
    <h1 class="serifa m-0 text-[clamp(28px,4vw,36px)]">Temas</h1>
    <p class="texto-2 mt-1.5 mb-6">São os temas oficiais que a Câmara dá a cada proposição.</p>
    <p v-if="erro" role="alert">{{ erro }}</p>
    <ul class="m-0 grid list-none grid-cols-1 gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
      <li v-for="t in temas" :key="t.cod_tema">
        <RouterLink
          :to="{ name: 'tema', params: { cod: t.cod_tema } }"
          class="cartao group grid h-full grid-cols-[32px_minmax(0,1fr)] items-center gap-x-3 gap-y-1 px-5 py-4 text-texto no-underline hover:text-texto"
        >
          <span class="icone row-span-2 text-[28px] text-destaque" aria-hidden="true">{{ iconeDoTema(t) }}</span>
          <span class="leading-[1.3] font-medium group-hover:underline">{{ t.nome }}</span>
          <span class="texto-2 text-[13px]">{{ t.noticias_publicadas }} {{ t.noticias_publicadas === 1 ? 'notícia' : 'notícias' }}</span>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
