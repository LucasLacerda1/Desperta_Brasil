<script setup>
// RF16: fila de revisao da equipe. Lista a esquerda, edicao a direita, acoes uma a uma ou em lote.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { equipe, mensagemDeErro, portal } from '../../services/api.js'
import { dataHora } from '../../util/datas.js'
import { alternarTema, temaAtual } from '../../util/tema.js'
import Paginacao from '../../componentes/Paginacao.vue'

const roteador = useRouter()
const eu = ref(null)
const temas = ref([])
const tema = ref(temaAtual())

const STATUS = [
  { valor: 'rascunho', nome: 'Fila de revisão', icone: 'inbox' },
  { valor: 'em_revisao', nome: 'Aprovadas, a publicar', icone: 'task_alt' },
  { valor: 'publicada', nome: 'Publicadas', icone: 'public' },
  { valor: 'rejeitada', nome: 'Rejeitadas', icone: 'block' },
  { valor: 'arquivada', nome: 'Arquivadas', icone: 'inventory_2' },
]
const CASOS = [
  { valor: '', nome: 'Todos' },
  { valor: 'votacao', nome: 'Votações' },
  { valor: 'situacao', nome: 'Mudanças de situação' },
  { valor: 'nova', nome: 'Proposições novas' },
]
const filtros = reactive({ status: 'rascunho', caso: '', tema: '', pagina: 1 })
const lista = ref({ itens: [], total: 0, paginas: 1, pagina: 1 })
const carregando = ref(true)
const erro = ref('')
const aviso = ref('')

const marcados = ref([])
const aberta = ref(null) // detalhe da noticia em edicao
const form = reactive({ titulo: '', resumo: '', corpo: '' })
const comentario = ref('')
const erroDaAcao = ref('')
const ocupado = ref(false)

const statusAtual = computed(() => STATUS.find((s) => s.valor === filtros.status))
const mudou = computed(() => aberta.value && (form.titulo !== aberta.value.titulo || form.resumo !== aberta.value.resumo || form.corpo !== aberta.value.corpo))
const geracao = computed(() => aberta.value?.geracoes?.at(-1) || null)
const NOMES_CASO = { votacao: 'Votação', situacao: 'Mudança de situação', nova: 'Proposição nova' }
const podeAgir = computed(() => ['rascunho', 'em_revisao'].includes(aberta.value?.status))

onMounted(async () => {
  document.title = 'Fila de revisão — Desperta Brasil'
  try {
    eu.value = (await equipe.eu()).administrador
  } catch {
    roteador.replace({ name: 'entrar' })
    return
  }
  portal.temas().then((r) => { temas.value = r.itens }).catch(() => {})
  carregar()
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
  filtros.pagina = 1
  carregar()
})

async function abrir(id) {
  erroDaAcao.value = ''
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
  try {
    const d = await equipe.editar(aberta.value.id, { titulo: form.titulo, resumo: form.resumo, corpo: form.corpo })
    aberta.value = d
    Object.assign(form, { titulo: d.titulo, resumo: d.resumo, corpo: d.corpo })
    aviso.value = 'Texto salvo.'
    await carregar(true)
  } catch (e) {
    erroDaAcao.value = mensagemDeErro(e)
  } finally {
    ocupado.value = false
  }
}

