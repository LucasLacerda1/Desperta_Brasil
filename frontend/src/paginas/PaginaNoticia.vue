<script setup>
// RF18: a noticia pelo slug, com fonte oficial, votacao (RF09) e andamento da proposicao.
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { mensagemDeErro, portal } from '../services/api.js'
import { dataHora } from '../util/datas.js'
import { iconeDoTema } from '../temas.js'
import SecaoVotacao from '../componentes/SecaoVotacao.vue'
import SecaoAndamento from '../componentes/SecaoAndamento.vue'
import QuadroProposicao from '../componentes/QuadroProposicao.vue'
import ComoFoiFeita from '../componentes/ComoFoiFeita.vue'

const rota = useRoute()
const noticia = ref(null)
const votacao = ref(null)
const proposicao = ref(null)
const carregando = ref(true)
const erro = ref('')
const avisoOuvir = ref(false)

// O corpo vem dividido em secoes (25.14): cada uma com titulo e texto. Dentro do texto,
// "### " abre uma atualizacao e linhas com "- " viram lista.
function blocos(texto) {
  const saida = []
  for (const parte of (texto || '').split(/\n\s*\n/)) {
    const linhas = parte.split('\n').map((l) => l.trim()).filter(Boolean)
    if (!linhas.length) continue
    if (linhas[0].startsWith('### ')) {
      saida.push({ tipo: 'sub', texto: linhas.shift().slice(4) })
      if (!linhas.length) continue
    }
    if (linhas.every((l) => l.startsWith('- '))) saida.push({ tipo: 'lista', itens: linhas.map((l) => l.slice(2)) })
    else saida.push({ tipo: 'p', texto: linhas.join('\n') })
  }
  return saida
}
const secoes = computed(() => (noticia.value?.secoes || [{ titulo: null, texto: noticia.value?.corpo }])
  .map((s) => ({ ...s, blocos: blocos(s.texto), lacunas: s.titulo === 'O que a Câmara não informou', atualizacoes: s.titulo === 'Atualizações' })))
// Endereco no meio do texto vira link
function partes(texto) {
  return texto.split(/(https?:\/\/\S+[^\s.,;)])/).map((t, i) => ({ link: i % 2 === 1, t }))
}

