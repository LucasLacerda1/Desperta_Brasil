<script setup>
// Autoria da proposta: os 3 primeiros nomes (na ordem de assinatura da Camara) e, se houver mais,
// um botao que estende a lista inteira. "aberta" vem da pagina, para o cartao do resumo poder abrir.
import { computed } from 'vue'

const props = defineProps({
  autores: { type: Array, required: true },
  aberta: { type: Boolean, default: false },
})
const emit = defineEmits(['update:aberta'])

const VISIVEIS = 3
const nomes = computed(() => props.autores.map((a) => a.nome))
const resto = computed(() => Math.max(nomes.value.length - VISIVEIS, 0))

function juntar(lista) {
  if (lista.length <= 1) return lista.join('')
  return `${lista.slice(0, -1).join(', ')} e ${lista.at(-1)}`
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <p class="m-0">
      <template v-if="!resto">{{ juntar(nomes) }}</template>
      <template v-else>
        {{ nomes.slice(0, VISIVEIS).join(', ') }}
        <button
          type="button" class="cursor-pointer border-none bg-transparent p-0 font-medium text-link underline [font:inherit]"
          :aria-expanded="aberta" aria-controls="lista-autores" @click="emit('update:aberta', !aberta)"
        >{{ aberta ? 'mostrar menos' : `e mais ${resto}` }}</button>
      </template>
    </p>
    <ul
      v-if="resto && aberta" id="lista-autores"
      class="m-0 flex max-h-72 list-none flex-wrap gap-1.5 overflow-y-auto p-0"
      :aria-label="`Todos os ${nomes.length} autores`"
    >
      <li v-for="(n, i) in nomes" :key="i" class="rounded-full bg-faixa px-2.5 py-0.5 text-[13px]">{{ n }}</li>
    </ul>
  </div>
</template>
