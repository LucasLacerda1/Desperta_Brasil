<script setup>
// RF09: andamento da proposicao (as 20 tramitacoes mais recentes vem na API).
// Texto vazio e "sem valor" (decisao 14.1): despacho vazio nao aparece.
import { computed, ref } from 'vue'
import { data } from '../util/datas.js'

const props = defineProps({ proposicao: { type: Object, required: true } })

const tudo = ref(false)
const itens = computed(() => props.proposicao.tramitacoes?.itens || [])
const total = computed(() => props.proposicao.tramitacoes?.total || itens.value.length)
const visiveis = computed(() => (tudo.value ? itens.value : itens.value.slice(0, 5)))
// A API manda so a sigla do orgao; as duas mais comuns ganham o nome por extenso (na Fase 5, o nome deve vir da API).
const ORGAOS = { PLEN: 'Plenário', MESA: 'Mesa Diretora' }
const orgao = (sigla) => ORGAOS[sigla] || sigla
</script>

<template>
  <section v-if="itens.length" class="cartao andamento" aria-labelledby="t-andamento">
    <h2 id="t-andamento">Andamento do projeto</h2>
    <ol>
      <li v-for="t in visiveis" :key="t.sequencia">
        <span class="quando texto-2">{{ data(t.data_hora) }}</span>
        <span class="trilho" aria-hidden="true"><span class="ponto"></span><span class="fio"></span></span>
        <span class="passo">
          <strong>{{ t.descricao }}</strong> · {{ orgao(t.orgao) }}
          <template v-if="t.despacho"><br>{{ t.despacho }}</template>
        </span>
      </li>
    </ol>
    <div class="acoes">
      <button v-if="itens.length > 5" type="button" class="link-botao" @click="tudo = !tudo">
        {{ tudo ? 'Mostrar só as 5 mais recentes' : `Mostrar as ${itens.length} mais recentes` }}
      </button>
      <a v-if="proposicao.url_pagina" :href="proposicao.url_pagina" target="_blank" rel="noopener">
        Ver as {{ total }} etapas no site da Câmara<span class="icone pequeno" aria-hidden="true">open_in_new</span>
      </a>
    </div>
  </section>
</template>

<style scoped>
.andamento { padding: 28px; display: flex; flex-direction: column; gap: 16px; }
h2 { margin: 0; font-size: 22px; }
ol { list-style: none; margin: 0; padding: 0; }
li { display: grid; grid-template-columns: 96px 20px minmax(0, 1fr); gap: 12px; }
.quando { font-size: 14px; padding-top: 2px; }
.trilho { display: flex; flex-direction: column; align-items: center; }
.ponto { width: 12px; height: 12px; border-radius: 6px; background: var(--principal); margin-top: 5px; }
.fio { flex: 1; width: 2px; background: var(--linha); }
li:last-child .fio { display: none; }
.passo { padding-bottom: 20px; font-size: 15px; overflow-wrap: anywhere; }
.acoes { display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: 15px; font-weight: 500; }
.link-botao { background: none; border: none; padding: 0; font: inherit; font-weight: 500; color: var(--link); cursor: pointer; text-decoration: underline; }
.pequeno { font-size: 16px; }
@media (max-width: 600px) {
  .andamento { padding: 20px; }
  li { grid-template-columns: 20px minmax(0, 1fr); }
  .quando { grid-column: 2; grid-row: 1; padding: 0; }
  .trilho { grid-column: 1; grid-row: 1 / span 2; }
  .passo { grid-column: 2; }
}
</style>
