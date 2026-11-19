<script setup>
defineProps({ pagina: { type: Number, required: true }, paginas: { type: Number, required: true } })
defineEmits(['ir'])
</script>

<template>
  <nav v-if="paginas > 1" class="flex flex-wrap items-center justify-center gap-4 text-[14px]" aria-label="Páginas">
    <button type="button" class="botao botao-contorno" :disabled="pagina <= 1" @click="$emit('ir', pagina - 1)">
      <span class="icone" aria-hidden="true">chevron_left</span>Anterior
    </button>
    <span class="texto-2">Página {{ pagina }} de {{ paginas }}</span>
    <button type="button" class="botao botao-contorno" :disabled="pagina >= paginas" @click="$emit('ir', pagina + 1)">
      Próxima<span class="icone" aria-hidden="true">chevron_right</span>
    </button>
  </nav>
</template>
