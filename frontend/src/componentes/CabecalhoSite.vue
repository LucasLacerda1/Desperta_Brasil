<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { TEMA_ESCURO_LIGADO, alternarTema, temaAtual } from '../util/tema.js'
import MenuLateral from './MenuLateral.vue'
import { portal } from '../services/api.js'
import { ANOS, CAMPOS_DO_FILTRO, MESES } from '../util/busca.js'

const rota = useRoute()
const roteador = useRouter()
const termo = ref(rota.query.q || '')
const tema = ref(temaAtual())
const avisoVoz = ref(false)
const menuAberto = ref(false)
const botaoMenu = ref(null)

function fecharMenu() {
  menuAberto.value = false
  // O foco volta para o botao que abriu o menu (teclado e leitor de tela)
  botaoMenu.value?.focus()
}

watch(() => rota.query.q, (q) => { termo.value = q || '' })

// Filtros da busca: abrem num painel embaixo da barra (dia, mes, ano e tema)
const filtroAberto = ref(false)
const filtros = reactive({ dia: '', mes: '', ano: '', tema: '' })
const temas = ref([])
const avisoFiltro = ref('')
const caixaBusca = ref(null)
function fecharFiltroFora(evento) {
  if (evento.type === 'keydown' ? evento.key === 'Escape' : !caixaBusca.value?.contains(evento.target)) filtroAberto.value = false
}
watch(filtroAberto, (aberto) => {
  const acao = aberto ? 'addEventListener' : 'removeEventListener'
  document[acao]('mousedown', fecharFiltroFora)
  document[acao]('keydown', fecharFiltroFora)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', fecharFiltroFora)
  document.removeEventListener('keydown', fecharFiltroFora)
})
const filtrosAtivos = computed(() => CAMPOS_DO_FILTRO.filter((c) => String(filtros[c]).trim()).length)

watch(() => rota.query, (q) => {
  if (rota.name !== 'busca') return
  for (const c of CAMPOS_DO_FILTRO) filtros[c] = q[c] || ''
}, { immediate: true })

function abrirFiltro() {
  filtroAberto.value = !filtroAberto.value
  avisoFiltro.value = ''
  if (filtroAberto.value && !temas.value.length) portal.temas().then((r) => { temas.value = r.itens }).catch(() => {})
}

function limparFiltros() {
  for (const c of CAMPOS_DO_FILTRO) filtros[c] = ''
}

function buscar() {
  const q = termo.value.trim()
  if (!q) {
    if (filtroAberto.value) avisoFiltro.value = 'Escreva na barra o assunto que você procura.'
    document.getElementById('busca-topo')?.focus()
    return
  }
  const query = { q }
  for (const c of CAMPOS_DO_FILTRO) if (String(filtros[c]).trim()) query[c] = String(filtros[c]).trim()
  filtroAberto.value = false
  avisoFiltro.value = ''
  roteador.push({ name: 'busca', query })
}

function trocarTema() {
  tema.value = alternarTema()
}
</script>

