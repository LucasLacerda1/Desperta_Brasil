<script setup>
// Molde das telas da equipe (RF16): barra lateral, conferencia do login e do papel.
// A pagina recebe quem esta logado pelo evento "pronto" e so carrega os dados depois dele.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { equipe } from '../services/api.js'
import { TEMA_ESCURO_LIGADO, alternarTema, temaAtual } from '../util/tema.js'
import { STATUS_DA_FILA } from '../util/equipe.js'

const props = defineProps({
  // Tela so para admin (equipe, coletas e log): o editor ve um aviso no lugar
  soAdmin: { type: Boolean, default: false },
  // Total da lista aberta na fila, mostrado ao lado do status ativo
  conta: { type: Number, default: null },
})
const emit = defineEmits(['pronto'])

const ADMIN = [
  { rota: 'equipe-membros', nome: 'Equipe', icone: 'group' },
  { rota: 'coletas', nome: 'Coletas', icone: 'cloud_sync' },
  { rota: 'log', nome: 'Log do sistema', icone: 'receipt_long' },
]

const rota = useRoute()
const roteador = useRouter()
const eu = ref(null)
const tema = ref(temaAtual())
const menuAberto = ref(false)

const statusAtivo = computed(() => (rota.name === 'fila' ? rota.query.status || 'rascunho' : null))
const ehAdmin = computed(() => eu.value?.papel === 'admin')
const bloqueado = computed(() => props.soAdmin && eu.value && !ehAdmin.value)

onMounted(async () => {
  try {
    eu.value = (await equipe.eu()).administrador
  } catch {
    roteador.replace({ name: 'entrar', query: { volta: rota.fullPath } })
    return
  }
  if (!bloqueado.value) emit('pronto', eu.value)
})

async function sair() {
  await equipe.sair().catch(() => {})
  roteador.push({ name: 'entrar' })
}
function trocarTema() {
  tema.value = alternarTema()
}
</script>

<template>
  <!-- Computador: menu lateral + area; celular: menu recolhido no topo -->
  <div class="flex min-h-screen flex-col md:flex-row">
    <nav class="flex flex-col bg-rodape p-3 text-[#f3eee6] md:w-[260px] md:flex-none md:px-3 md:py-5" aria-label="Área da equipe">
      <div class="flex items-center justify-between">
        <RouterLink to="/" class="flex items-center gap-2 px-2 text-[18px] font-bold text-[#ffffff] no-underline hover:text-[#ffffff] md:pb-5">
          <span class="icone text-[26px] text-marca" aria-hidden="true">wb_twilight</span>
          <span class="serifa">Desperta · equipe</span>
        </RouterLink>
        <button
          type="button" class="inline-flex size-11 cursor-pointer items-center justify-center border-none bg-transparent text-[#f3eee6] md:hidden"
          :aria-expanded="menuAberto" aria-controls="menu-equipe" @click="menuAberto = !menuAberto"
        >
          <span class="icone" aria-hidden="true">{{ menuAberto ? 'close' : 'menu' }}</span>
          <span class="so-leitor">Menu</span>
        </button>
      </div>
      <div id="menu-equipe" class="flex-1 flex-col gap-1 pt-3 md:flex md:pt-0" :class="menuAberto ? 'flex' : 'hidden'">
        <RouterLink
          v-for="s in STATUS_DA_FILA" :key="s.valor"
          :to="{ name: 'fila', query: s.valor === 'rascunho' ? {} : { status: s.valor } }"
          class="flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 no-underline" :class="statusAtivo === s.valor ? 'bg-[#2e3d4e] font-medium text-[#ffffff] hover:text-[#ffffff]' : 'text-[#f3eee6] hover:bg-[#262a34] hover:text-[#ffffff]'"
          :aria-current="statusAtivo === s.valor ? 'page' : undefined" @click="menuAberto = false"
        >
          <span class="icone" aria-hidden="true">{{ s.icone }}</span>
          <span class="flex-1">{{ s.nome }}</span>
          <span v-if="statusAtivo === s.valor && conta !== null" class="text-[13px]">{{ conta.toLocaleString('pt-BR') }}</span>
        </RouterLink>
        <span class="px-3 pt-5 pb-1.5 text-[12px] tracking-[0.06em] text-[#d8ccbf]">SÓ ADMIN</span>
        <template v-for="a in ADMIN" :key="a.rota">
          <RouterLink
            v-if="ehAdmin" :to="{ name: a.rota }" class="flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 no-underline text-[#f3eee6] hover:bg-[#262a34] hover:text-[#ffffff]"
            active-class="bg-[#2e3d4e] font-medium text-[#ffffff]!" @click="menuAberto = false"
          >
            <span class="icone" aria-hidden="true">{{ a.icone }}</span><span class="flex-1">{{ a.nome }}</span>
          </RouterLink>
          <span v-else class="flex items-center gap-2.5 rounded-[10px] px-3 py-2.5 no-underline cursor-not-allowed text-[#d8ccbf]" title="Só para admin">
            <span class="icone" aria-hidden="true">{{ a.icone }}</span><span class="flex-1">{{ a.nome }}</span>
          </span>
        </template>
        <div class="mt-auto flex flex-col gap-2 border-t border-[#353a45] px-3 pt-4 text-[14px] text-[#f3eee6]">
          <span v-if="eu">{{ eu.nome }} · {{ eu.papel }}</span>
          <div class="flex gap-4 [&_button]:cursor-pointer [&_button]:border-none [&_button]:bg-transparent [&_button]:p-0 [&_button]:text-[#ecc9a6] [&_button]:underline [&_button]:[font:inherit]">
            <button v-if="TEMA_ESCURO_LIGADO" type="button" @click="trocarTema">{{ tema === 'escuro' ? 'Tema claro' : 'Tema escuro' }}</button>
            <button type="button" @click="sair">Sair</button>
          </div>
        </div>
      </div>
    </nav>

    <main id="principal" class="flex min-w-0 flex-1 flex-col gap-4 px-4 py-5 md:px-8 md:py-7">
      <p v-if="!eu" class="texto-2">Conferindo o login…</p>
      <div v-else-if="bloqueado" class="cartao flex items-start gap-3 border-l-4 border-erro" role="alert">
        <span class="icone text-erro" aria-hidden="true">lock</span>
        <div>
          <strong>Esta tela é só para quem tem o papel admin.</strong>
          <p class="texto-2 mt-1 mb-0">O seu papel é {{ eu.papel }}. Peça a um admin, se precisar destes dados.</p>
        </div>
      </div>
      <slot v-else :eu="eu" />
    </main>
  </div>
</template>
