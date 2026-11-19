<script setup>
// Barra de votos: Sim (verde), Nao (vermelho) e outros, numa escala de "base" votos
// (os 513 deputados no Plenario). O minimo para aprovar, quando existe, vira um marco na barra.
import { computed } from 'vue'

const props = defineProps({
  sim: { type: Number, required: true },
  nao: { type: Number, required: true },
  outros: { type: Number, default: 0 },
  base: { type: Number, required: true },
  minimo: { type: Number, default: null },
  rotuloBase: { type: String, default: '' },
})

const pct = (n) => `${Math.min(100, (100 * n) / props.base).toFixed(2)}%`
const descricao = computed(() => {
  let texto = `${props.sim} votos Sim e ${props.nao} votos Não`
  if (props.minimo) texto += `; mínimo para aprovar: ${props.minimo}`
  return texto
})
</script>

<template>
  <div class="votos">
    <div class="topo">
      <span>
        <strong class="sim">Sim {{ sim }}</strong> ·
        <strong class="nao">Não {{ nao }}</strong>
      </span>
      <span v-if="rotuloBase">{{ rotuloBase }}</span>
    </div>
    <div class="barra" role="img" :aria-label="descricao">
      <div class="parte p-sim" :style="{ width: pct(sim) }"></div>
      <div class="parte p-nao" :style="{ width: pct(nao) }"></div>
      <div v-if="outros" class="parte p-outros" :style="{ width: pct(outros) }"></div>
    </div>
    <div v-if="minimo" class="marco" aria-hidden="true">
      <div class="risco" :style="{ left: pct(minimo) }"></div>
      <span class="rotulo" :style="{ left: pct(minimo) }">mínimo para aprovar: {{ minimo }}</span>
    </div>
  </div>
</template>

<style scoped>
.votos { display: flex; flex-direction: column; gap: 8px; }
.topo { display: flex; justify-content: space-between; gap: 12px; font-size: 14px; }
.sim { color: var(--sim-texto); }
.nao { color: var(--nao-texto); }
.barra { height: 20px; border-radius: 10px; background: var(--barra-fundo); overflow: hidden; display: flex; }
.p-sim { background: var(--sim); }
.p-nao { background: var(--nao); }
.p-outros { background: var(--outro-voto); }
.marco { position: relative; height: 20px; }
.risco { position: absolute; top: -32px; width: 2px; height: 34px; background: var(--texto); }
.rotulo { position: absolute; transform: translateX(-50%); font-size: 13px; white-space: nowrap; }
</style>
