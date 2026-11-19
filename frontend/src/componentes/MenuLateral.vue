<script setup>
// Menu lateral (botao de tres tracinhos no cabecalho): toda a navegacao do portal num lugar so.
// Abre por cima da pagina; fecha no X, clicando fora, com Esc ou ao escolher um destino.
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { portal } from '../services/api.js'
import { iconeDoTema } from '../temas.js'

const props = defineProps({ aberto: { type: Boolean, default: false } })
const emit = defineEmits(['fechar'])

const PRINCIPAIS = [
  { nome: 'Início', icone: 'home', para: { name: 'inicio' } },
  { nome: 'Buscar notícias', icone: 'search', para: { name: 'busca' } },
  { nome: 'Todos os temas', icone: 'category', para: { name: 'temas' } },
  { nome: 'Como funciona', icone: 'help', para: { name: 'como-funciona' } },
]

const rota = useRoute()
const temas = ref([])
const botaoFechar = ref(null)
let carregou = false

const item = 'flex items-center gap-4 rounded-full px-4 py-2.5 text-[15px] text-texto no-underline hover:bg-faixa hover:text-texto'
const ativo = 'bg-faixa font-semibold'

function teclas(evento) {
  if (evento.key === 'Escape') emit('fechar')
}

watch(() => props.aberto, async (aberto) => {
  document.body.style.overflow = aberto ? 'hidden' : ''
  if (aberto) {
    document.addEventListener('keydown', teclas)
    if (!carregou) {
      carregou = true
      // So os temas que ja tem noticia publicada
      portal.temas().then((r) => { temas.value = r.itens.filter((t) => t.noticias_publicadas > 0) }).catch(() => { carregou = false })
    }
    await nextTick()
    botaoFechar.value?.focus()
  } else {
    document.removeEventListener('keydown', teclas)
  }
}, { immediate: true })
// Escolheu um destino: fecha
watch(() => rota.fullPath, () => props.aberto && emit('fechar'))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', teclas)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div v-if="aberto" class="fixed inset-0 z-50">
      <div class="absolute inset-0 bg-[rgba(24,26,32,0.45)]" aria-hidden="true" @click="emit('fechar')"></div>
      <div
        role="dialog" aria-modal="true" aria-label="Menu do portal"
        class="absolute inset-y-0 left-0 flex w-[300px] max-w-[85vw] flex-col overflow-y-auto bg-superficie px-3 pb-6 shadow-[0_0_24px_rgba(0,0,0,0.25)]"
      >
        <div class="sticky top-0 flex items-center gap-2 bg-superficie py-3 pl-1">
          <button
            ref="botaoFechar" type="button" class="flex size-11 cursor-pointer items-center justify-center rounded-full border-none bg-transparent text-texto hover:bg-faixa"
            aria-label="Fechar o menu" @click="emit('fechar')"
          >
            <span class="icone text-[26px]" aria-hidden="true">close</span>
          </button>
          <span class="flex items-center gap-2 text-[18px] font-bold">
            <span class="icone text-[28px] text-destaque-forte" aria-hidden="true">wb_twilight</span>
            <span class="serifa">Desperta Brasil</span>
          </span>
        </div>

        <nav aria-label="Navegação principal" class="flex flex-col gap-0.5 border-b border-linha pb-3">
          <RouterLink v-for="l in PRINCIPAIS" :key="l.nome" :to="l.para" :class="item" :exact-active-class="ativo">
            <span class="icone text-[24px] text-destaque-forte" aria-hidden="true">{{ l.icone }}</span>{{ l.nome }}
          </RouterLink>
        </nav>

        <nav v-if="temas.length" aria-label="Temas" class="flex flex-col gap-0.5 border-b border-linha py-3">
          <span class="px-4 pb-1 text-[12px] font-semibold tracking-[0.06em] text-texto-2 uppercase">Temas</span>
          <RouterLink
            v-for="t in temas" :key="t.cod_tema" :to="{ name: 'tema', params: { cod: t.cod_tema } }"
            :class="item" :exact-active-class="ativo"
          >
            <span class="icone text-[24px] text-destaque-forte" aria-hidden="true">{{ iconeDoTema(t) }}</span>
            <span class="min-w-0 flex-1 leading-snug">{{ t.nome }}</span>
          </RouterLink>
        </nav>

        <nav aria-label="Equipe" class="pt-3">
          <RouterLink to="/equipe" :class="item">
            <span class="icone text-[24px] text-texto-2" aria-hidden="true">lock</span>Área da equipe
          </RouterLink>
        </nav>
      </div>
    </div>
  </Teleport>
</template>
