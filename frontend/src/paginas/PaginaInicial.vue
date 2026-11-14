<script setup>
// RF10: manchete (a mais recente), as ultimas publicadas e as principais de cada tema.
import { onMounted, ref } from 'vue'
import { mensagemDeErro, portal } from '../services/api.js'
import { data } from '../util/datas.js'
import { iconeDoTema } from '../temas.js'
import NavTemas from '../componentes/NavTemas.vue'
import CartaoNoticia from '../componentes/CartaoNoticia.vue'

const manchete = ref(null)
const ultimas = ref([])
const secoes = ref([])
const carregando = ref(true)
const erro = ref('')

onMounted(async () => {
  try {
    const [recentes, principal] = await Promise.all([portal.recentes({ por_pagina: 6 }), portal.principal(3)])
    manchete.value = recentes.itens[0] || null
    ultimas.value = recentes.itens.slice(1)
    secoes.value = principal.secoes
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
})
</script>

<template>
  <NavTemas />
  <div class="conteudo pagina">
    <p v-if="carregando" class="carregando">Carregando as notícias…</p>
    <p v-else-if="erro" class="carregando" role="alert">{{ erro }}</p>
    <p v-else-if="!manchete" class="carregando">Ainda não há notícias publicadas.</p>

    <template v-else>
      <section class="topo">
        <article class="cartao manchete">
          <div class="linha-tema">
            <RouterLink :to="{ name: 'tema', params: { cod: manchete.tema.cod_tema } }" class="etiqueta-tema">
              <span class="icone" aria-hidden="true">{{ iconeDoTema(manchete.tema) }}</span>{{ manchete.tema.nome }}
            </RouterLink>
            <span class="texto-2">Publicada em {{ data(manchete.publicado_em) }}</span>
          </div>
          <h1 class="serifa">
            <RouterLink :to="{ name: 'noticia', params: { slug: manchete.slug } }">{{ manchete.titulo }}</RouterLink>
          </h1>
          <p class="resumo">{{ manchete.resumo }}</p>
          <div>
            <RouterLink :to="{ name: 'noticia', params: { slug: manchete.slug } }" class="botao botao-principal">
              Ler a notícia<span class="icone" aria-hidden="true">arrow_forward</span>
            </RouterLink>
          </div>
        </article>

        <aside class="cartao ultimas" aria-labelledby="t-ultimas">
          <h2 id="t-ultimas"><span class="icone" aria-hidden="true">schedule</span>Últimas publicadas</h2>
          <RouterLink v-for="n in ultimas" :key="n.id" :to="{ name: 'noticia', params: { slug: n.slug } }" class="ultima">
            <span class="ultima-titulo">{{ n.titulo }}</span>
            <span class="texto-2 ultima-meta">{{ n.tema.nome }} · {{ data(n.publicado_em) }}</span>
          </RouterLink>
        </aside>
      </section>

      <section aria-labelledby="t-temas" class="por-tema">
        <h2 id="t-temas" class="serifa titulo-secao">Por tema</h2>
        <div class="grade">
          <div v-for="s in secoes" :key="s.tema.cod_tema" class="cartao secao">
            <h3 class="nome-tema">
              <span class="roda"><span class="icone" aria-hidden="true">{{ iconeDoTema(s.tema) }}</span></span>
              {{ s.tema.nome }}
            </h3>
            <template v-for="(n, i) in s.noticias" :key="n.id">
              <hr v-if="i > 0">
              <CartaoNoticia :noticia="n" :com-resumo="i === 0" />
            </template>
            <RouterLink :to="{ name: 'tema', params: { cod: s.tema.cod_tema } }" class="ver-tudo">
              Ver tudo em {{ s.tema.nome }}
            </RouterLink>
          </div>
        </div>
      </section>
    </template>

    <section id="como-funciona" class="como" aria-labelledby="t-como">
      <h2 id="t-como" class="serifa titulo-secao">Como cada notícia é feita</h2>
      <div class="passos">
        <div class="passo">
          <span class="icone" aria-hidden="true">cloud_download</span>
          <strong>1. Os dados vêm da Câmara</strong>
          <span>De hora em hora buscamos votações, eventos e projetos na API de Dados Abertos da Câmara dos Deputados.</span>
        </div>
        <div class="passo">
          <span class="icone" aria-hidden="true">edit_note</span>
          <strong>2. O sistema escreve um rascunho</strong>
          <span>Com frases prontas e só com os dados oficiais: nenhum número, nome ou data é inventado.</span>
        </div>
        <div class="passo">
          <span class="icone" aria-hidden="true">fact_check</span>
          <strong>3. Uma pessoa revisa</strong>
          <span>Nada é publicado sem revisão da equipe. Toda notícia mostra a fonte oficial e quem publicou.</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pagina { display: flex; flex-direction: column; gap: 48px; padding-block: 16px 0; }

.topo { display: flex; flex-wrap: wrap; gap: 24px; align-items: stretch; }
.manchete { flex: 999 1 560px; min-width: 0; padding: 32px; display: flex; flex-direction: column; justify-content: center; gap: 20px; }
.linha-tema { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; font-size: 14px; }
.manchete h1 { margin: 0; font-size: clamp(30px, 4.6vw, 48px); line-height: 1.12; font-weight: 700; }
.manchete h1 a { color: var(--texto); text-decoration: none; }
.manchete h1 a:hover { text-decoration: underline; }
.manchete .resumo { margin: 0; font-size: 20px; line-height: 1.55; }

.ultimas { flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; }
.ultimas h2 { margin: 0 0 8px; font-size: 18px; display: flex; align-items: center; gap: 8px; }
.ultimas h2 .icone { color: var(--link); }
.ultima { display: block; padding: 12px 0; border-top: 1px solid var(--linha); text-decoration: none; color: var(--texto); }
.ultima:hover .ultima-titulo { text-decoration: underline; }
.ultima-titulo { display: block; font-weight: 500; line-height: 1.35; }
.ultima-meta { display: block; font-size: 13px; margin-top: 4px; }

.titulo-secao { margin: 0 0 20px; font-size: 28px; font-weight: 700; }
.grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; }
.secao { display: flex; flex-direction: column; gap: 16px; }
.nome-tema { margin: 0; display: flex; align-items: center; gap: 8px; font-size: 18px; }
.roda {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: 18px;
  background: var(--superficie-2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.roda .icone { color: var(--destaque); }
hr { width: 100%; border: none; border-top: 1px solid var(--linha); margin: 0; }
.ver-tudo { font-size: 14px; font-weight: 500; margin-top: auto; }

.como { background: #263b5c; color: #f3eee6; border-radius: 16px; padding: 32px; scroll-margin-top: 16px; }
.passos { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 24px; }
.passo { display: flex; flex-direction: column; gap: 8px; }
.passo .icone { font-size: 32px; color: #dcb48f; }
.passo strong { font-size: 17px; }
.passo span:last-child { font-size: 15px; color: #e1dad4; }

@media (max-width: 600px) {
  .manchete { padding: 20px; }
  .como { padding: 24px 20px; }
}
</style>
