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
  <a class="absolute top-2 -left-[9999px] z-[100] rounded-lg bg-superficie px-4 py-2.5 text-texto focus:left-2" href="#principal">Pular para o conteúdo</a>
  <template v-if="naEquipe">
    <RouterView />
  </template>
  <template v-else>
    <CabecalhoSite />
    <FaixaColeta />
    <main id="principal" class="min-h-[60vh]">
      <RouterView />
    </main>
    <RodapeSite />
    <AvisoCookies />
  </template>
</template>
