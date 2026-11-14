<script setup>
// Situacao do projeto. O que a Camara nao informou ja vem escrito pela API ("nao informado pela Camara", 22.5).
import { computed } from 'vue'
import { data } from '../util/datas.js'

const props = defineProps({ proposicao: { type: Object, required: true } })
const autores = computed(() => {
  const nomes = (props.proposicao.autores || []).map((a) => a.nome)
  if (nomes.length <= 3) return nomes.join(', ')
  return `${nomes.slice(0, 3).join(', ')} e mais ${nomes.length - 3}`
})
</script>

<template>
  <div class="cartao quadro">
    <h2>{{ proposicao.sigla }}</h2>
    <p class="tipo texto-2">{{ proposicao.tipo }}</p>
    <p class="ementa">{{ proposicao.ementa }}</p>
    <dl>
      <dt>Situação</dt><dd class="forte">{{ proposicao.situacao }}</dd>
      <dt>Regime</dt><dd>{{ proposicao.regime }}</dd>
      <dt>Quem decide</dt><dd>{{ proposicao.apreciacao }}</dd>
      <template v-if="autores"><dt>Autoria</dt><dd>{{ autores }}</dd></template>
      <dt>Apresentado</dt><dd>{{ data(proposicao.data_apresentacao) }}</dd>
      <template v-if="proposicao.temas?.length">
        <dt>Temas</dt>
        <dd>
          <template v-for="(t, i) in proposicao.temas" :key="t.cod_tema">
            <template v-if="i">, </template>
            <RouterLink :to="{ name: 'tema', params: { cod: t.cod_tema } }">{{ t.nome }}</RouterLink>
          </template>
        </dd>
      </template>
    </dl>
    <a v-if="proposicao.url_inteiro_teor" :href="proposicao.url_inteiro_teor" class="botao botao-principal" target="_blank" rel="noopener">
      <span class="icone" aria-hidden="true">description</span>Texto completo
    </a>
    <p v-else class="texto-2 sem-texto">Texto completo não informado pela Câmara.</p>
    <a v-if="proposicao.url_pagina" :href="proposicao.url_pagina" class="botao botao-contorno" target="_blank" rel="noopener">
      <span class="icone" aria-hidden="true">open_in_new</span>Ver no site da Câmara
    </a>
  </div>
</template>

<style scoped>
.quadro { display: flex; flex-direction: column; gap: 12px; }
h2 { margin: 0; font-size: 18px; }
.tipo { margin: -8px 0 0; font-size: 13px; }
.ementa { margin: 0; font-size: 15px; }
dl { margin: 0; display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px 12px; font-size: 14px; }
dt { color: var(--texto-2); }
dd { margin: 0; overflow-wrap: anywhere; }
.forte { font-weight: 500; }
.sem-texto { margin: 0; font-size: 14px; }
</style>
