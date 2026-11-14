<script setup>
import { data } from '../util/datas.js'
import { iconeDoTema } from '../temas.js'

defineProps({
  noticia: { type: Object, required: true },
  comTema: { type: Boolean, default: false },
  comResumo: { type: Boolean, default: true },
})
</script>

<template>
  <article class="item">
    <RouterLink v-if="comTema && noticia.tema" :to="{ name: 'tema', params: { cod: noticia.tema.cod_tema } }" class="etiqueta-tema">
      <span class="icone" aria-hidden="true">{{ iconeDoTema(noticia.tema) }}</span>{{ noticia.tema.nome }}
    </RouterLink>
    <RouterLink :to="{ name: 'noticia', params: { slug: noticia.slug } }" class="link">
      <h3 class="serifa titulo">{{ noticia.titulo }}</h3>
      <p v-if="comResumo" class="resumo">{{ noticia.resumo }}</p>
    </RouterLink>
    <p class="meta texto-2">
      Publicada em {{ data(noticia.publicado_em) }}
      <template v-if="noticia.alterado_em"> · alterada em {{ data(noticia.alterado_em) }}</template>
    </p>
  </article>
</template>

<style scoped>
.item { display: flex; flex-direction: column; gap: 6px; }
.link { text-decoration: none; color: var(--texto); display: flex; flex-direction: column; gap: 6px; }
.link:hover .titulo { text-decoration: underline; }
.titulo {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.resumo {
  margin: 0;
  font-size: 15px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta { margin: 0; font-size: 13px; }
</style>
