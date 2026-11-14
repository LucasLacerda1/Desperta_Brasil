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
  <nav class="temas conteudo" aria-label="Temas">
    <RouterLink to="/" class="chip" :class="{ ativo: atual === null }">
      <span class="icone" aria-hidden="true">home</span>Início
    </RouterLink>
    <RouterLink
      v-for="t in temas" :key="t.cod_tema" :to="{ name: 'tema', params: { cod: t.cod_tema } }"
      class="chip" :class="{ ativo: atual === t.cod_tema }"
    >
      <span class="icone" aria-hidden="true">{{ iconeDoTema(t) }}</span>{{ t.nome }}
    </RouterLink>
    <RouterLink to="/temas" class="todos">Todos os 32 temas</RouterLink>
  </nav>
</template>

<style scoped>
.temas { display: flex; gap: 8px; overflow-x: auto; padding-block: 20px 8px; scrollbar-width: thin; scrollbar-color: var(--borda) transparent; }
.chip {
  flex: none;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid var(--borda);
  color: var(--texto);
  text-decoration: none;
  font-size: 14px;
}
.chip .icone { font-size: 18px; color: var(--destaque); }
.chip.ativo { background: var(--principal); border-color: var(--principal); color: var(--sobre-principal); font-weight: 500; }
.chip.ativo .icone { color: var(--sobre-principal); }
.todos { flex: none; align-self: center; padding: 8px 12px; font-size: 14px; font-weight: 500; }
</style>
