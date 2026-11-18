<script setup>
// RF16: fila de revisao da equipe. Lista a esquerda, edicao a direita, acoes uma a uma ou em lote.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { equipe, errosDosCampos, mensagemDeErro, portal } from '../../services/api.js'
import { dataHora } from '../../util/datas.js'
import { STATUS_DA_FILA } from '../../util/equipe.js'
import LayoutEquipe from '../../componentes/LayoutEquipe.vue'
import Paginacao from '../../componentes/Paginacao.vue'

const rota = useRoute()
const roteador = useRouter()
const temas = ref([])
const pronto = ref(false)
const CASOS = [
  { valor: '', nome: 'Todos' },
  { valor: 'votacao', nome: 'Votações' },
  { valor: 'situacao', nome: 'Mudanças de situação' },
  { valor: 'nova', nome: 'Proposições novas' },
  { valor: 'boletim', nome: 'Boletins' },
]
const filtros = reactive({ status: rota.query.status || 'rascunho', caso: '', tema: '', pagina: 1 })
const lista = ref({ itens: [], total: 0, paginas: 1, pagina: 1 })
const carregando = ref(true)
const erro = ref('')
const aviso = ref('')

const marcados = ref([])
const aberta = ref(null) // detalhe da noticia em edicao
const form = reactive({ titulo: '', resumo: '', corpo: '' })
const comentario = ref('')
const erroDaAcao = ref('')
const errosCampos = ref({})
const ocupado = ref(false)

const statusAtual = computed(() => STATUS_DA_FILA.find((s) => s.valor === filtros.status) || STATUS_DA_FILA[0])
const mudou = computed(() => aberta.value && (form.titulo !== aberta.value.titulo || form.resumo !== aberta.value.resumo || form.corpo !== aberta.value.corpo))
const geracao = computed(() => aberta.value?.geracoes?.at(-1) || null)
const NOMES_CASO = { votacao: 'Votação', situacao: 'Mudança de situação', nova: 'Proposição nova' }
const podeAgir = computed(() => ['rascunho', 'em_revisao'].includes(aberta.value?.status))

onMounted(() => {
  document.title = 'Fila de revisão — Desperta Brasil'
})

// O molde da equipe avisa quando o login foi conferido
function iniciar() {
  pronto.value = true
  portal.temas().then((r) => { temas.value = r.itens }).catch(() => {})
  carregar()
}

// A barra lateral muda o status pelo endereco (?status=)
watch(() => rota.query.status, (novo) => {
  filtros.status = novo || 'rascunho'
})

