<script setup>
// Log do sistema (so admin, RF15): o que o coletor, a IA e a equipe fizeram, do mais novo para o mais antigo.
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { equipe, mensagemDeErro } from '../../services/api.js'
import { dataHora } from '../../util/datas.js'
import LayoutEquipe from '../../componentes/LayoutEquipe.vue'
import Paginacao from '../../componentes/Paginacao.vue'

const NIVEIS = [
  { valor: '', nome: 'Todos' },
  { valor: 'info', nome: 'Informação' },
  { valor: 'aviso', nome: 'Aviso' },
  { valor: 'erro', nome: 'Erro' },
]
const MODULOS = [
  { valor: '', nome: 'Todos os módulos' },
  { valor: 'coletor', nome: 'Coletor' },
  { valor: 'IA', nome: 'IA' },
  { valor: 'admin', nome: 'Equipe (admin)' },
]

const rota = useRoute()
const roteador = useRouter()
const filtros = reactive({ nivel: '', modulo: '', coleta: rota.query.coleta || '', pagina: 1 })
const lista = ref({ itens: [], total: 0, paginas: 1, pagina: 1 })
const carregando = ref(true)
const erro = ref('')
const pronto = ref(false)

function iniciar() {
  document.title = 'Log do sistema — Desperta Brasil'
  pronto.value = true
  carregar()
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const params = { pagina: filtros.pagina, por_pagina: 30 }
    if (filtros.nivel) params.nivel = filtros.nivel
    if (filtros.modulo) params.modulo = filtros.modulo
    if (filtros.coleta) params.coleta = filtros.coleta
    lista.value = await equipe.log(params)
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}

watch(() => [filtros.nivel, filtros.modulo, filtros.coleta], () => {
  if (!pronto.value) return
  filtros.pagina = 1
  carregar()
})

function tirarColeta() {
  filtros.coleta = ''
  roteador.replace({ name: 'log' })
}
function mudarPagina(p) {
  filtros.pagina = p
  carregar()
}
const ICONES = { info: 'info', aviso: 'warning', erro: 'error' }
</script>

<template>
  <LayoutEquipe so-admin @pronto="iniciar">
    <header>
      <h1 class="m-0 text-[28px]">Log do sistema</h1>
      <p class="texto-2 mt-1.5 mb-0 max-w-[75ch] text-[15px]">Tudo o que o coletor, a IA e a equipe registraram. Os erros da Câmara (por exemplo, um registro que sumiu da API) também ficam aqui.</p>
    </header>

    <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div role="group" aria-label="Filtrar por nível" class="flex flex-wrap gap-2">
        <button
          v-for="n in NIVEIS" :key="n.valor" type="button" class="chip" :class="{ ativo: filtros.nivel === n.valor }"
          :aria-pressed="filtros.nivel === n.valor" @click="filtros.nivel = n.valor"
        >{{ n.nome }}</button>
      </div>
      <label class="so-leitor" for="f-modulo">Módulo</label>
      <select id="f-modulo" v-model="filtros.modulo" class="filtro">
        <option v-for="m in MODULOS" :key="m.valor" :value="m.valor">{{ m.nome }}</option>
      </select>
      <span v-if="filtros.coleta" class="inline-flex min-h-10 items-center gap-1 rounded-[20px] bg-faixa pr-1 pl-3.5 text-[14px]">
        Só da coleta nº {{ filtros.coleta }}
        <button type="button" class="size-8 cursor-pointer border-none bg-transparent text-texto" aria-label="Tirar o filtro da coleta" @click="tirarColeta"><span class="icone" aria-hidden="true">close</span></button>
      </span>
    </div>

    <p v-if="erro" class="texto-erro" role="alert">{{ erro }}</p>

    <section class="cartao" aria-label="Registros do log">
      <p class="texto-2 m-0 mb-2 text-[14px]">{{ lista.total.toLocaleString('pt-BR') }} {{ lista.total === 1 ? 'registro' : 'registros' }}</p>
      <p v-if="carregando" class="texto-2">Carregando…</p>
      <p v-else-if="!lista.itens.length" class="texto-2">Nenhum registro com esses filtros.</p>
      <ol v-else class="m-0 list-none p-0">
        <li v-for="r in lista.itens" :key="r.id" class="flex gap-3 border-b border-linha px-1 py-3">
          <span class="icone text-[20px]" :class="{ aviso: 'text-destaque-forte', erro: 'text-erro' }[r.nivel] || 'text-texto-2'" :aria-label="r.nivel">{{ ICONES[r.nivel] || 'info' }}</span>
          <div class="min-w-0">
            <div class="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[14px]">
              <strong>{{ r.acao }}</strong>
              <span class="texto-2">{{ r.modulo }} · {{ dataHora(r.data_hora) }}</span>
              <span v-if="r.entidade" class="texto-2">· {{ r.entidade }} {{ r.entidade_id }}</span>
              <RouterLink v-if="r.coleta_id && !filtros.coleta" :to="{ name: 'log', query: { coleta: r.coleta_id } }" class="texto-2" @click="filtros.coleta = String(r.coleta_id)">· coleta {{ r.coleta_id }}</RouterLink>
            </div>
            <p class="mt-1 mb-0 text-[14px] [overflow-wrap:anywhere]">{{ r.descricao }}</p>
          </div>
        </li>
      </ol>
      <div class="pt-3"><Paginacao :pagina="lista.pagina || 1" :paginas="lista.paginas || 1" @ir="mudarPagina" /></div>
    </section>
  </LayoutEquipe>
</template>
