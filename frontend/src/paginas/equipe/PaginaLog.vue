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
      <h1>Log do sistema</h1>
      <p class="texto-2">Tudo o que o coletor, a IA e a equipe registraram. Os erros da Câmara (por exemplo, um registro que sumiu da API) também ficam aqui.</p>
    </header>

    <div class="filtros">
      <div role="group" aria-label="Filtrar por nível" class="chips">
        <button
          v-for="n in NIVEIS" :key="n.valor" type="button" class="chip" :class="{ ativo: filtros.nivel === n.valor }"
          :aria-pressed="filtros.nivel === n.valor" @click="filtros.nivel = n.valor"
        >{{ n.nome }}</button>
      </div>
      <label class="so-leitor" for="f-modulo">Módulo</label>
      <select id="f-modulo" v-model="filtros.modulo">
        <option v-for="m in MODULOS" :key="m.valor" :value="m.valor">{{ m.nome }}</option>
      </select>
      <span v-if="filtros.coleta" class="filtro-coleta">
        Só da coleta nº {{ filtros.coleta }}
        <button type="button" class="tirar" aria-label="Tirar o filtro da coleta" @click="tirarColeta"><span class="icone" aria-hidden="true">close</span></button>
      </span>
    </div>

    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <section class="cartao" aria-label="Registros do log">
      <p class="texto-2 total">{{ lista.total.toLocaleString('pt-BR') }} {{ lista.total === 1 ? 'registro' : 'registros' }}</p>
      <p v-if="carregando" class="texto-2">Carregando…</p>
      <p v-else-if="!lista.itens.length" class="texto-2">Nenhum registro com esses filtros.</p>
      <ol v-else class="registros">
        <li v-for="r in lista.itens" :key="r.id" :class="r.nivel">
          <span class="icone nivel" :aria-label="r.nivel">{{ ICONES[r.nivel] || 'info' }}</span>
          <div class="conteudo-registro">
            <div class="cabeca">
              <strong>{{ r.acao }}</strong>
              <span class="texto-2">{{ r.modulo }} · {{ dataHora(r.data_hora) }}</span>
              <span v-if="r.entidade" class="texto-2">· {{ r.entidade }} {{ r.entidade_id }}</span>
              <RouterLink v-if="r.coleta_id && !filtros.coleta" :to="{ name: 'log', query: { coleta: r.coleta_id } }" class="texto-2" @click="filtros.coleta = String(r.coleta_id)">· coleta {{ r.coleta_id }}</RouterLink>
            </div>
            <p>{{ r.descricao }}</p>
          </div>
        </li>
      </ol>
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
.filtro-coleta { display: inline-flex; align-items: center; gap: 4px; padding: 0 4px 0 14px; min-height: 40px; border-radius: 20px; background: var(--faixa); font-size: 14px; }
.tirar { background: none; border: none; width: 32px; height: 32px; cursor: pointer; color: var(--texto); }
.erro { margin: 0; color: var(--erro); font-weight: 500; }
.total { margin: 0 0 8px; font-size: 14px; }

.registros { list-style: none; margin: 0; padding: 0; }
.registros li { display: flex; gap: 12px; padding: 12px 4px; border-bottom: 1px solid var(--linha); }
.nivel { font-size: 20px; color: var(--texto-2); }
li.aviso .nivel { color: var(--destaque-forte); }
li.erro .nivel { color: var(--erro); }
.conteudo-registro { min-width: 0; }
.cabeca { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: baseline; font-size: 14px; }
.conteudo-registro p { margin: 4px 0 0; font-size: 14px; overflow-wrap: anywhere; }
.pe { padding-top: 12px; }
</style>
