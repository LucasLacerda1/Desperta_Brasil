<script setup>
// RF09: resultado da votacao, voto de cada deputado e orientacoes em tres grupos (decisao 10.1).
// A explicacao da situacao dos votos (nominal, simbolica, secreta...) vem pronta da API (22.5).
import { computed, ref } from 'vue'
import { data } from '../util/datas.js'
import BarraVotos from './BarraVotos.vue'

const props = defineProps({ votacao: { type: Object, required: true } })

const DEPUTADOS = 513
const NAO_INFORMADO = 'não informado pela Câmara'

const codigo = computed(() => props.votacao.situacao_dos_votos?.codigo)
const noPlenario = computed(() => props.votacao.orgao?.sigla === 'PLEN')

// Placar: dos votos registrados; na votacao secreta, o que a Camara divulgou.
const placar = computed(() => {
  const origem = codigo.value === 'secreta'
    ? props.votacao.situacao_dos_votos.placar_da_camara || {}
    : props.votacao.total_por_tipo || {}
  const sim = origem['Sim'] || 0
  const nao = origem['Não'] || 0
  const outros = Object.entries(origem)
    .filter(([tipo]) => !['Sim', 'Não', 'Total', NAO_INFORMADO].includes(tipo))
    .map(([tipo, total]) => ({ tipo, total }))
  const totalOutros = outros.reduce((soma, o) => soma + o.total, 0)
  return { sim, nao, outros, totalOutros, votaram: sim + nao + totalOutros }
})
const temPlacar = computed(() => placar.value.sim + placar.value.nao > 0)
const base = computed(() => (noPlenario.value ? DEPUTADOS : placar.value.votaram))
const semVoto = computed(() => (noPlenario.value ? DEPUTADOS - placar.value.votaram : 0))

/*
  PROTOTIPO: minimo de votos para aprovar no Plenario.
  Lei complementar (PLP) pede maioria absoluta (257 dos 513); emenda a Constituicao (PEC), tres quintos (308).
  So vale para a votacao do texto; requerimentos sobre o mesmo projeto seguem outra regra.
  Na Fase 5 esta regra deve sair do front e vir do service de votacoes.
*/
const minimo = computed(() => {
  if (!noPlenario.value) return null
  if (/requerimento/i.test(props.votacao.descricao || '')) return null
  const sigla = props.votacao.proposicoes_afetadas?.[0]?.sigla || ''
  if (sigla.startsWith('PLP ')) return { votos: 257, motivo: 'Lei complementar precisa do voto de mais da metade dos 513 deputados.' }
  if (sigla.startsWith('PEC ')) return { votos: 308, motivo: 'Emenda à Constituição precisa do voto de três quintos dos 513 deputados.' }
  return null
})

const resultado = computed(() => {
  const r = props.votacao.resultado
  if (r === 'aprovada') return { texto: 'Aprovado', classe: 'aprovado', icone: 'check' }
  if (r === 'rejeitada') return { texto: 'Rejeitado', classe: 'rejeitado', icone: 'close' }
  return { texto: 'Resultado não informado pela Câmara', classe: 'neutro', icone: 'help' }
})

// Votos por partido, do maior para o menor
const partidos = computed(() => {
  const mapa = new Map()
  for (const v of props.votacao.votos || []) {
    const p = mapa.get(v.sigla_partido) || { sigla: v.sigla_partido, sim: 0, nao: 0, outros: 0, total: 0 }
    if (v.voto === 'Sim') p.sim += 1
    else if (v.voto === 'Não') p.nao += 1
    else p.outros += 1
    p.total += 1
    mapa.set(v.sigla_partido, p)
  }
  return [...mapa.values()].sort((a, b) => b.total - a.total)
})
const maiorPartido = computed(() => Math.max(1, ...partidos.value.map((p) => p.total)))
const todosPartidos = ref(false)
const partidosVisiveis = computed(() => (todosPartidos.value ? partidos.value : partidos.value.slice(0, 10)))
const largura = (n) => `${((100 * n) / maiorPartido.value).toFixed(1)}%`

// Orientacoes: tres grupos; quem nao orientou fica numa linha so
const grupos = computed(() => {
  const o = props.votacao.orientacoes || {}
  return [
    { nome: 'Partidos', itens: o.partidos || [] },
    { nome: 'Governo, Maioria, Minoria e Oposição', itens: o.liderancas || [] },
    { nome: 'Blocos e federações', itens: o.blocos || [], nota: 'O nome do bloco aparece como a Câmara informa, às vezes cortado.' },
  ]
    .filter((g) => g.itens.length)
    .map((g) => ({
      ...g,
      orientaram: g.itens.filter((i) => i.orientacao !== NAO_INFORMADO),
      calados: g.itens.filter((i) => i.orientacao === NAO_INFORMADO).map((i) => i.nome),
    }))
})
const classeDoVoto = (voto) => (voto === 'Sim' ? 'sim' : voto === 'Não' ? 'nao' : 'neutro')
const iconeDoVoto = (voto) => (voto === 'Sim' ? 'check' : voto === 'Não' ? 'close' : 'remove')

