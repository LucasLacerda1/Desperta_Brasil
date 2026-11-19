<script setup>
// RF18: a noticia pelo slug, com fonte oficial, votacao (RF09) e andamento da proposicao.
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { mensagemDeErro, portal } from '../services/api.js'
import { dataHora } from '../util/datas.js'
import { iconeDaSecao, lerSecao } from '../util/blocos.js'
import { iconeDoTema } from '../temas.js'
import SecaoVotacao from '../componentes/SecaoVotacao.vue'
import SecaoAndamento from '../componentes/SecaoAndamento.vue'
import QuadroProposicao from '../componentes/QuadroProposicao.vue'
import ComoFoiFeita from '../componentes/ComoFoiFeita.vue'
import CartaoNoticia from '../componentes/CartaoNoticia.vue'
import ListaAutores from '../componentes/ListaAutores.vue'

const rota = useRoute()
const noticia = ref(null)
const votacao = ref(null)
const proposicao = ref(null)
const carregando = ref(true)
const erro = ref('')
// Lista de autores estendida (o cartao do resumo tambem abre)
const autoresAbertos = ref(false)
async function verAutores() {
  autoresAbertos.value = true
  await nextTick()
  document.getElementById('autoria')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

// O corpo vem dividido em secoes (25.14); cada uma vira um bloco (ficha, linha do tempo, texto)
const secoes = computed(() => (noticia.value?.secoes || [{ titulo: null, texto: noticia.value?.corpo }])
  .map((s) => ({ ...s, blocos: lerSecao(s.texto), lacunas: s.titulo === 'O que a Câmara não informou' })))
// Com a votacao carregada, o quadro "Como votaram" entra no lugar do texto "Resultado da votacao"
const votacaoNoTexto = computed(() => !!votacao.value && secoes.value.some((s) => s.titulo === 'Resultado da votação'))

// "Em resumo": ate 3 cartoes no topo, so com o que a Camara informou
const resumo = computed(() => {
  const cartoes = []
  const v = votacao.value
  if (v) {
    const nominal = v.total_por_tipo && (v.total_por_tipo['Sim'] || v.total_por_tipo['Não'])
    const placar = nominal ? v.total_por_tipo : v.situacao_dos_votos?.placar_da_camara
    cartoes.push({
      rotulo: 'Resultado', icone: 'how_to_vote',
      valor: { aprovada: 'Aprovado', rejeitada: 'Rejeitado' }[v.resultado] || 'Não informado',
      cor: { aprovada: 'text-sim-texto', rejeitada: 'text-nao-texto' }[v.resultado] || '',
      extra: placar && (placar['Sim'] || placar['Não']) ? `${placar['Sim'] || 0} sim × ${placar['Não'] || 0} não` : v.situacao_dos_votos?.codigo === 'simbolica' ? 'Votação simbólica, sem placar' : '',
    })
  }
  const p = proposicao.value
  if (p) {
    const sit = p.situacao_explicada
    cartoes.push({
      rotulo: 'Situação agora', icone: 'location_on',
      valor: sit?.informada === false ? 'Não informada pela Câmara' : sit?.nome_da_camara || p.situacao || 'Não informada pela Câmara',
      extra: sit?.explicacao || '',
    })
    const autores = p.autores || []
    if (autores.length) {
      cartoes.push({
        rotulo: 'Autoria', icone: 'person',
        valor: autores[0].nome,
        extra: autores.length > 1 ? '' : p.sigla,
        maisAutores: autores.length > 1 ? autores.length - 1 : 0,
      })
    }
  }
  return cartoes
})
// Endereco no meio do texto vira link
function partes(texto) {
  return texto.split(/(https?:\/\/\S+[^\s.,;)])/).map((t, i) => ({ link: i % 2 === 1, t }))
}

