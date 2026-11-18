<script setup>
// Molde das telas da equipe (RF16): barra lateral, conferencia do login e do papel.
// A pagina recebe quem esta logado pelo evento "pronto" e so carrega os dados depois dele.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { equipe } from '../services/api.js'
import { alternarTema, temaAtual } from '../util/tema.js'
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
  <div class="equipe">
    <nav class="lateral" aria-label="Área da equipe">
      <div class="topo">
        <RouterLink to="/" class="marca">
          <span class="icone sol" aria-hidden="true">wb_twilight</span>
          <span class="serifa">Desperta · equipe</span>
        </RouterLink>
        <button type="button" class="menu" :aria-expanded="menuAberto" aria-controls="menu-equipe" @click="menuAberto = !menuAberto">
          <span class="icone" aria-hidden="true">{{ menuAberto ? 'close' : 'menu' }}</span>
          <span class="so-leitor">Menu</span>
        </button>
      </div>
      <div id="menu-equipe" class="itens" :class="{ aberto: menuAberto }">
        <RouterLink
          v-for="s in STATUS_DA_FILA" :key="s.valor" class="item" :class="{ ativo: statusAtivo === s.valor }"
          :to="{ name: 'fila', query: s.valor === 'rascunho' ? {} : { status: s.valor } }"
          :aria-current="statusAtivo === s.valor ? 'page' : undefined" @click="menuAberto = false"
        >
          <span class="icone" aria-hidden="true">{{ s.icone }}</span>
          <span class="nome">{{ s.nome }}</span>
          <span v-if="statusAtivo === s.valor && conta !== null" class="conta">{{ conta.toLocaleString('pt-BR') }}</span>
        </RouterLink>
        <span class="grupo">SÓ ADMIN</span>
        <template v-for="a in ADMIN" :key="a.rota">
          <RouterLink v-if="ehAdmin" :to="{ name: a.rota }" class="item" active-class="ativo" @click="menuAberto = false">
            <span class="icone" aria-hidden="true">{{ a.icone }}</span><span class="nome">{{ a.nome }}</span>
          </RouterLink>
          <span v-else class="item apagado" :title="'Só para admin'">
            <span class="icone" aria-hidden="true">{{ a.icone }}</span><span class="nome">{{ a.nome }}</span>
          </span>
        </template>
        <div class="pe">
          <span v-if="eu">{{ eu.nome }} · {{ eu.papel }}</span>
          <div class="pe-botoes">
            <button type="button" class="link-claro" @click="trocarTema">{{ tema === 'escuro' ? 'Tema claro' : 'Tema escuro' }}</button>
            <button type="button" class="link-claro" @click="sair">Sair</button>
          </div>
        </div>
      </div>
    </nav>

    <main id="principal" class="area">
      <p v-if="!eu" class="texto-2">Conferindo o login…</p>
      <div v-else-if="bloqueado" class="cartao bloqueio" role="alert">
        <span class="icone" aria-hidden="true">lock</span>
        <div>
          <strong>Esta tela é só para quem tem o papel admin.</strong>
          <p class="texto-2">O seu papel é {{ eu.papel }}. Peça a um admin, se precisar destes dados.</p>
        </div>
      </div>
      <slot v-else :eu="eu" />
    </main>
  </div>
</template>

<style scoped>
.equipe { min-height: 100vh; display: flex; flex-wrap: wrap; }

.lateral {
  flex: 1 1 220px;
  max-width: 260px;
  background: var(--rodape);
  color: #e1dad4;
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
}
.topo { display: flex; align-items: center; justify-content: space-between; }
.marca { display: flex; align-items: center; gap: 8px; padding: 0 8px 20px; text-decoration: none; color: #f3eee6; font-size: 18px; font-weight: 700; }
.sol { font-size: 26px; color: #dcb48f; }
.menu { display: none; background: none; border: none; color: #f3eee6; width: 44px; height: 44px; cursor: pointer; }
.itens { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  color: #e1dad4;
  text-decoration: none;
}
.item:hover { color: #f3eee6; background: #2f3442; }
.item .nome { flex: 1; }
.item.ativo { background: #38495b; color: #f3eee6; font-weight: 500; }
.item .conta { font-size: 13px; }
.item.apagado { color: #b8a798; cursor: not-allowed; }
.item.apagado:hover { background: transparent; color: #b8a798; }
.grupo { padding: 20px 12px 6px; font-size: 12px; letter-spacing: 0.06em; color: #b8a798; }
.pe { margin-top: auto; padding: 16px 12px 0; border-top: 1px solid #38495b; font-size: 14px; display: flex; flex-direction: column; gap: 8px; color: #f3eee6; }
.pe-botoes { display: flex; gap: 16px; }
.link-claro { background: none; border: none; padding: 0; font: inherit; color: #dcb48f; text-decoration: underline; cursor: pointer; }

.area { flex: 999 1 640px; min-width: 0; padding: 28px 32px; display: flex; flex-direction: column; gap: 16px; }
.bloqueio { display: flex; gap: 12px; align-items: flex-start; border-left: 4px solid var(--erro); }
.bloqueio .icone { color: var(--erro); }
.bloqueio p { margin: 4px 0 0; }

@media (max-width: 760px) {
  .lateral { max-width: none; flex-basis: 100%; padding: 12px; }
  .marca { padding-bottom: 0; }
  .menu { display: inline-flex; align-items: center; justify-content: center; }
  .itens { display: none; padding-top: 12px; }
  .itens.aberto { display: flex; }
  .area { padding: 20px 16px; }
}
</style>
