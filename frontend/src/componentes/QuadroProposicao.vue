<script setup>
// Quadro lateral do projeto: sigla, data, temas e os links oficiais.
import { data } from '../util/datas.js'

const props = defineProps({ proposicao: { type: Object, required: true } })
</script>

<template>
  <!-- Enxuto: o que a Camara informou sobre a proposta (situacao, regime, autoria) ja esta nos blocos da noticia -->
  <div class="cartao flex flex-col gap-3">
    <div>
      <h2 class="m-0 text-[18px]">{{ proposicao.sigla }}</h2>
      <p class="texto-2 m-0 text-[13px]">{{ proposicao.tipo }}</p>
    </div>
    <dl class="m-0 grid grid-cols-[96px_minmax(0,1fr)] gap-x-3 gap-y-2 text-[14px]">
      <dt class="texto-2">Apresentado</dt><dd class="m-0">{{ data(proposicao.data_apresentacao) }}</dd>
      <template v-if="proposicao.temas?.length">
        <dt class="texto-2">Temas</dt>
        <dd class="m-0">
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
    <p v-else class="texto-2 m-0 text-[14px]">Texto completo não informado pela Câmara.</p>
    <a v-if="proposicao.url_pagina" :href="proposicao.url_pagina" class="botao botao-contorno" target="_blank" rel="noopener">
      <span class="icone" aria-hidden="true">open_in_new</span>Ver no site da Câmara
    </a>
  </div>
</template>