async function carregar(slug) {
  carregando.value = true
  erro.value = ''
  noticia.value = votacao.value = proposicao.value = null
  autoresAbertos.value = false
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
  <div class="conteudo pt-5 pb-4">
    <p v-if="carregando" class="carregando">Carregando a notícia…</p>
    <div v-else-if="erro" class="carregando" role="alert">
      <p>{{ erro }}</p>
      <RouterLink to="/" class="botao botao-principal">Voltar ao início</RouterLink>
    </div>

    <template v-else>
      <nav class="texto-2 mb-5 text-[14px]" aria-label="Você está em">
        <RouterLink to="/">Início</RouterLink> ›
        <RouterLink :to="{ name: 'tema', params: { cod: noticia.tema.cod_tema } }">{{ noticia.tema.nome }}</RouterLink>
      </nav>

      <!-- Computador: a noticia e o quadro do projeto lado a lado; celular: um embaixo do outro -->
      <div class="grid items-start gap-6 sm:gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <article class="flex min-w-0 flex-col gap-5">
          <header class="flex flex-col gap-3">
            <RouterLink :to="{ name: 'tema', params: { cod: noticia.tema.cod_tema } }" class="etiqueta-tema">
              <span class="icone" aria-hidden="true">{{ iconeDoTema(noticia.tema) }}</span>{{ noticia.tema.nome }}
            </RouterLink>
            <h1 class="serifa m-0 text-[clamp(28px,4vw,38px)] leading-[1.15] font-bold">{{ noticia.titulo }}</h1>
            <p class="m-0 text-[18px] leading-[1.55]">{{ noticia.resumo }}</p>
            <p class="texto-2 m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-[14px]">
              <span>Publicada em {{ dataHora(noticia.publicado_em) }}</span>
              <span v-if="noticia.alterado_em">· alterada em {{ dataHora(noticia.alterado_em) }}</span>
              <span v-if="noticia.atualizada" class="inline-flex items-center gap-1 rounded-full bg-faixa px-2.5 py-0.5 text-[13px] text-texto"><span class="icone text-[16px]" aria-hidden="true">update</span>{{ noticia.atualizacoes }} {{ noticia.atualizacoes === 1 ? 'atualização' : 'atualizações' }}</span>
            </p>
          </header>

          <!-- Em resumo: o essencial em blocos curtos -->
          <section v-if="resumo.length" aria-label="Em resumo" class="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div v-for="r in resumo" :key="r.rotulo" class="cartao flex min-w-0 flex-col gap-1 p-4">
              <span class="texto-2 flex items-center gap-1.5 text-[12px] font-semibold tracking-[0.05em] uppercase">
                <span class="icone text-[18px] text-destaque" aria-hidden="true">{{ r.icone }}</span>{{ r.rotulo }}
              </span>
              <strong class="text-[18px] leading-tight" :class="r.cor">{{ r.valor }}</strong>
              <span v-if="r.extra" class="texto-2 text-[14px] leading-snug">{{ r.extra }}</span>
              <button
                v-if="r.maisAutores" type="button" class="cursor-pointer self-start border-none bg-transparent p-0 text-[14px] font-medium text-link underline [font:inherit]"
                @click="verAutores"
              >e mais {{ r.maisAutores }} {{ r.maisAutores === 1 ? 'autor' : 'autores' }}</button>
            </div>
          </section>

          <!-- Cada parte da noticia (planta 25.14) num bloco proprio -->
          <template v-for="(s, i) in secoes" :key="i">
            <SecaoVotacao v-if="s.titulo === 'Resultado da votação' && votacaoNoTexto" :votacao="votacao" />
            <section
              v-else class="cartao flex flex-col gap-3 leading-[1.6]"
              :class="{ 'border-l-4 border-destaque-forte': s.lacunas }"
            >
              <h2 v-if="s.titulo" class="m-0 flex items-center gap-2 text-[19px]">
                <span class="icone text-[22px]" :class="s.lacunas ? 'text-destaque-forte' : 'text-link'" aria-hidden="true">{{ iconeDaSecao(s.titulo) }}</span>{{ s.titulo }}
              </h2>
              <template v-for="(b, j) in s.blocos" :key="j">
                <h3 v-if="b.tipo === 'sub'" class="m-0 mt-1 border-t border-linha pt-3 text-[15px] text-texto-2">{{ b.texto }}</h3>
                <ul v-else-if="b.tipo === 'lista'" class="m-0 flex flex-col gap-1.5 pl-5 [overflow-wrap:anywhere]"><li v-for="(it, k) in b.itens" :key="k"><template v-for="(x, m) in partes(it)" :key="m"><a v-if="x.link" :href="x.t" target="_blank" rel="noopener">{{ x.t }}</a><template v-else>{{ x.t }}</template></template></li></ul>
                <dl v-else-if="b.tipo === 'ficha'" class="m-0 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[170px_minmax(0,1fr)] sm:gap-y-3">
                  <template v-for="(f, k) in b.itens" :key="k">
                    <dt class="texto-2 mt-2 text-[12px] font-semibold tracking-[0.05em] uppercase sm:mt-0 sm:pt-1">{{ f.rotulo }}</dt>
                    <dd v-if="f.rotulo === 'Autoria' && proposicao?.autores?.length > 1" id="autoria" class="m-0">
                      <ListaAutores v-model:aberta="autoresAbertos" :autores="proposicao.autores" />
                    </dd>
                    <dd v-else class="m-0" :class="{ 'border-l-[3px] border-marca pl-3 text-texto-2 italic': f.rotulo === 'Ementa oficial' }">{{ f.valor }}</dd>
                  </template>
                </dl>
                <ol v-else-if="b.tipo === 'passos'" class="m-0 flex list-none flex-col gap-2.5 p-0" aria-label="Últimos passos">
                  <li v-for="(passo, k) in b.itens" :key="k" class="flex items-start gap-3">
                    <span class="flex-none rounded-full bg-faixa px-2.5 py-0.5 text-[13px] font-medium whitespace-nowrap">{{ passo.data }}</span>
                    <span class="text-[15px]">{{ passo.texto }} <span class="texto-2">· {{ passo.orgao }}</span></span>
                  </li>
                </ol>
                <p v-else class="m-0 whitespace-pre-line [overflow-wrap:anywhere]"><template v-for="(x, k) in partes(b.texto)" :key="k"><a v-if="x.link" :href="x.t" target="_blank" rel="noopener">{{ x.t }}</a><template v-else>{{ x.t }}</template></template></p>
              </template>
            </section>
          </template>

          <SecaoVotacao v-if="votacao && !votacaoNoTexto" :votacao="votacao" />
          <SecaoAndamento v-if="proposicao" :proposicao="proposicao" />
          <ComoFoiFeita :noticia="noticia" />
          <section v-if="noticia.relacionadas?.length" class="cartao flex flex-col gap-4" aria-labelledby="titulo-relacionadas">
            <h2 id="titulo-relacionadas" class="m-0 flex items-center gap-2 text-[19px]"><span class="icone text-[22px] text-link" aria-hidden="true">link</span>Notícias relacionadas</h2>
            <CartaoNoticia v-for="r in noticia.relacionadas" :key="r.slug" :noticia="r" com-tema :com-resumo="false" />
          </section>
        </article>

        <aside v-if="proposicao" class="flex min-w-0 flex-col gap-4 lg:sticky lg:top-4" aria-label="O projeto">
          <QuadroProposicao :proposicao="proposicao" />
          <div v-if="proposicao.noticias?.length > 1" class="cartao flex flex-col gap-2.5 text-[15px]">
            <h2 class="m-0 text-[16px]">Outras notícias deste projeto</h2>
            <template v-for="n in proposicao.noticias" :key="n.slug">
              <RouterLink v-if="n.slug !== noticia.slug" :to="{ name: 'noticia', params: { slug: n.slug } }">{{ n.titulo }}</RouterLink>
            </template>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>