<template>
  <header class="bg-cabecalho text-cabecalho-texto">
    <!-- Celular: menu e marca numa linha, busca embaixo; computador: tudo numa linha -->
    <div class="conteudo flex flex-wrap items-center gap-x-3 gap-y-2.5 py-3 sm:flex-nowrap sm:gap-x-6">
      <button
        ref="botaoMenu" type="button"
        class="flex size-11 flex-none cursor-pointer items-center justify-center rounded-full border-none bg-transparent text-cabecalho-texto hover:bg-[#2e3d4e]"
        :aria-expanded="menuAberto" aria-label="Abrir o menu" @click="menuAberto = true"
      >
        <span class="icone text-[28px]" aria-hidden="true">menu</span>
      </button>
      <RouterLink to="/" class="flex flex-none items-center gap-2.5 text-cabecalho-texto no-underline hover:text-cabecalho-texto">
        <span class="icone text-[34px] text-marca" aria-hidden="true">wb_twilight</span>
        <span class="flex flex-col leading-[1.1]">
          <span class="serifa text-[22px] font-bold sm:text-[26px]">Desperta Brasil</span>
          <span class="hidden text-[13px] text-cabecalho-texto-2 lg:inline">A Câmara dos Deputados em linguagem simples</span>
        </span>
      </RouterLink>

      <div ref="caixaBusca" class="relative basis-full sm:mx-auto sm:max-w-[600px] sm:flex-1 sm:basis-auto">
      <form
        class="flex items-center gap-2 rounded-[28px] border border-borda bg-superficie py-1 pr-1.5 pl-[18px] focus-within:outline-[3px] focus-within:outline-offset-2 focus-within:outline-foco focus-within:outline-solid"
        role="search" @submit.prevent="buscar"
      >
        <label for="busca-topo" class="so-leitor">Buscar notícias</label>
        <span class="icone text-texto-2" aria-hidden="true">search</span>
        <input
          id="busca-topo" v-model="termo" type="search" placeholder="Busque um assunto: salário mínimo, vacinas, escolas…"
          class="min-w-0 flex-1 border-none bg-transparent py-2.5 text-texto [font:inherit] focus:outline-none"
        >
        <button
          type="button" class="relative flex size-11 cursor-pointer items-center justify-center rounded-full border-none bg-transparent text-texto hover:bg-faixa"
          :class="{ 'bg-faixa': filtroAberto }" :aria-expanded="filtroAberto" aria-controls="painel-filtros"
          :aria-label="filtrosAtivos ? `Filtrar a busca (${filtrosAtivos} ativos)` : 'Filtrar a busca'" @click="abrirFiltro"
        >
          <span class="icone text-[24px]" aria-hidden="true">tune</span>
          <span v-if="filtrosAtivos" class="absolute top-1 right-1 flex size-4 items-center justify-center rounded-full bg-destaque-forte text-[11px] font-bold text-sobre-destaque" aria-hidden="true">{{ filtrosAtivos }}</span>
        </button>
        <button type="button" class="flex size-11 cursor-pointer items-center justify-center rounded-full border-none bg-principal text-sobre-principal" aria-label="Buscar por voz" @click="avisoVoz = !avisoVoz">
          <span class="icone" aria-hidden="true">mic</span>
        </button>
      </form>

      <!-- Filtros: painel pequeno, suspenso embaixo da barra (nao empurra a pagina) -->
      <div
        v-if="filtroAberto" id="painel-filtros"
        class="absolute inset-x-0 top-full z-40 mt-2 rounded-2xl bg-superficie p-3 text-texto shadow-[0_8px_24px_rgba(24,26,32,0.2)]"
      >
        <form class="flex flex-wrap items-end gap-2 [&_label]:text-[12px] [&_label]:font-medium [&_label]:text-texto-2" @submit.prevent="buscar">
          <div class="flex w-[72px] flex-col gap-0.5">
            <label for="f-dia">Dia</label>
            <input id="f-dia" v-model="filtros.dia" type="number" min="1" max="31" inputmode="numeric" placeholder="—" class="campo-texto min-h-9 w-full px-2 text-[14px]">
          </div>
          <div class="flex w-[124px] flex-col gap-0.5">
            <label for="f-mes">Mês</label>
            <select id="f-mes" v-model="filtros.mes" class="campo-texto min-h-9 w-full px-2 text-[14px]">
              <option value="">Todos</option>
              <option v-for="(m, i) in MESES" :key="m" :value="String(i + 1)">{{ m }}</option>
            </select>
          </div>
          <div class="flex w-[88px] flex-col gap-0.5">
            <label for="f-ano">Ano</label>
            <select id="f-ano" v-model="filtros.ano" class="campo-texto min-h-9 w-full px-2 text-[14px]">
              <option value="">Todos</option>
              <option v-for="a in ANOS" :key="a" :value="String(a)">{{ a }}</option>
            </select>
          </div>
          <div class="flex min-w-[150px] flex-1 flex-col gap-0.5">
            <label for="f-tema">Tema</label>
            <select id="f-tema" v-model="filtros.tema" class="campo-texto min-h-9 w-full px-2 text-[14px]">
              <option value="">Todos</option>
              <option v-for="t in temas" :key="t.cod_tema" :value="String(t.cod_tema)">{{ t.nome }}</option>
            </select>
          </div>
          <div class="flex items-center gap-3">
            <button type="submit" class="botao botao-principal min-h-9 px-4 text-[14px]">Aplicar</button>
            <button
              type="button" class="cursor-pointer border-none bg-transparent p-0 text-[14px] text-link underline [font:inherit] disabled:cursor-default disabled:text-texto-2 disabled:no-underline"
              :disabled="!filtrosAtivos" @click="limparFiltros"
            >Limpar</button>
          </div>
          <p v-if="avisoFiltro" class="m-0 w-full text-[13px] font-medium text-erro" role="alert">{{ avisoFiltro }}</p>
        </form>
      </div>
      </div>

      <button
        v-if="TEMA_ESCURO_LIGADO"
        type="button" class="flex size-11 flex-none cursor-pointer items-center justify-center rounded-full border border-cabecalho-texto-2 bg-transparent text-cabecalho-texto"
        :aria-label="tema === 'escuro' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'" @click="trocarTema"
      >
        <span class="icone" aria-hidden="true">{{ tema === 'escuro' ? 'light_mode' : 'dark_mode' }}</span>
      </button>
    </div>
    <p v-if="avisoVoz" class="conteudo m-0 pb-3 text-[14px] text-cabecalho-texto-2" role="status">
      A busca por voz (Whisper) ainda não está disponível. Por enquanto, digite o assunto.
    </p>
    <MenuLateral :aberto="menuAberto" @fechar="fecharMenu" />
  </header>
</template>