// Lista de votos, com filtro
const abrirVotos = ref(false)
const filtro = ref('')
const limite = ref(30)
const votosFiltrados = computed(() => {
  const termo = filtro.value.trim().toLowerCase()
  const lista = props.votacao.votos || []
  if (!termo) return lista
  return lista.filter((v) => `${v.nome} ${v.sigla_partido} ${v.sigla_uf} ${v.voto}`.toLowerCase().includes(termo))
})
</script>

<template>
  <section class="cartao votacao" aria-labelledby="t-votacao">
    <div class="cabeca">
      <h2 id="t-votacao">Como votaram</h2>
      <span class="selo" :class="resultado.classe">
        <span class="icone" aria-hidden="true">{{ resultado.icone }}</span>{{ resultado.texto }}
      </span>
    </div>
    <p class="descricao">
      <strong>{{ data(votacao.data) }} · {{ noPlenario ? 'Plenário' : votacao.orgao?.sigla }}.</strong>
      {{ votacao.descricao }}
    </p>
    <p class="explicacao texto-2">{{ votacao.situacao_dos_votos?.explicacao }}</p>

    <template v-if="temPlacar">
      <BarraVotos
        :sim="placar.sim" :nao="placar.nao" :outros="placar.totalOutros" :base="base"
        :minimo="minimo?.votos ?? null" :rotulo-base="noPlenario ? '513 deputados' : `${placar.votaram} votos`"
      />
      <p v-if="minimo" class="motivo">{{ minimo.motivo }}</p>

      <ul class="legenda">
        <li><span class="quadrado q-sim"></span><span><strong>{{ placar.sim }}</strong>Sim</span></li>
        <li><span class="quadrado q-nao"></span><span><strong>{{ placar.nao }}</strong>Não</span></li>
        <li v-for="o in placar.outros" :key="o.tipo">
          <span class="quadrado q-outros"></span>
          <span>
            <strong>{{ o.total }}</strong>{{ o.tipo === 'Artigo 17' ? 'Artigo 17: quem presidia a sessão, que pelo regimento não vota' : o.tipo }}
          </span>
        </li>
        <li v-if="semVoto > 0"><span class="quadrado q-vazio"></span><span><strong>{{ semVoto }}</strong>não registraram voto</span></li>
      </ul>
    </template>

    <template v-if="partidos.length">
      <h3>Por partido</h3>
      <div class="partidos">
        <div v-for="p in partidosVisiveis" :key="p.sigla" class="partido">
          <span class="sigla">{{ p.sigla }}</span>
          <div class="barrinha" aria-hidden="true">
            <div class="b-sim" :style="{ width: largura(p.sim) }"></div>
            <div class="b-nao" :style="{ width: largura(p.nao) }"></div>
            <div class="b-outros" :style="{ width: largura(p.outros) }"></div>
          </div>
          <span class="texto-2 conta">{{ p.sim }} sim · {{ p.nao }} não</span>
        </div>
      </div>
      <button v-if="partidos.length > 10" type="button" class="link-botao" @click="todosPartidos = !todosPartidos">
        {{ todosPartidos ? 'Mostrar só os 10 maiores' : `Mostrar os ${partidos.length} partidos` }}
      </button>
    </template>

    <template v-if="grupos.length">
      <h3>O que cada liderança orientou</h3>
      <div class="grupos">
        <div v-for="g in grupos" :key="g.nome" class="grupo">
          <strong>{{ g.nome }}</strong>
          <span v-for="i in g.orientaram" :key="i.nome">
            {{ i.nome }} ·
            <strong :class="classeDoVoto(i.orientacao)">
              <span class="icone pequeno" aria-hidden="true">{{ iconeDoVoto(i.orientacao) }}</span>{{ i.orientacao }}
            </strong>
          </span>
          <span v-if="g.calados.length" class="texto-2">Não orientaram: {{ g.calados.join(', ') }}</span>
          <span v-if="g.nota" class="texto-2 nota">{{ g.nota }}</span>
        </div>
      </div>
    </template>

    <template v-if="votacao.votos?.length">
      <button type="button" class="botao botao-contorno abrir" :aria-expanded="abrirVotos" @click="abrirVotos = !abrirVotos">
        <span class="icone" aria-hidden="true">{{ abrirVotos ? 'expand_less' : 'expand_more' }}</span>
        {{ abrirVotos ? 'Esconder o voto de cada deputado' : `Ver o voto de cada deputado (${votacao.votos.length})` }}
      </button>
      <div v-if="abrirVotos" class="lista-votos">
        <label for="filtro-votos">Procure por nome, partido, estado ou voto</label>
        <input id="filtro-votos" v-model="filtro" type="search" placeholder="Ex.: Silva, PT, SP, Não">
        <ul>
          <li v-for="v in votosFiltrados.slice(0, limite)" :key="v.deputado_id">
            <span>{{ v.nome }} <span class="texto-2">({{ v.sigla_partido }}-{{ v.sigla_uf }})</span></span>
            <strong :class="classeDoVoto(v.voto)">{{ v.voto }}</strong>
          </li>
        </ul>
        <p class="texto-2 contagem">
          Mostrando {{ Math.min(limite, votosFiltrados.length) }} de {{ votosFiltrados.length }}.
          <button v-if="votosFiltrados.length > limite" type="button" class="link-botao" @click="limite += 100">Mostrar mais</button>
        </p>
      </div>
    </template>

    <a :href="votacao.url_dados_abertos" class="fonte" target="_blank" rel="noopener">
      Ver esta votação nos Dados Abertos da Câmara<span class="icone pequeno" aria-hidden="true">open_in_new</span>
    </a>
  </section>
