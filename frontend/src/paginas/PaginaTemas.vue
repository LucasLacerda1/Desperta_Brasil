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
  <div class="conteudo pagina">
    <h1 class="serifa">Temas</h1>
    <p class="texto-2">São os temas oficiais que a Câmara dá a cada proposição.</p>
    <p v-if="erro" role="alert">{{ erro }}</p>
    <ul class="grade">
      <li v-for="t in temas" :key="t.cod_tema">
        <RouterLink :to="{ name: 'tema', params: { cod: t.cod_tema } }" class="cartao tema">
          <span class="icone" aria-hidden="true">{{ iconeDoTema(t) }}</span>
          <span class="nome">{{ t.nome }}</span>
          <span class="texto-2 conta">{{ t.noticias_publicadas }} {{ t.noticias_publicadas === 1 ? 'notícia' : 'notícias' }}</span>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.pagina { padding-block: 28px 16px; }
h1 { margin: 0; font-size: clamp(28px, 4vw, 36px); }
.pagina > p { margin: 6px 0 24px; }
.grade { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.tema { display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 4px 12px; align-items: center; padding: 16px 20px; text-decoration: none; color: var(--texto); height: 100%; }
.tema:hover .nome { text-decoration: underline; }
.tema .icone { font-size: 28px; color: var(--destaque); grid-row: span 2; }
.nome { font-weight: 500; line-height: 1.3; }
.conta { font-size: 13px; }
</style>
