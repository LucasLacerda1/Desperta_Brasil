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
      <h1>Coletas</h1>
      <p class="texto-2">
        Cada busca na API de Dados Abertos da Câmara. "Parcial" quer dizer que parte dos itens falhou ou que a rotina parou no limite de tempo; o motivo fica no log.
      </p>
    </header>

    <div class="filtros">
      <div role="group" aria-label="Filtrar por situação" class="chips">
        <button
          v-for="s in STATUS" :key="s.valor" type="button" class="chip" :class="{ ativo: filtros.status === s.valor }"
          :aria-pressed="filtros.status === s.valor" @click="filtros.status = s.valor"
        >{{ s.nome }}</button>
      </div>
      <label class="so-leitor" for="f-recurso">O que foi coletado</label>
      <select id="f-recurso" v-model="filtros.recurso">
        <option value="">Tudo o que foi coletado</option>
        <option v-for="r in RECURSOS" :key="r" :value="r">{{ r }}</option>
      </select>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <section class="cartao" aria-label="Coletas">
      <p class="texto-2 total">{{ lista.total.toLocaleString('pt-BR') }} {{ lista.total === 1 ? 'coleta' : 'coletas' }}</p>
      <p v-if="carregando" class="texto-2">Carregando…</p>
      <p v-else-if="!lista.itens.length" class="texto-2">Nenhuma coleta com esses filtros.</p>
      <div v-else class="rolagem">
        <table>
          <thead>
            <tr>
              <th scope="col">Nº</th><th scope="col">O quê</th><th scope="col">Início</th><th scope="col">Duração</th>
              <th scope="col">Situação</th><th scope="col" class="num">Itens</th><th scope="col" class="num">Novos</th>
              <th scope="col" class="num">Atualizados</th><th scope="col" class="num">Requisições</th><th scope="col" class="num">Erros HTTP</th><th scope="col">Log</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="c in lista.itens" :key="c.id">
              <tr>
                <td>{{ c.id }}</td>
                <td><strong>{{ c.recurso }}</strong><span v-if="c.tipo" class="texto-2"> · {{ c.tipo }}</span></td>
                <td class="nowrap">{{ dataHora(c.iniciado_em) }}</td>
                <td class="nowrap">{{ duracao(c) }}</td>
                <td><span class="selo" :class="c.status">{{ NOMES_STATUS[c.status] || c.status }}</span></td>
                <td class="num">{{ c.total_itens.toLocaleString('pt-BR') }}</td>
                <td class="num">{{ c.itens_novos.toLocaleString('pt-BR') }}</td>
                <td class="num">{{ c.itens_atualizados.toLocaleString('pt-BR') }}</td>
                <td class="num">{{ (c.requisicoes ?? 0).toLocaleString('pt-BR') }}</td>
                <td class="num">{{ c.erros_http ?? 0 }}</td>
                <td><RouterLink :to="{ name: 'log', query: { coleta: c.id } }">ver</RouterLink></td>
              </tr>
              <tr v-if="c.mensagem_erro" class="mensagem"><td></td><td colspan="10">{{ c.mensagem_erro }}</td></tr>
            </template>
          </tbody>
        </table>
      </div>
      <div class="pe"><Paginacao :pagina="lista.pagina || 1" :paginas="lista.paginas || 1" @ir="mudarPagina" /></div>
    </section>
  </LayoutEquipe>
</template>

<style scoped>
h1 { margin: 0; font-size: 28px; }
header p { margin: 6px 0 0; font-size: 15px; max-width: 75ch; }
.filtros { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { min-height: 40px; padding: 0 16px; border-radius: 20px; border: 1px solid var(--borda); background: var(--superficie); color: var(--texto); font: inherit; font-size: 14px; cursor: pointer; }
.chip.ativo { background: var(--principal); border-color: var(--principal); color: var(--sobre-principal); font-weight: 500; }
select { min-height: 40px; padding: 0 12px; border-radius: 8px; border: 1px solid var(--borda); background: var(--superficie); color: var(--texto); font: inherit; }
.erro { margin: 0; color: var(--erro); font-weight: 500; }
.total { margin: 0 0 8px; font-size: 14px; }
.rolagem { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; font-size: 13px; color: var(--texto-2); font-weight: 600; padding: 8px; border-bottom: 2px solid var(--linha); white-space: nowrap; }
td { padding: 8px; border-bottom: 1px solid var(--linha); }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.nowrap { white-space: nowrap; }
.mensagem td { color: var(--erro); font-size: 13px; padding-top: 0; }
.selo { padding: 2px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; white-space: nowrap; border: 1px solid var(--linha); }
.selo.ok { color: var(--ok); border-color: var(--ok); }
.selo.parcial { background: var(--aviso-fundo); color: var(--aviso-texto); border-color: transparent; }
.selo.erro { color: var(--erro); border-color: var(--erro); }
.pe { padding-top: 12px; }
</style>