async function carregar(manterAberta = false) {
  carregando.value = true
  erro.value = ''
  try {
    const params = { status: filtros.status, pagina: filtros.pagina, por_pagina: 12 }
    if (filtros.caso) params.caso = filtros.caso
    if (filtros.tema) params.tema = filtros.tema
    lista.value = await equipe.fila(params)
    marcados.value = []
    if (!manterAberta) {
      if (lista.value.itens.length) abrir(lista.value.itens[0].id)
      else aberta.value = null
    }
  } catch (e) {
    if (e?.response?.status === 401) roteador.replace({ name: 'entrar' })
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}

watch(() => [filtros.status, filtros.caso, filtros.tema], () => {
  if (!pronto.value) return
  filtros.pagina = 1
  carregar()
})

async function abrir(id) {
  erroDaAcao.value = ''
  errosCampos.value = {}
  comentario.value = ''
  try {
    const d = await equipe.detalhe(id)
    aberta.value = d
    Object.assign(form, { titulo: d.titulo, resumo: d.resumo, corpo: d.corpo })
  } catch (e) {
    erroDaAcao.value = mensagemDeErro(e)
  }
}

async function salvar() {
  ocupado.value = true
  erroDaAcao.value = ''
  errosCampos.value = {}
  try {
    const d = await equipe.editar(aberta.value.id, { titulo: form.titulo, resumo: form.resumo, corpo: form.corpo })
    aberta.value = d
    Object.assign(form, { titulo: d.titulo, resumo: d.resumo, corpo: d.corpo })
    aviso.value = 'Texto salvo.'
    await carregar(true)
  } catch (e) {
    erroDaAcao.value = mensagemDeErro(e)
    errosCampos.value = errosDosCampos(e)
  } finally {
    ocupado.value = false
  }
}

async function agir(acao) {
  ocupado.value = true
  erroDaAcao.value = ''
  errosCampos.value = {}
  try {
    if (mudou.value) await equipe.editar(aberta.value.id, { titulo: form.titulo, resumo: form.resumo, corpo: form.corpo })
    await equipe.acao(aberta.value.id, acao, comentario.value || undefined)
    aviso.value = { aprovar: 'Aprovada.', publicar: 'Publicada.', rejeitar: 'Rejeitada.', arquivar: 'Arquivada.' }[acao]
    await carregar()
  } catch (e) {
    erroDaAcao.value = mensagemDeErro(e)
    errosCampos.value = errosDosCampos(e)
  } finally {
    ocupado.value = false
  }
}

async function agirEmLote(acao) {
  ocupado.value = true
  erro.value = ''
  try {
    const r = await equipe.lote(marcados.value, acao, comentario.value || undefined)
    aviso.value = `${r.feitas.length} feitas` + (r.falhas.length ? `, ${r.falhas.length} com problema: ${r.falhas[0].erro}` : '.')
    await carregar()
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    ocupado.value = false
  }
}

function marcarTodos(evento) {
  marcados.value = evento.target.checked ? lista.value.itens.map((n) => n.id) : []
}

function mudarPagina(p) {
  filtros.pagina = p
  carregar()
}
</script>

<template>
  <LayoutEquipe :conta="lista.total" @pronto="iniciar">
      <header>
        <h1 class="m-0 text-[28px]">{{ statusAtual.nome }}</h1>
        <p class="texto-2 mt-1.5 mb-0 text-[15px]">
          {{ lista.total.toLocaleString('pt-BR') }} {{ lista.total === 1 ? 'notícia' : 'notícias' }} · mais antigas primeiro
        </p>
      </header>

      <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div role="group" aria-label="Filtrar por caso" class="flex flex-wrap gap-2">
          <button
            v-for="c in CASOS" :key="c.valor" type="button" class="chip" :class="{ ativo: filtros.caso === c.valor }"
            :aria-pressed="filtros.caso === c.valor" @click="filtros.caso = c.valor"
          >{{ c.nome }}</button>
        </div>
        <label class="so-leitor" for="f-tema">Tema</label>
        <select id="f-tema" v-model="filtros.tema" class="filtro max-w-[280px]">
          <option value="">Todos os temas</option>
          <option v-for="t in temas" :key="t.cod_tema" :value="String(t.cod_tema)">{{ t.nome }}</option>
        </select>
      </div>

      <p v-if="aviso" class="aviso-ok text-[15px]" role="status">
        <span class="icone" aria-hidden="true">check_circle</span>{{ aviso }}
        <button type="button" class="ml-auto size-8 cursor-pointer border-none bg-transparent text-texto-2" aria-label="Fechar aviso" @click="aviso = ''"><span class="icone" aria-hidden="true">close</span></button>
      </p>
      <p v-if="erro" class="texto-erro" role="alert">{{ erro }}</p>

      <div v-if="marcados.length" class="flex flex-wrap items-center gap-3 rounded-xl bg-faixa px-4 py-2.5 text-[14px]">
        <strong>{{ marcados.length }} {{ marcados.length === 1 ? 'selecionada' : 'selecionadas' }}</strong>
        <template v-if="['rascunho', 'em_revisao'].includes(filtros.status)">
          <button v-if="filtros.status === 'rascunho'" type="button" class="botao botao-contorno botao-baixo" :disabled="ocupado" @click="agirEmLote('aprovar')">Aprovar</button>
          <button type="button" class="botao botao-principal botao-baixo" :disabled="ocupado" @click="agirEmLote('publicar')">Publicar</button>
          <button type="button" class="botao botao-perigo botao-baixo" :disabled="ocupado || !comentario.trim()" @click="agirEmLote('rejeitar')">Rejeitar</button>
          <span class="texto-2">Para rejeitar, escreva o comentário no painel ao lado. Até 200 por vez.</span>
        </template>
        <button v-else-if="filtros.status === 'publicada'" type="button" class="botao botao-contorno botao-baixo" :disabled="ocupado" @click="agirEmLote('arquivar')">Arquivar</button>
      </div>

      <!-- Tela larga: lista e editor lado a lado; menor: um embaixo do outro -->
        <div class="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section class="cartao min-w-0 overflow-hidden p-0" aria-label="Notícias">
          <p v-if="carregando" class="vazio texto-2">Carregando…</p>
          <p v-else-if="!lista.itens.length" class="vazio texto-2">Nada aqui com esses filtros.</p>
          <template v-else>
            <label class="linha-todos">
              <input type="checkbox" :checked="marcados.length === lista.itens.length" @change="marcarTodos">
              Selecionar as {{ lista.itens.length }} desta página
            </label>
            <div v-for="n in lista.itens" :key="n.id" class="linha" :class="{ aberta: aberta?.id === n.id }">
              <input v-model="marcados" type="checkbox" :value="n.id" :aria-label="`Selecionar ${n.titulo}`">
              <button type="button" class="abrir" @click="abrir(n.id)">
                <span class="titulo">{{ n.titulo }}</span>
                <span v-if="n.prioridade?.motivos?.length" class="motivo texto-2">{{ n.prioridade.motivos[0] }}</span>
                <span class="meta texto-2">
                  <span v-if="n.prioridade" class="prio" :class="n.prioridade.nivel" :title="n.prioridade.motivos.join('; ')">Prioridade {{ { alta: 'alta', media: 'média', baixa: 'baixa' }[n.prioridade.nivel] }}</span>
                  <span v-if="n.conferencia && !n.conferencia.passou" class="falha" :title="n.conferencia.falhas.join('; ')">Não passou na planta</span>
                  <span v-if="n.origem === 'equipe'" class="origem">Escrita pela equipe</span>
                  <span>{{ n.tema?.nome }}</span>
                  <span>{{ dataHora(n.criado_em) }}</span>
                </span>
              </button>
            </div>
          </template>
          <div class="pe-lista"><Paginacao :pagina="lista.pagina || 1" :paginas="lista.paginas || 1" @ir="mudarPagina" /></div>
        </section>

        <section v-if="aberta" class="editor-campos cartao flex min-w-0 flex-col gap-2.5" aria-labelledby="t-editor">
          <h2 id="t-editor" class="so-leitor">Editar notícia</h2>
          <div class="etiquetas">
            <span class="status">{{ aberta.status.replace('_', ' ') }}</span>
            <span v-if="geracao?.entrada?.caso" class="caso">{{ NOMES_CASO[geracao.entrada.caso] || geracao.entrada.caso }}</span>
            <span class="texto-2">{{ aberta.tema?.nome }} · criada em {{ dataHora(aberta.criado_em) }}</span>
          </div>

          <label for="ed-titulo">Título <span class="texto-2">({{ form.titulo.length }} de 200)</span></label>
          <input id="ed-titulo" v-model="form.titulo" type="text" maxlength="200" class="serifa" :aria-invalid="!!errosCampos.titulo" aria-describedby="erro-ed-titulo">
          <span v-if="errosCampos.titulo" id="erro-ed-titulo" class="erro-campo text-[13px]">{{ errosCampos.titulo }}</span>
          <label for="ed-resumo">Resumo <span class="texto-2">({{ form.resumo.length }} de 500)</span></label>
          <textarea id="ed-resumo" v-model="form.resumo" rows="3" maxlength="500" :aria-invalid="!!errosCampos.resumo" aria-describedby="erro-ed-resumo"></textarea>
          <span v-if="errosCampos.resumo" id="erro-ed-resumo" class="erro-campo text-[13px]">{{ errosCampos.resumo }}</span>
          <details>
            <summary>Corpo da notícia</summary>
            <label for="ed-corpo" class="so-leitor">Corpo</label>
            <textarea id="ed-corpo" v-model="form.corpo" rows="12" :aria-invalid="!!errosCampos.corpo"></textarea>
          </details>
          <span v-if="errosCampos.corpo" class="erro-campo text-[13px]">Corpo: {{ errosCampos.corpo }}</span>
          <RouterLink :to="{ name: 'editar', params: { id: aberta.id } }" class="inline-flex items-center gap-1.5 self-start text-[14px] font-medium [&_.icone]:text-[18px]">
            <span class="icone" aria-hidden="true">open_in_full</span>Editar em tela cheia (título, resumo, tema e corpo)
          </RouterLink>

          <div class="usou">
            <strong><span class="icone" aria-hidden="true">fact_check</span>O que o sistema usou</strong>
            <span>
              Fontes:
              <template v-for="(f, i) in aberta.fontes" :key="f.tipo + f.ref_id">
                <template v-if="i">, </template>
                <a v-if="f.url_pagina || f.url_dados_abertos" :href="f.url_pagina || f.url_dados_abertos" target="_blank" rel="noopener">{{ f.tipo }} {{ f.ref_id }}</a>
                <span v-else>{{ f.tipo }} {{ f.ref_id }}</span>
              </template>
              <template v-if="!aberta.fontes.length">nenhuma</template>
            </span>
            <span v-if="geracao">Gerador: {{ geracao.modelo_geracao }} · busca: {{ geracao.modelo_embedding }}</span>
            <details v-if="geracao?.trechos?.length">
              <summary>Ver os {{ geracao.trechos.length }} trechos que a busca encontrou</summary>
              <ol class="trechos">
                <li v-for="t in geracao.trechos" :key="t.posicao">
                  <span class="texto-2">{{ t.tipo }} {{ t.ref_id }}</span>
                  {{ t.texto }}
                </li>
              </ol>
            </details>
          </div>

          <details v-if="aberta.revisoes?.length" class="historico">
            <summary>Histórico ({{ aberta.revisoes.length }})</summary>
            <ul>
              <li v-for="(r, i) in aberta.revisoes" :key="i">
                <strong>{{ r.acao }}</strong> por {{ r.administrador || 'equipe' }}, {{ dataHora(r.data_hora) }}
                <template v-if="r.comentario">: {{ r.comentario }}</template>
              </li>
            </ul>
          </details>

          <template v-if="podeAgir">
            <label for="ed-comentario">Comentário <span class="texto-2">(obrigatório para rejeitar)</span></label>
            <textarea id="ed-comentario" v-model="comentario" rows="2" placeholder="Ex.: o título não diz o que o projeto faz"></textarea>
          </template>
          <p v-if="erroDaAcao" class="texto-erro" role="alert">{{ erroDaAcao }}</p>

          <div class="mt-2 flex flex-wrap gap-2.5">
            <button v-if="podeAgir" type="button" class="botao botao-principal" :disabled="ocupado" @click="agir('publicar')">Publicar</button>
            <button v-if="aberta.status === 'rascunho'" type="button" class="botao botao-contorno" :disabled="ocupado" @click="agir('aprovar')">Aprovar</button>
            <button type="button" class="botao botao-contorno" :disabled="ocupado || !mudou" @click="salvar">Salvar texto</button>
            <button v-if="podeAgir" type="button" class="botao botao-perigo" :disabled="ocupado || !comentario.trim()" @click="agir('rejeitar')">Rejeitar</button>
            <button v-if="aberta.status === 'publicada'" type="button" class="botao botao-perigo" :disabled="ocupado" @click="agir('arquivar')">Arquivar</button>
          </div>
        </section>
      </div>
  </LayoutEquipe>
</template>

<style scoped>
/* So os detalhes internos da lista e do editor; a estrutura da tela usa as classes do Tailwind */
.vazio { margin: 0; padding: 24px; }
.linha-todos { display: flex; align-items: center; gap: 12px; padding: 12px 16px; font-size: 14px; border-bottom: 1px solid var(--linha); cursor: pointer; }
.linha { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--linha); border-left: 4px solid transparent; align-items: start; }
.linha.aberta { background: var(--faixa); border-left-color: var(--principal); }
input[type='checkbox'] { width: 18px; height: 18px; margin: 3px 0 0; accent-color: var(--principal); }
.abrir { background: none; border: none; padding: 0; font: inherit; color: var(--texto); text-align: left; cursor: pointer; display: flex; flex-direction: column; gap: 6px; }
.abrir:hover .titulo { text-decoration: underline; }
.titulo { font-weight: 500; line-height: 1.35; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; }
.prio { padding: 0 8px; border-radius: 999px; font-weight: 600; }
.prio.alta { background: var(--principal); color: var(--sobre-principal); }
.prio.media { background: var(--faixa); color: var(--texto); }
.prio.baixa { border: 1px solid var(--linha); }
.falha { color: var(--erro); font-weight: 600; }
.motivo { font-size: 13px; }
.origem { color: var(--destaque); font-weight: 500; }
.pe-lista { padding: 12px 16px; }

.etiquetas { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13px; }
.status { padding: 3px 10px; border-radius: 10px; background: var(--superficie-2); }
.caso { color: var(--link); font-weight: 500; }
.editor-campos label { font-size: 13px; font-weight: 500; margin-top: 6px; }
input[type='text'], textarea { border-radius: 8px; border: 1px solid var(--borda); background: var(--superficie-2); color: var(--texto); font: inherit; }
input[type='text'] { min-height: 44px; padding: 0 12px; font-size: 19px; font-weight: 600; }
textarea { padding: 10px 12px; font-size: 15px; line-height: 1.5; resize: vertical; width: 100%; }
input[aria-invalid='true'], textarea[aria-invalid='true'] { border: 2px solid var(--erro); }
details summary { cursor: pointer; font-weight: 500; color: var(--link); padding: 6px 0; }
.usou { background: var(--superficie-2); border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
.usou > strong { display: flex; align-items: center; gap: 6px; }
.usou > strong .icone { font-size: 18px; color: var(--link); }
.trechos { margin: 8px 0 0; padding-left: 20px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; max-height: 280px; overflow-y: auto; }
.trechos .texto-2 { display: block; }
.historico ul { margin: 6px 0 0; padding-left: 20px; font-size: 14px; }
</style>
