<script setup>
// RF12: busca por palavras, com filtro por dia, mes e ano (horario de Brasilia; a API converte) e por tema.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mensagemDeErro, portal } from '../services/api.js'
import CartaoNoticia from '../componentes/CartaoNoticia.vue'
import Paginacao from '../componentes/Paginacao.vue'
import { ANOS, MESES } from '../util/busca.js'

const rota = useRoute()
const roteador = useRouter()
const temas = ref([])
const filtros = reactive({ q: '', dia: '', mes: '', ano: '', tema: '' })
const resultado = ref(null)
const carregando = ref(false)
const erro = ref('')

const anos = ANOS
const pagina = computed(() => Number(rota.query.pagina) || 1)

onMounted(async () => {
  document.title = 'Busca — Desperta Brasil'
  try {
    temas.value = (await portal.temas()).itens
  } catch {
    temas.value = []
  }
})

// A busca vive no endereco (?q=...&ano=...): da para copiar o link e voltar com o botao do navegador.
async function buscarDoEndereco() {
  for (const campo of Object.keys(filtros)) filtros[campo] = rota.query[campo] || ''
  erro.value = ''
  resultado.value = null
  if (!filtros.q.trim()) return
  carregando.value = true
  try {
    const params = { q: filtros.q, pagina: pagina.value, por_pagina: 10 }
    for (const campo of ['dia', 'mes', 'ano', 'tema']) if (filtros[campo]) params[campo] = filtros[campo]
    resultado.value = await portal.busca(params)
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}
watch(() => rota.query, buscarDoEndereco, { immediate: true })

function enviar() {
  const query = {}
  for (const campo of Object.keys(filtros)) if (String(filtros[campo]).trim()) query[campo] = String(filtros[campo]).trim()
  roteador.push({ name: 'busca', query })
}
const irPara = (p) => roteador.push({ name: 'busca', query: { ...rota.query, pagina: p } })
</script>

<template>
  <div class="conteudo flex flex-col gap-5 pt-7 pb-4">
    <h1 class="serifa m-0 text-[clamp(28px,4vw,36px)]">Busca</h1>
    <!-- Celular: um campo por linha; computador: os filtros lado a lado -->
    <form class="cartao grid grid-cols-2 items-end gap-4 md:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,2fr)_auto]" role="search" @submit.prevent="enviar">
      <div class="flex flex-col gap-1.5 col-span-full">
        <label for="b-q" class="text-[14px] font-medium">O que você procura?</label>
        <input id="b-q" v-model="filtros.q" type="search" placeholder="Ex.: piso salarial dos professores" required class="campo-texto min-h-11 w-full px-3">
      </div>
      <div class="flex flex-col gap-1.5">
        <label for="b-dia" class="text-[14px] font-medium">Dia</label>
        <input id="b-dia" v-model="filtros.dia" type="number" min="1" max="31" inputmode="numeric" placeholder="Todos" class="campo-texto min-h-11 w-full px-3">
      </div>
      <div class="flex flex-col gap-1.5">
        <label for="b-mes" class="text-[14px] font-medium">Mês</label>
        <select id="b-mes" v-model="filtros.mes" class="campo-texto min-h-11 w-full px-3">
          <option value="">Todos</option>
          <option v-for="(m, i) in MESES" :key="m" :value="String(i + 1)">{{ m }}</option>
        </select>
      </div>
      <div class="flex flex-col gap-1.5">
        <label for="b-ano" class="text-[14px] font-medium">Ano</label>
        <select id="b-ano" v-model="filtros.ano" class="campo-texto min-h-11 w-full px-3">
          <option value="">Todos</option>
          <option v-for="a in anos" :key="a" :value="String(a)">{{ a }}</option>
        </select>
      </div>
      <div class="flex flex-col gap-1.5">
        <label for="b-tema" class="text-[14px] font-medium">Tema</label>
        <select id="b-tema" v-model="filtros.tema" class="campo-texto min-h-11 w-full px-3">
          <option value="">Todos os temas</option>
          <option v-for="t in temas" :key="t.cod_tema" :value="String(t.cod_tema)">{{ t.nome }}</option>
        </select>
      </div>
      <button type="submit" class="botao botao-principal col-span-full md:col-span-1"><span class="icone" aria-hidden="true">search</span>Buscar</button>
    </form>

    <p v-if="carregando" class="carregando">Buscando…</p>
    <p v-else-if="erro" class="carregando" role="alert">{{ erro }}</p>
    <template v-else-if="resultado">
      <p class="texto-2 m-0 text-[15px]" role="status">
        {{ resultado.total }} {{ resultado.total === 1 ? 'notícia encontrada' : 'notícias encontradas' }} para “{{ rota.query.q }}”
      </p>
      <p v-if="!resultado.total" class="carregando">Nada encontrado. Tente outras palavras ou tire o filtro de data.</p>
      <div class="flex flex-col gap-4">
        <div v-for="n in resultado.itens" :key="n.id" class="cartao"><CartaoNoticia :noticia="n" com-tema /></div>
      </div>
      <Paginacao :pagina="resultado.pagina" :paginas="resultado.paginas" @ir="irPara" />
    </template>
    <p v-else class="carregando">Digite um assunto para buscar nas notícias publicadas.</p>
  </div>
</template>