</template>

<style scoped>
.votacao { padding: 28px; display: flex; flex-direction: column; gap: 16px; }
.cabeca { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
h2 { margin: 0; font-size: 22px; }
h3 { margin: 8px 0 0; font-size: 17px; }
.selo {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
}
.selo .icone { font-size: 16px; }
.selo.aprovado { background: var(--sim); color: var(--superficie); }
.selo.rejeitado { background: var(--erro); color: var(--superficie); }
.selo.neutro { background: var(--barra-fundo); color: var(--texto); }
.descricao, .explicacao, .motivo { margin: 0; font-size: 15px; }
.motivo { font-size: 14px; }

.legenda { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; font-size: 14px; }
.legenda li { display: flex; gap: 8px; align-items: flex-start; }
.legenda strong { display: block; font-size: 20px; }
.quadrado { flex: none; width: 14px; height: 14px; margin-top: 4px; border-radius: 3px; }
.q-sim { background: var(--sim); }
.q-nao { background: var(--nao); }
.q-outros { background: var(--outro-voto); }
.q-vazio { background: var(--barra-fundo); border: 1px solid var(--borda); }

.partidos { display: flex; flex-direction: column; gap: 8px; }
.partido { display: grid; grid-template-columns: 120px minmax(0, 1fr) 100px; align-items: center; gap: 12px; font-size: 14px; }
.sigla { font-weight: 500; overflow-wrap: anywhere; }
.barrinha { display: flex; height: 14px; border-radius: 3px; overflow: hidden; }
.b-sim { background: var(--sim); }
.b-nao { background: var(--nao); }
.b-outros { background: var(--outro-voto); }
.conta { text-align: right; }

.grupos { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
.grupo { background: var(--superficie-2); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 8px; font-size: 14px; }
.grupo > strong { font-size: 15px; }
.nota { font-size: 13px; }
.sim { color: var(--sim-texto); }
.nao { color: var(--nao-texto); }
.neutro { color: var(--texto-2); }
.pequeno { font-size: 16px; }

.abrir { align-self: flex-start; }
.lista-votos { display: flex; flex-direction: column; gap: 10px; }
.lista-votos label { font-size: 14px; font-weight: 500; }
.lista-votos input {
  min-height: 44px;
  max-width: 360px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid var(--borda);
  background: var(--superficie-2);
  color: var(--texto);
  font: inherit;
}
.lista-votos ul { list-style: none; margin: 0; padding: 0; font-size: 15px; }
.lista-votos li { display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--linha); }
.contagem { margin: 0; font-size: 13px; }
.link-botao { background: none; border: none; padding: 0; font: inherit; font-weight: 500; color: var(--link); cursor: pointer; text-decoration: underline; align-self: flex-start; }
.fonte { font-size: 14px; font-weight: 500; }

@media (max-width: 600px) {
  .votacao { padding: 20px; }
  .partido { grid-template-columns: 84px minmax(0, 1fr); }
  .conta { grid-column: 2; text-align: left; }
}
</style>
