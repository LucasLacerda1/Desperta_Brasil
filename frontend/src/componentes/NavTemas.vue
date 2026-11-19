<script setup>
// Temas que ja tem noticia publicada, como atalhos.
import { onMounted, ref } from 'vue'
import { portal } from '../services/api.js'
import { iconeDoTema } from '../temas.js'

defineProps({ atual: { type: Number, default: null } })
const temas = ref([])

onMounted(async () => {
  try {
    const resposta = await portal.temas()
    temas.value = resposta.itens.filter((t) => t.noticias_publicadas > 0)
  } catch {
    temas.value = []
  }
})
</script>

<template>
  <nav class="conteudo flex gap-2 overflow-x-auto pt-5 pb-2 [scrollbar-color:var(--borda)_transparent] [scrollbar-width:thin]" aria-label="Temas">
    <RouterLink
      to="/" class="flex flex-none items-center gap-1.5 rounded-[20px] border px-4 py-2 text-[14px] no-underline"
      :class="atual === null ? 'border-principal bg-principal font-medium text-sobre-principal hover:text-sobre-principal' : 'border-borda text-texto'"
    >
      <span class="icone text-[18px]" :class="atual === null ? 'text-sobre-principal' : 'text-destaque'" aria-hidden="true">home</span>Início
    </RouterLink>
    <RouterLink
      v-for="t in temas" :key="t.cod_tema" :to="{ name: 'tema', params: { cod: t.cod_tema } }"
      class="flex flex-none items-center gap-1.5 rounded-[20px] border px-4 py-2 text-[14px] no-underline"
      :class="atual === t.cod_tema ? 'border-principal bg-principal font-medium text-sobre-principal hover:text-sobre-principal' : 'border-borda text-texto'"
    >
      <span class="icone text-[18px]" :class="atual === t.cod_tema ? 'text-sobre-principal' : 'text-destaque'" aria-hidden="true">{{ iconeDoTema(t) }}</span>{{ t.nome }}
    </RouterLink>
    <RouterLink to="/temas" class="flex-none self-center px-3 py-2 text-[14px] font-medium">Todos os 32 temas</RouterLink>
  </nav>
</template>
