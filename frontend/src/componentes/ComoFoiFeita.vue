<script setup>
// Transparencia (22.5): quem escreveu, quem publicou e de onde vieram os dados.
import { computed } from 'vue'
import { dataHora } from '../util/datas.js'

const props = defineProps({ noticia: { type: Object, required: true } })
const feita = computed(() => props.noticia.como_foi_feita || {})

const NOMES = { proposicao: 'Proposição', votacao: 'Votação', deputado: 'Deputado', evento: 'Evento', orgao: 'Órgão', partido: 'Partido' }
const fontes = computed(() =>
  (props.noticia.fontes || []).map((f) => ({
    ...f,
    rotulo: `${NOMES[f.tipo] || f.tipo} ${f.ref_id}`,
    link: f.url_pagina || f.url_dados_abertos,
  })),
)
</script>

<template>
  <section class="como" aria-labelledby="t-feita">
    <h2 id="t-feita"><span class="icone" aria-hidden="true">verified</span>Como esta notícia foi feita</h2>
    <ul>
      <li v-if="feita.origem === 'ia'">
        Rascunho escrito automaticamente com frases prontas e os dados da Câmara, sem inventar nenhum número
        <span class="texto-2">(gerador: {{ feita.gerador || 'não registrado' }})</span>.
      </li>
      <li v-else>Escrita pela equipe do Desperta Brasil, com os dados da Câmara.</li>
      <li>
        Revisada e publicada por <strong>{{ feita.publicada_por || 'equipe' }}</strong>
        <template v-if="feita.publicada_em"> em {{ dataHora(feita.publicada_em) }}</template>.
      </li>
      <li v-if="noticia.alterado_em">Texto alterado pela última vez em {{ dataHora(noticia.alterado_em) }}.</li>
      <li v-if="fontes.length">
        Fontes oficiais:
        <template v-for="(f, i) in fontes" :key="f.tipo + f.ref_id">
          <template v-if="i">, </template>
          <a v-if="f.link" :href="f.link" target="_blank" rel="noopener">{{ f.rotulo }}</a>
          <span v-else>{{ f.rotulo }}</span>
        </template>.
      </li>
    </ul>
    <p class="texto-2 vistas">Esta notícia foi aberta {{ noticia.visualizacoes }} {{ noticia.visualizacoes === 1 ? 'vez' : 'vezes' }}.</p>
  </section>
</template>

<style scoped>
.como { border: 2px solid var(--principal); border-radius: 16px; padding: 28px; display: flex; flex-direction: column; gap: 12px; }
h2 { margin: 0; font-size: 22px; display: flex; align-items: center; gap: 8px; }
h2 .icone { color: var(--link); font-size: 24px; }
ul { margin: 0; padding-left: 20px; font-size: 15px; display: flex; flex-direction: column; gap: 6px; }
.vistas { margin: 0; font-size: 13px; }
@media (max-width: 600px) { .como { padding: 20px; } }
</style>
