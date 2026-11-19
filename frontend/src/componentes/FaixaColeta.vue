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
  <div
    v-if="situacao || falhou" role="status" class="text-[14px]"
    :class="falhou || situacao?.dados_desatualizados ? 'bg-aviso-fundo text-aviso-texto' : 'bg-faixa text-texto'"
  >
    <div class="conteudo flex flex-wrap items-center gap-x-3.5 gap-y-1.5 py-2.5 [&_strong]:font-medium">
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
        <span class="size-2.5 rounded-full bg-ok" aria-hidden="true"></span>
        <strong>Dados da Câmara atualizados {{ quando(situacao.ultima_coleta_concluida) }}.</strong>
        <RouterLink to="/como-funciona" class="font-medium">De onde vêm os dados?</RouterLink>
      </template>
    </div>
  </div>
</template>
