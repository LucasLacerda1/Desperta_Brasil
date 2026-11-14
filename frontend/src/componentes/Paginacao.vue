<script setup>
defineProps({ pagina: { type: Number, required: true }, paginas: { type: Number, required: true } })
defineEmits(['ir'])
</script>

<template>
  <nav v-if="paginas > 1" class="paginacao" aria-label="Páginas">
    <button type="button" class="botao botao-contorno" :disabled="pagina <= 1" @click="$emit('ir', pagina - 1)">
      <span class="icone" aria-hidden="true">chevron_left</span>Anterior
    </button>
    <span class="texto-2">Página {{ pagina }} de {{ paginas }}</span>
    <button type="button" class="botao botao-contorno" :disabled="pagina >= paginas" @click="$emit('ir', pagina + 1)">
      Próxima<span class="icone" aria-hidden="true">chevron_right</span>
    </button>
  </nav>
</template>

<style scoped>
.paginacao { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 16px; font-size: 14px; }
</style>
