<script setup>
// Coletas (so admin, RF04): cada chamada do coletor a API da Camara, da mais nova para a mais antiga.
import { reactive, ref, watch } from 'vue'
import { equipe, mensagemDeErro } from '../../services/api.js'
import { dataHora } from '../../util/datas.js'
import LayoutEquipe from '../../componentes/LayoutEquipe.vue'
import Paginacao from '../../componentes/Paginacao.vue'

const STATUS = [
  { valor: '', nome: 'Todas' },
  { valor: 'ok', nome: 'Concluídas' },
  { valor: 'parcial', nome: 'Parciais' },
  { valor: 'erro', nome: 'Com erro' },
]
const RECURSOS = ['proposicoes', 'votacoes', 'eventos', 'deputados', 'partidos', 'legislaturas', 'orgaos', 'orgao_membros', 'mesa', 'liderancas', 'blocos', 'frentes', 'temas']

const filtros = reactive({ status: '', recurso: '', pagina: 1 })
const lista = ref({ itens: [], total: 0, paginas: 1, pagina: 1 })
const carregando = ref(true)
const erro = ref('')
const pronto = ref(false)

function iniciar() {
  document.title = 'Coletas — Desperta Brasil'
  pronto.value = true
  carregar()
}

async function carregar() {
  carregando.value = true
  erro.value = ''
  try {
    const params = { pagina: filtros.pagina, por_pagina: 25 }
    if (filtros.status) params.status = filtros.status
    if (filtros.recurso) params.recurso = filtros.recurso
    lista.value = await equipe.coletas(params)
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}

watch(() => [filtros.status, filtros.recurso], () => {
  if (!pronto.value) return
  filtros.pagina = 1
  carregar()
})

function mudarPagina(p) {
  filtros.pagina = p
  carregar()
}

function duracao(c) {
  if (!c.finalizado_em) return 'não terminou'
  const s = Math.round((new Date(c.finalizado_em) - new Date(c.iniciado_em)) / 1000)
  if (s < 60) return `${s} s`
  return `${Math.floor(s / 60)} min ${s % 60} s`
}
const NOMES_STATUS = { ok: 'concluída', parcial: 'parcial', erro: 'erro' }
</script>

<template>
  <LayoutEquipe so-admin @pronto="iniciar">
    <header>
      <h1 class="m-0 text-[28px]">Coletas</h1>
      <p class="texto-2 mt-1.5 mb-0 max-w-[75ch] text-[15px]">
        Cada busca na API de Dados Abertos da Câmara. "Parcial" quer dizer que parte dos itens falhou ou que a rotina parou no limite de tempo; o motivo fica no log.
      </p>
    </header>

    <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div role="group" aria-label="Filtrar por situação" class="flex flex-wrap gap-2">
        <button
          v-for="s in STATUS" :key="s.valor" type="button" class="chip" :class="{ ativo: filtros.status === s.valor }"
          :aria-pressed="filtros.status === s.valor" @click="filtros.status = s.valor"
        >{{ s.nome }}</button>
      </div>
      <label class="so-leitor" for="f-recurso">O que foi coletado</label>
      <select id="f-recurso" v-model="filtros.recurso" class="filtro">
        <option value="">Tudo o que foi coletado</option>
        <option v-for="r in RECURSOS" :key="r" :value="r">{{ r }}</option>
      </select>
    </div>

    <p v-if="erro" class="texto-erro" role="alert">{{ erro }}</p>

    <section class="cartao" aria-label="Coletas">
      <p class="texto-2 m-0 mb-2 text-[14px]">{{ lista.total.toLocaleString('pt-BR') }} {{ lista.total === 1 ? 'coleta' : 'coletas' }}</p>
      <p v-if="carregando" class="texto-2">Carregando…</p>
      <p v-else-if="!lista.itens.length" class="texto-2">Nenhuma coleta com esses filtros.</p>
      <div v-else class="overflow-x-auto">
        <table class="tabela">
          <thead>
            <tr>
              <th scope="col">Nº</th><th scope="col">O quê</th><th scope="col">Início</th><th scope="col">Duração</th>
              <th scope="col">Situação</th><th scope="col" class="text-right tabular-nums">Itens</th><th scope="col" class="text-right tabular-nums">Novos</th>
              <th scope="col" class="text-right tabular-nums">Atualizados</th><th scope="col" class="text-right tabular-nums">Requisições</th><th scope="col" class="text-right tabular-nums">Erros HTTP</th><th scope="col">Log</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="c in lista.itens" :key="c.id">
              <tr>
                <td>{{ c.id }}</td>
                <td><strong>{{ c.recurso }}</strong><span v-if="c.tipo" class="texto-2"> · {{ c.tipo }}</span></td>
                <td class="whitespace-nowrap">{{ dataHora(c.iniciado_em) }}</td>
                <td class="whitespace-nowrap">{{ duracao(c) }}</td>
                <td><span class="selo" :class="{ ok: 'border-ok text-ok', parcial: 'border-transparent bg-aviso-fundo text-aviso-texto', erro: 'border-erro text-erro' }[c.status]">{{ NOMES_STATUS[c.status] || c.status }}</span></td>
                <td class="text-right tabular-nums">{{ c.total_itens.toLocaleString('pt-BR') }}</td>
                <td class="text-right tabular-nums">{{ c.itens_novos.toLocaleString('pt-BR') }}</td>
                <td class="text-right tabular-nums">{{ c.itens_atualizados.toLocaleString('pt-BR') }}</td>
                <td class="text-right tabular-nums">{{ (c.requisicoes ?? 0).toLocaleString('pt-BR') }}</td>
                <td class="text-right tabular-nums">{{ c.erros_http ?? 0 }}</td>
                <td><RouterLink :to="{ name: 'log', query: { coleta: c.id } }">ver</RouterLink></td>
              </tr>
              <tr v-if="c.mensagem_erro" class="[&_td]:pt-0 [&_td]:text-[13px] [&_td]:text-erro"><td></td><td colspan="10">{{ c.mensagem_erro }}</td></tr>
            </template>
          </tbody>
        </table>
      </div>
      <div class="pt-3"><Paginacao :pagina="lista.pagina || 1" :paginas="lista.paginas || 1" @ir="mudarPagina" /></div>
    </section>
  </LayoutEquipe>
</template>
