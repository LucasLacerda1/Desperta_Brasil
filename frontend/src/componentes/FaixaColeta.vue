<script setup>
// RNF05: mostra a ultima coleta concluida e avisa quando os dados estao desatualizados.
import { onMounted, ref } from 'vue'
import { portal } from '../services/api.js'
import { quando } from '../util/datas.js'

const situacao = ref(null)
const falhou = ref(false)

onMounted(async () => {
  try {
    situacao.value = await portal.situacao()
  } catch {
    falhou.value = true
  }
})
</script>

<template>
  <div v-if="situacao || falhou" class="faixa" :class="{ alerta: falhou || situacao?.dados_desatualizados }" role="status">
    <div class="conteudo linha">
      <template v-if="falhou">
        <span class="icone" aria-hidden="true">cloud_off</span>
        <strong>Não conseguimos falar com o servidor do portal.</strong>
      </template>
      <template v-else-if="situacao.dados_desatualizados">
        <span class="icone" aria-hidden="true">warning</span>
        <strong>Dados desatualizados.</strong>
        <span>{{ situacao.aviso || `A última coleta concluída foi ${quando(situacao.ultima_coleta_concluida)}.` }}</span>
      </template>
      <template v-else>
        <span class="bolinha" aria-hidden="true"></span>
        <strong>Dados da Câmara atualizados {{ quando(situacao.ultima_coleta_concluida) }}.</strong>
        <RouterLink :to="{ path: '/', hash: '#como-funciona' }">De onde vêm os dados?</RouterLink>
      </template>
    </div>
  </div>
</template>

<style scoped>
.faixa { background: var(--faixa); color: var(--texto); font-size: 14px; }
.faixa.alerta { background: var(--aviso-fundo); color: var(--aviso-texto); }
.linha { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding-block: 10px; }
.linha strong { font-weight: 500; }
.bolinha { width: 10px; height: 10px; border-radius: 5px; background: var(--ok); }
.faixa a { font-weight: 500; }
</style>
