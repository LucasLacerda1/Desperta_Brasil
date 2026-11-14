<script setup>
// RF12: busca por palavras, com filtro por dia, mes e ano (horario de Brasilia; a API converte) e por tema.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { mensagemDeErro, portal } from '../services/api.js'
import CartaoNoticia from '../componentes/CartaoNoticia.vue'
import Paginacao from '../componentes/Paginacao.vue'

const rota = useRoute()
const roteador = useRouter()
const temas = ref([])
const filtros = reactive({ q: '', dia: '', mes: '', ano: '', tema: '' })
const resultado = ref(null)
const carregando = ref(false)
const erro = ref('')

const MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
const anoAtual = new Date().getFullYear()
const anos = [anoAtual, anoAtual - 1, anoAtual - 2]
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
  <div class="conteudo pagina">
    <h1 class="serifa">Busca</h1>
    <form class="cartao filtros" role="search" @submit.prevent="enviar">
      <div class="campo largo">
        <label for="b-q">O que você procura?</label>
        <input id="b-q" v-model="filtros.q" type="search" placeholder="Ex.: piso salarial dos professores" required>
      </div>
      <div class="campo">
        <label for="b-dia">Dia</label>
        <input id="b-dia" v-model="filtros.dia" type="number" min="1" max="31" inputmode="numeric" placeholder="Todos">
      </div>
      <div class="campo">
        <label for="b-mes">Mês</label>
        <select id="b-mes" v-model="filtros.mes">
          <option value="">Todos</option>
          <option v-for="(m, i) in MESES" :key="m" :value="String(i + 1)">{{ m }}</option>
        </select>
      </div>
      <div class="campo">
        <label for="b-ano">Ano</label>
        <select id="b-ano" v-model="filtros.ano">
          <option value="">Todos</option>
          <option v-for="a in anos" :key="a" :value="String(a)">{{ a }}</option>
        </select>
      </div>
      <div class="campo medio">
        <label for="b-tema">Tema</label>
        <select id="b-tema" v-model="filtros.tema">
          <option value="">Todos os temas</option>
          <option v-for="t in temas" :key="t.cod_tema" :value="String(t.cod_tema)">{{ t.nome }}</option>
        </select>
      </div>
      <button type="submit" class="botao botao-principal"><span class="icone" aria-hidden="true">search</span>Buscar</button>
    </form>

    <p v-if="carregando" class="carregando">Buscando…</p>
    <p v-else-if="erro" class="carregando" role="alert">{{ erro }}</p>
    <template v-else-if="resultado">
      <p class="texto-2 total" role="status">
        {{ resultado.total }} {{ resultado.total === 1 ? 'notícia encontrada' : 'notícias encontradas' }} para “{{ rota.query.q }}”
      </p>
      <p v-if="!resultado.total" class="carregando">Nada encontrado. Tente outras palavras ou tire o filtro de data.</p>
      <div class="lista">
        <div v-for="n in resultado.itens" :key="n.id" class="cartao"><CartaoNoticia :noticia="n" com-tema /></div>
      </div>
      <Paginacao :pagina="resultado.pagina" :paginas="resultado.paginas" @ir="irPara" />
    </template>
    <p v-else class="carregando">Digite um assunto para buscar nas notícias publicadas.</p>
  </div>
</template>

<style scoped>
.pagina { padding-block: 28px 16px; display: flex; flex-direction: column; gap: 20px; }
h1 { margin: 0; font-size: clamp(28px, 4vw, 36px); }
.filtros { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 16px; }
.campo { display: flex; flex-direction: column; gap: 6px; flex: 1 1 90px; }
.campo.largo { flex: 1 1 100%; }
.campo.medio { flex: 2 1 220px; }
label { font-size: 14px; font-weight: 500; }
input, select {
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--borda);
  background: var(--superficie-2);
  color: var(--texto);
  font: inherit;
  width: 100%;
}
.total { margin: 0; font-size: 15px; }
.lista { display: flex; flex-direction: column; gap: 16px; }
</style>