async function carregar(slug) {
  carregando.value = true
  erro.value = ''
  noticia.value = votacao.value = proposicao.value = null
  try {
    const n = await portal.noticia(slug)
    noticia.value = n
    document.title = `${n.titulo} — Desperta Brasil`
    const fonteVotacao = n.fontes.find((f) => f.tipo === 'votacao')
    const fonteProposicao = n.fontes.find((f) => f.tipo === 'proposicao')
    // A votacao e a proposicao sao complementos: se uma falhar, a noticia aparece do mesmo jeito.
    if (fonteVotacao) votacao.value = await portal.votacao(fonteVotacao.ref_id).catch(() => null)
    const idProposicao = fonteProposicao?.ref_id || votacao.value?.proposicoes_afetadas?.[0]?.id
    if (idProposicao) proposicao.value = await portal.proposicao(idProposicao).catch(() => null)
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}

watch(() => rota.params.slug, (slug) => slug && carregar(slug), { immediate: true })
</script>

<template>
  <div class="conteudo pagina">
    <p v-if="carregando" class="carregando">Carregando a notícia…</p>
    <div v-else-if="erro" class="carregando" role="alert">
      <p>{{ erro }}</p>
      <RouterLink to="/" class="botao botao-principal">Voltar ao início</RouterLink>
    </div>

    <template v-else>
      <nav class="trilha texto-2" aria-label="Você está em">
        <RouterLink to="/">Início</RouterLink> ›
        <RouterLink :to="{ name: 'tema', params: { cod: noticia.tema.cod_tema } }">{{ noticia.tema.nome }}</RouterLink>
      </nav>

      <div class="colunas">
        <article class="artigo">
          <RouterLink :to="{ name: 'tema', params: { cod: noticia.tema.cod_tema } }" class="etiqueta-tema">
            <span class="icone" aria-hidden="true">{{ iconeDoTema(noticia.tema) }}</span>{{ noticia.tema.nome }}
          </RouterLink>
          <h1 class="serifa">{{ noticia.titulo }}</h1>
          <p class="lide">{{ noticia.resumo }}</p>

          <div class="barra-acoes">
            <button type="button" class="botao ouvir" @click="avisoOuvir = !avisoOuvir">
              <span class="icone" aria-hidden="true">play_arrow</span>Ouvir a notícia
            </button>
            <span class="texto-2 datas">
              Publicada em {{ dataHora(noticia.publicado_em) }}
              <template v-if="noticia.alterado_em"> · alterada em {{ dataHora(noticia.alterado_em) }}</template>
              <span v-if="noticia.atualizada" class="selo-atualizada"><span class="icone" aria-hidden="true">update</span>{{ noticia.atualizacoes }} {{ noticia.atualizacoes === 1 ? 'atualização' : 'atualizações' }}</span>
            </span>
          </div>
          <p v-if="avisoOuvir" class="texto-2 aviso" role="status">
            A leitura em voz alta (Piper) entra na Fase 5. Neste protótipo o botão só mostra onde ela vai ficar.
          </p>

          <div class="corpo serifa">
            <section v-for="(s, i) in secoes" :key="i" class="secao" :class="{ lacunas: s.lacunas, atualizacoes: s.atualizacoes }">
              <h2 v-if="s.titulo" class="titulo-secao">
                <span v-if="s.lacunas" class="icone" aria-hidden="true">report</span>
                <span v-else-if="s.atualizacoes" class="icone" aria-hidden="true">update</span>{{ s.titulo }}
              </h2>
              <template v-for="(b, j) in s.blocos" :key="j">
                <h3 v-if="b.tipo === 'sub'" class="sub">{{ b.texto }}</h3>
                <ul v-else-if="b.tipo === 'lista'"><li v-for="(it, k) in b.itens" :key="k">{{ it }}</li></ul>
                <p v-else><template v-for="(x, k) in partes(b.texto)" :key="k"><a v-if="x.link" :href="x.t" target="_blank" rel="noopener">{{ x.t }}</a><template v-else>{{ x.t }}</template></template></p>
              </template>
            </section>
          </div>

          <SecaoVotacao v-if="votacao" :votacao="votacao" />
          <SecaoAndamento v-if="proposicao" :proposicao="proposicao" />
          <ComoFoiFeita :noticia="noticia" />
        </article>

        <aside v-if="proposicao" class="lateral" aria-label="O projeto">
          <QuadroProposicao :proposicao="proposicao" />
          <div v-if="proposicao.noticias?.length > 1" class="cartao outras">
            <h2>Outras notícias deste projeto</h2>
            <template v-for="n in proposicao.noticias" :key="n.slug">
              <RouterLink v-if="n.slug !== noticia.slug" :to="{ name: 'noticia', params: { slug: n.slug } }">{{ n.titulo }}</RouterLink>
            </template>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
.pagina { padding-block: 20px 16px; }
.trilha { font-size: 14px; margin-bottom: 20px; }
.colunas { display: flex; flex-wrap: wrap; gap: 40px; align-items: flex-start; }
.artigo { flex: 999 1 600px; min-width: 0; display: flex; flex-direction: column; gap: 24px; }
.lateral { flex: 1 1 300px; min-width: 0; display: flex; flex-direction: column; gap: 16px; }

h1 { margin: 0; font-size: clamp(30px, 4.5vw, 44px); line-height: 1.15; font-weight: 700; }
.lide { margin: 0; font-size: 20px; line-height: 1.55; }
.barra-acoes {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 24px;
  padding: 12px 0;
  border-top: 1px solid var(--linha);
  border-bottom: 1px solid var(--linha);
}
.ouvir { background: var(--destaque-forte); color: var(--sobre-destaque); }
.datas { font-size: 14px; }
.aviso { margin: -12px 0 0; font-size: 14px; }

.corpo { font-size: 19px; line-height: 1.7; display: flex; flex-direction: column; gap: 16px; }
.corpo p { margin: 0; white-space: pre-line; overflow-wrap: anywhere; }
.secao { display: flex; flex-direction: column; gap: 12px; }
.titulo-secao { font-family: inherit; font-size: 22px; margin: 12px 0 0; display: flex; align-items: center; gap: 8px; }
.titulo-secao .icone { color: var(--link); font-size: 24px; }
.sub { font-size: 17px; margin: 8px 0 0; color: var(--texto-2); }
.corpo ul { margin: 0; padding-left: 22px; display: flex; flex-direction: column; gap: 6px; }
.secao.lacunas { border-left: 4px solid var(--aviso, var(--principal)); padding: 4px 0 4px 18px; font-size: 17px; }
.secao.atualizacoes { border-top: 1px solid var(--linha); padding-top: 8px; }
.selo-atualizada { display: inline-flex; align-items: center; gap: 4px; margin-left: 8px; padding: 2px 10px; border-radius: 999px; background: var(--faixa); color: var(--texto); font-size: 13px; }
.selo-atualizada .icone { font-size: 16px; }

.outras { display: flex; flex-direction: column; gap: 10px; font-size: 15px; }
.outras h2 { margin: 0; font-size: 16px; }

@media (max-width: 600px) {
  .lide { font-size: 18px; }
  .corpo { font-size: 18px; }
  .colunas { gap: 24px; }
}
</style>
