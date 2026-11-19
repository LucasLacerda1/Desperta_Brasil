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
  <article class="flex flex-col gap-1.5">
    <RouterLink v-if="comTema && noticia.tema" :to="{ name: 'tema', params: { cod: noticia.tema.cod_tema } }" class="etiqueta-tema">
      <span class="icone" aria-hidden="true">{{ iconeDoTema(noticia.tema) }}</span>{{ noticia.tema.nome }}
    </RouterLink>
    <RouterLink :to="{ name: 'noticia', params: { slug: noticia.slug } }" class="group flex flex-col gap-1.5 text-texto no-underline hover:text-texto">
      <h3 class="serifa m-0 line-clamp-4 text-[20px] leading-[1.3] font-semibold group-hover:underline">{{ noticia.titulo }}</h3>
      <p v-if="comResumo" class="m-0 line-clamp-3 text-[15px]">{{ noticia.resumo }}</p>
    </RouterLink>
    <p class="texto-2 m-0 text-[13px]">
      Publicada em {{ data(noticia.publicado_em) }}
      <template v-if="noticia.alterado_em"> · alterada em {{ data(noticia.alterado_em) }}</template>
      <template v-if="noticia.atualizada"> · <strong>atualizada em {{ data(noticia.ultima_atualizacao) }}</strong></template>
    </p>
  </article>
</template>
