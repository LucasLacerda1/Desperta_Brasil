<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import CabecalhoSite from './componentes/CabecalhoSite.vue'
import FaixaColeta from './componentes/FaixaColeta.vue'
import RodapeSite from './componentes/RodapeSite.vue'
import AvisoCookies from './componentes/AvisoCookies.vue'

const rota = useRoute()
// A area da equipe tem o proprio desenho (menu lateral), sem o cabecalho do portal.
const naEquipe = computed(() => rota.path.startsWith('/equipe'))
</script>

<template>
  <a class="pular" href="#principal">Pular para o conteúdo</a>
  <template v-if="naEquipe">
    <RouterView />
  </template>
  <template v-else>
    <CabecalhoSite />
    <FaixaColeta />
    <main id="principal">
      <RouterView />
    </main>
    <RodapeSite />
    <AvisoCookies />
  </template>
</template>

<style scoped>
.pular {
  position: absolute;
  left: -9999px;
  top: 8px;
  z-index: 100;
  background: var(--superficie);
  color: var(--texto);
  padding: 10px 16px;
  border-radius: 8px;
}
.pular:focus { left: 8px; }
main { min-height: 60vh; }
</style>
