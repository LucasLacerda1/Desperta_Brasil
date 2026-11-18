<script setup>
// RF10: pagina inicial como hub de navegacao. So o essencial: 3 destaques, os temas com
// mais noticias e os atalhos. O resto fica no menu (tres tracinhos) e nas paginas de cada tema.
import { onMounted, ref } from 'vue'
import { mensagemDeErro, portal } from '../services/api.js'
import { data } from '../util/datas.js'
import { iconeDoTema } from '../temas.js'

const TEMAS_NA_INICIAL = 8
const ATALHOS = [
  { nome: 'Buscar notícias', texto: 'Por assunto, dia, mês ou ano', icone: 'search', para: { name: 'busca' } },
  { nome: 'Como funciona', texto: 'De onde vêm os dados e como a notícia é feita', icone: 'help', para: { name: 'como-funciona' } },
]

const destaques = ref([])
const temas = ref([])
const carregando = ref(true)
const erro = ref('')

onMounted(async () => {
  document.title = 'Desperta Brasil — a Câmara dos Deputados em linguagem simples'
  try {
    const [recentes, lista] = await Promise.all([portal.recentes({ por_pagina: 3 }), portal.temas()])
    destaques.value = recentes.itens
    // Os temas com mais noticias publicadas primeiro
    temas.value = lista.itens
      .filter((t) => t.noticias_publicadas > 0)
      .sort((a, b) => b.noticias_publicadas - a.noticias_publicadas)
      .slice(0, TEMAS_NA_INICIAL)
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
})
</script>

<template>
  <div class="conteudo flex flex-col gap-10 pt-8 sm:pt-10">
    <header class="flex flex-col gap-2">
      <h1 class="serifa m-0 text-[clamp(26px,3.6vw,36px)] leading-tight">O que a Câmara decidiu, em linguagem simples</h1>
      <p class="texto-2 m-0 text-[17px]">Votações e projetos dos deputados, com a fonte oficial em cada notícia.</p>
    </header>

    <p v-if="carregando" class="carregando">Carregando…</p>
    <p v-else-if="erro" class="carregando" role="alert">{{ erro }}</p>

    <template v-else>
      <!-- Destaques: so as 3 mais recentes -->
      <section aria-labelledby="t-destaques" class="flex flex-col gap-4">
        <h2 id="t-destaques" class="m-0 flex items-center gap-2 text-[20px]">
          <span class="icone text-[26px] text-destaque-forte" aria-hidden="true">newspaper</span>Destaques
        </h2>
        <p v-if="!destaques.length" class="texto-2 m-0">Ainda não há notícias publicadas.</p>
        <!-- A principal em destaque grande; as outras duas ao lado (no celular, embaixo) -->
        <div v-if="destaques.length" class="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <RouterLink
            :to="{ name: 'noticia', params: { slug: destaques[0].slug } }"
            class="cartao group flex flex-col justify-center gap-4 p-6 text-texto no-underline transition-shadow hover:text-texto hover:shadow-[0_4px_16px_rgba(36,39,49,0.12)] sm:p-8"
          >
            <span class="flex items-center gap-1.5 text-[14px] font-bold text-destaque">
              <span class="icone text-[22px]" aria-hidden="true">{{ iconeDoTema(destaques[0].tema) }}</span>{{ destaques[0].tema?.nome }}
            </span>
            <h3 class="serifa m-0 text-[clamp(26px,3.2vw,38px)] leading-[1.15] font-bold group-hover:underline">{{ destaques[0].titulo }}</h3>
            <p class="m-0 line-clamp-3 text-[18px] leading-[1.55]">{{ destaques[0].resumo }}</p>
            <span class="flex flex-wrap items-center gap-4">
              <span class="botao botao-principal">Ler a notícia<span class="icone" aria-hidden="true">arrow_forward</span></span>
              <span class="texto-2 text-[14px]">{{ data(destaques[0].publicado_em) }}</span>
            </span>
          </RouterLink>
          <div class="flex flex-col gap-4">
            <RouterLink
              v-for="n in destaques.slice(1)" :key="n.id" :to="{ name: 'noticia', params: { slug: n.slug } }"
              class="cartao group flex flex-1 flex-col gap-2 p-5 text-texto no-underline transition-shadow hover:text-texto hover:shadow-[0_4px_16px_rgba(36,39,49,0.12)]"
            >
              <span class="flex items-center gap-1.5 text-[13px] font-bold text-destaque">
                <span class="icone text-[20px]" aria-hidden="true">{{ iconeDoTema(n.tema) }}</span>{{ n.tema?.nome }}
              </span>
              <h3 class="serifa m-0 line-clamp-3 text-[20px] leading-[1.3] font-semibold group-hover:underline">{{ n.titulo }}</h3>
              <span class="texto-2 mt-auto text-[13px]">{{ data(n.publicado_em) }}</span>
            </RouterLink>
          </div>
        </div>
      </section>

      <!-- Navegar por tema: blocos grandes com icone -->
      <section aria-labelledby="t-temas" class="flex flex-col gap-4">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="t-temas" class="m-0 flex items-center gap-2 text-[18px]">
            <span class="icone text-[24px] text-destaque-forte" aria-hidden="true">category</span>Navegue por tema
          </h2>
          <RouterLink :to="{ name: 'temas' }" class="inline-flex items-center gap-1 text-[15px] font-medium">
            Ver todos os 32 temas<span class="icone text-[20px]" aria-hidden="true">arrow_forward</span>
          </RouterLink>
        </div>
        <!-- Blocos compactos: icone pequeno e o nome numa linha -->
        <ul class="m-0 grid list-none grid-cols-1 gap-2 p-0 sm:grid-cols-2 lg:grid-cols-4">
          <li v-for="t in temas" :key="t.cod_tema">
            <RouterLink
              :to="{ name: 'tema', params: { cod: t.cod_tema } }"
              class="cartao flex h-full items-center gap-3 px-3 py-2.5 text-texto no-underline hover:bg-faixa hover:text-texto"
            >
              <span class="flex size-9 flex-none items-center justify-center rounded-full bg-faixa">
                <span class="icone text-[22px] text-destaque-forte" aria-hidden="true">{{ iconeDoTema(t) }}</span>
              </span>
              <span class="line-clamp-2 text-[14px] leading-snug font-medium">{{ t.nome }}</span>
            </RouterLink>
          </li>
        </ul>
      </section>

      <!-- Atalhos -->
      <section aria-label="Atalhos" class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <RouterLink
          v-for="a in ATALHOS" :key="a.nome" :to="a.para"
          class="cartao flex items-center gap-4 p-4 text-texto no-underline hover:bg-faixa hover:text-texto"
        >
          <span class="flex size-12 flex-none items-center justify-center rounded-full bg-principal">
            <span class="icone text-[26px] text-sobre-principal" aria-hidden="true">{{ a.icone }}</span>
          </span>
          <span class="flex flex-col">
            <strong class="text-[16px]">{{ a.nome }}</strong>
            <span class="texto-2 text-[14px] leading-snug">{{ a.texto }}</span>
          </span>
        </RouterLink>
      </section>
    </template>
  </div>
</template>