async function agir(acao) {
  ocupado.value = true
  erroDaAcao.value = ''
  try {
    if (mudou.value) await equipe.editar(aberta.value.id, { titulo: form.titulo, resumo: form.resumo, corpo: form.corpo })
    await equipe.acao(aberta.value.id, acao, comentario.value || undefined)
    aviso.value = { aprovar: 'Aprovada.', publicar: 'Publicada.', rejeitar: 'Rejeitada.', arquivar: 'Arquivada.' }[acao]
    await carregar()
  } catch (e) {
    erroDaAcao.value = mensagemDeErro(e)
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

async function sair() {
  await equipe.sair().catch(() => {})
  roteador.push({ name: 'entrar' })
}
function trocarTema() {
  tema.value = alternarTema()
}
function mudarPagina(p) {
  filtros.pagina = p
  carregar()
}
</script>

<template>
  <div class="equipe">
    <nav class="lateral" aria-label="Área da equipe">
      <RouterLink to="/" class="marca">
        <span class="icone sol" aria-hidden="true">wb_twilight</span>
        <span class="serifa">Desperta · equipe</span>
      </RouterLink>
      <button
        v-for="s in STATUS" :key="s.valor" type="button" class="item" :class="{ ativo: filtros.status === s.valor }"
        :aria-current="filtros.status === s.valor ? 'page' : undefined" @click="filtros.status = s.valor"
      >
        <span class="icone" aria-hidden="true">{{ s.icone }}</span>
        <span class="nome">{{ s.nome }}</span>
        <span v-if="filtros.status === s.valor" class="conta">{{ lista.total.toLocaleString('pt-BR') }}</span>
      </button>
      <span class="grupo">SÓ ADMIN · FASE 5</span>
      <span class="item apagado"><span class="icone" aria-hidden="true">group</span>Equipe</span>
      <span class="item apagado"><span class="icone" aria-hidden="true">cloud_sync</span>Coletas</span>
      <span class="item apagado"><span class="icone" aria-hidden="true">receipt_long</span>Log do sistema</span>
      <div class="pe">
        <span v-if="eu">{{ eu.nome }} · {{ eu.papel }}</span>
        <div class="pe-botoes">
          <button type="button" class="link-claro" @click="trocarTema">{{ tema === 'escuro' ? 'Tema claro' : 'Tema escuro' }}</button>
          <button type="button" class="link-claro" @click="sair">Sair</button>
        </div>
      </div>
    </nav>

    <main id="principal" class="area">
      <header>
        <h1>{{ statusAtual.nome }}</h1>
        <p class="texto-2">
          {{ lista.total.toLocaleString('pt-BR') }} {{ lista.total === 1 ? 'notícia' : 'notícias' }} · mais antigas primeiro
        </p>
      </header>

      <div class="filtros">
        <div role="group" aria-label="Filtrar por caso" class="chips">
          <button
            v-for="c in CASOS" :key="c.valor" type="button" class="chip" :class="{ ativo: filtros.caso === c.valor }"
            :aria-pressed="filtros.caso === c.valor" @click="filtros.caso = c.valor"
          >{{ c.nome }}</button>
        </div>
        <label class="so-leitor" for="f-tema">Tema</label>
        <select id="f-tema" v-model="filtros.tema">
          <option value="">Todos os temas</option>
          <option v-for="t in temas" :key="t.cod_tema" :value="String(t.cod_tema)">{{ t.nome }}</option>
        </select>
      </div>

      <p v-if="aviso" class="aviso" role="status">
        <span class="icone" aria-hidden="true">check_circle</span>{{ aviso }}
        <button type="button" class="fechar" aria-label="Fechar aviso" @click="aviso = ''"><span class="icone" aria-hidden="true">close</span></button>
      </p>
      <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

      <div v-if="marcados.length" class="lote">
        <strong>{{ marcados.length }} {{ marcados.length === 1 ? 'selecionada' : 'selecionadas' }}</strong>
        <template v-if="['rascunho', 'em_revisao'].includes(filtros.status)">
          <button v-if="filtros.status === 'rascunho'" type="button" class="botao botao-contorno baixo" :disabled="ocupado" @click="agirEmLote('aprovar')">Aprovar</button>
          <button type="button" class="botao botao-principal baixo" :disabled="ocupado" @click="agirEmLote('publicar')">Publicar</button>
          <button type="button" class="botao botao-perigo baixo" :disabled="ocupado || !comentario.trim()" @click="agirEmLote('rejeitar')">Rejeitar</button>
          <span class="texto-2">Para rejeitar, escreva o comentário no painel ao lado. Até 200 por vez.</span>
        </template>
        <button v-else-if="filtros.status === 'publicada'" type="button" class="botao botao-contorno baixo" :disabled="ocupado" @click="agirEmLote('arquivar')">Arquivar</button>
      </div>

      <div class="paineis">
        <section class="cartao lista" aria-label="Notícias">
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
                <span class="meta texto-2">
                  <span v-if="n.origem === 'equipe'" class="origem">Escrita pela equipe</span>
                  <span>{{ n.tema?.nome }}</span>
                  <span>{{ dataHora(n.criado_em) }}</span>
                </span>
              </button>
            </div>
          </template>
          <div class="pe-lista"><Paginacao :pagina="lista.pagina || 1" :paginas="lista.paginas || 1" @ir="mudarPagina" /></div>
        </section>

        <section v-if="aberta" class="cartao editor" aria-labelledby="t-editor">
          <h2 id="t-editor" class="so-leitor">Editar notícia</h2>
          <div class="etiquetas">
            <span class="status">{{ aberta.status.replace('_', ' ') }}</span>
            <span v-if="geracao?.entrada?.caso" class="caso">{{ NOMES_CASO[geracao.entrada.caso] || geracao.entrada.caso }}</span>
            <span class="texto-2">{{ aberta.tema?.nome }} · criada em {{ dataHora(aberta.criado_em) }}</span>
          </div>

          <label for="ed-titulo">Título <span class="texto-2">({{ form.titulo.length }} de 200)</span></label>
          <input id="ed-titulo" v-model="form.titulo" type="text" maxlength="200" class="serifa">
          <label for="ed-resumo">Resumo <span class="texto-2">({{ form.resumo.length }} de 500)</span></label>
          <textarea id="ed-resumo" v-model="form.resumo" rows="3" maxlength="500"></textarea>
          <details>
            <summary>Corpo da notícia</summary>
            <label for="ed-corpo" class="so-leitor">Corpo</label>
            <textarea id="ed-corpo" v-model="form.corpo" rows="12"></textarea>
          </details>

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
          <p v-if="erroDaAcao" class="erro" role="alert">{{ erroDaAcao }}</p>

          <div class="acoes">
            <button v-if="podeAgir" type="button" class="botao botao-principal" :disabled="ocupado" @click="agir('publicar')">Publicar</button>
            <button v-if="aberta.status === 'rascunho'" type="button" class="botao botao-contorno" :disabled="ocupado" @click="agir('aprovar')">Aprovar</button>
            <button type="button" class="botao botao-contorno" :disabled="ocupado || !mudou" @click="salvar">Salvar texto</button>
            <button v-if="podeAgir" type="button" class="botao botao-perigo" :disabled="ocupado || !comentario.trim()" @click="agir('rejeitar')">Rejeitar</button>
            <button v-if="aberta.status === 'publicada'" type="button" class="botao botao-perigo" :disabled="ocupado" @click="agir('arquivar')">Arquivar</button>
          </div>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.equipe { min-height: 100vh; display: flex; flex-wrap: wrap; }

.lateral {
  flex: 1 1 220px;
  max-width: 260px;
  background: var(--rodape);
  color: #e1dad4;
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.marca { display: flex; align-items: center; gap: 8px; padding: 0 8px 20px; text-decoration: none; color: #f3eee6; font-size: 18px; font-weight: 700; }
.sol { font-size: 26px; color: #dcb48f; }
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #e1dad4;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.item .nome { flex: 1; }
.item.ativo { background: #38495b; color: #f3eee6; font-weight: 500; }
.item .conta { font-size: 13px; }
.item.apagado { color: #b8a798; cursor: default; }
.grupo { padding: 20px 12px 6px; font-size: 12px; letter-spacing: 0.06em; color: #b8a798; }
.pe { margin-top: auto; padding: 16px 12px 0; border-top: 1px solid #38495b; font-size: 14px; display: flex; flex-direction: column; gap: 8px; color: #f3eee6; }
.pe-botoes { display: flex; gap: 16px; }
.link-claro { background: none; border: none; padding: 0; font: inherit; color: #dcb48f; text-decoration: underline; cursor: pointer; }

.area { flex: 999 1 640px; min-width: 0; padding: 28px 32px; display: flex; flex-direction: column; gap: 16px; }
h1 { margin: 0; font-size: 28px; }
header p { margin: 6px 0 0; font-size: 15px; }

.filtros { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 20px;
  border: 1px solid var(--borda);
  background: var(--superficie);
  color: var(--texto);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
}
.chip.ativo { background: var(--principal); border-color: var(--principal); color: var(--sobre-principal); font-weight: 500; }
select, input[type='text'], textarea {
  border-radius: 8px;
  border: 1px solid var(--borda);
  background: var(--superficie-2);
  color: var(--texto);
  font: inherit;
}
select { min-height: 40px; padding: 0 12px; background: var(--superficie); max-width: 280px; }

.aviso { margin: 0; display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 10px; background: var(--superficie); border-left: 4px solid var(--ok); font-size: 15px; }
.aviso .icone:first-child { color: var(--ok); }
.fechar { margin-left: auto; background: none; border: none; color: var(--texto-2); cursor: pointer; width: 32px; height: 32px; }
.erro { margin: 0; color: var(--erro); font-weight: 500; }

.lote { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 10px 16px; background: var(--faixa); border-radius: 12px; font-size: 14px; }
.baixo { min-height: 36px; padding: 0 14px; }

.paineis { display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start; }
.lista { flex: 1 1 400px; min-width: 0; padding: 0; overflow: hidden; }
.vazio { margin: 0; padding: 24px; }
.linha-todos { display: flex; align-items: center; gap: 12px; padding: 12px 16px; font-size: 14px; border-bottom: 1px solid var(--linha); cursor: pointer; }
.linha { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--linha); border-left: 4px solid transparent; align-items: start; }
.linha.aberta { background: var(--faixa); border-left-color: var(--principal); }
input[type='checkbox'] { width: 18px; height: 18px; margin: 3px 0 0; accent-color: var(--principal); }
.abrir { background: none; border: none; padding: 0; font: inherit; color: var(--texto); text-align: left; cursor: pointer; display: flex; flex-direction: column; gap: 6px; }
.abrir:hover .titulo { text-decoration: underline; }
.titulo { font-weight: 500; line-height: 1.35; }
.meta { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; }
.origem { color: var(--destaque); font-weight: 500; }
.pe-lista { padding: 12px 16px; }

.editor { flex: 1 1 440px; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.etiquetas { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 13px; }
.status { padding: 3px 10px; border-radius: 10px; background: var(--superficie-2); }
.caso { color: var(--link); font-weight: 500; }
.editor label { font-size: 13px; font-weight: 500; margin-top: 6px; }
.editor input[type='text'] { min-height: 44px; padding: 0 12px; font-size: 19px; font-weight: 600; }
textarea { padding: 10px 12px; font-size: 15px; line-height: 1.5; resize: vertical; width: 100%; }
details summary { cursor: pointer; font-weight: 500; color: var(--link); padding: 6px 0; }
.usou { background: var(--superficie-2); border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 6px; font-size: 14px; }
.usou > strong { display: flex; align-items: center; gap: 6px; }
.usou > strong .icone { font-size: 18px; color: var(--link); }
.trechos { margin: 8px 0 0; padding-left: 20px; display: flex; flex-direction: column; gap: 8px; font-size: 13px; max-height: 280px; overflow-y: auto; }
.trechos .texto-2 { display: block; }
.historico ul { margin: 6px 0 0; padding-left: 20px; font-size: 14px; }
.acoes { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }

@media (max-width: 760px) {
  .lateral { max-width: none; flex-basis: 100%; }
  .area { padding: 20px 16px; }
}
</style>
