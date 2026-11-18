<script setup>
// Editar noticia (RF16): formulario com validacao no servidor.
// O Flask confere todos os campos de uma vez (conferir_formulario) e devolve
// {"erro": ..., "campos": {campo: mensagem}}; cada mensagem aparece embaixo do seu campo.
import { computed, reactive, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { equipe, errosDosCampos, mensagemDeErro, portal } from '../../services/api.js'
import { dataHora } from '../../util/datas.js'
import { nomeDoStatus } from '../../util/equipe.js'
import LayoutEquipe from '../../componentes/LayoutEquipe.vue'

// Mesmos tamanhos do banco (noticia.titulo String(200), noticia.resumo String(500))
const LIMITES = { titulo: 200, resumo: 500 }
const EDITAVEIS = ['rascunho', 'em_revisao', 'publicada']

const rota = useRoute()
const roteador = useRouter()
const noticia = ref(null)
const temas = ref([])
const form = reactive({ titulo: '', resumo: '', cod_tema: null, corpo: '' })
const erros = ref({})
const erroGeral = ref('')
const aviso = ref('')
const salvando = ref(false)

const podeEditar = computed(() => EDITAVEIS.includes(noticia.value?.status))
const mudou = computed(() => {
  const n = noticia.value
  return !!n && (form.titulo !== n.titulo || form.resumo !== n.resumo || form.corpo !== n.corpo || form.cod_tema !== n.tema?.cod_tema)
})

async function iniciar() {
  document.title = 'Editar notícia — Desperta Brasil'
  portal.temas().then((r) => { temas.value = r.itens }).catch(() => {})
  try {
    preencher(await equipe.detalhe(rota.params.id))
  } catch (e) {
    erroGeral.value = mensagemDeErro(e)
  }
}

function preencher(d) {
  noticia.value = d
  Object.assign(form, { titulo: d.titulo, resumo: d.resumo, corpo: d.corpo, cod_tema: d.tema?.cod_tema ?? null })
}

// Manda so o que mudou: o service registra em noticia_revisao o que foi alterado
function camposMudados() {
  const n = noticia.value
  const dados = {}
  if (form.titulo !== n.titulo) dados.titulo = form.titulo
  if (form.resumo !== n.resumo) dados.resumo = form.resumo
  if (form.corpo !== n.corpo) dados.corpo = form.corpo
  if (form.cod_tema !== n.tema?.cod_tema) dados.cod_tema = form.cod_tema
  return dados
}

async function salvar(depois) {
  salvando.value = true
  erros.value = {}
  erroGeral.value = ''
  aviso.value = ''
  try {
    preencher(await equipe.editar(noticia.value.id, camposMudados()))
    if (depois === 'voltar') {
      roteador.push({ name: 'fila', query: noticia.value.status === 'rascunho' ? {} : { status: noticia.value.status } })
      return
    }
    aviso.value = 'Mudanças salvas. Ficaram registradas no histórico da notícia.'
  } catch (e) {
    erros.value = errosDosCampos(e)
    erroGeral.value = mensagemDeErro(e)
    // Leva o foco ao primeiro campo com erro (leitor de tela e teclado)
    const primeiro = ['titulo', 'resumo', 'cod_tema', 'corpo'].find((c) => erros.value[c])
    if (primeiro) document.getElementById(`ed-${primeiro}`)?.focus()
  } finally {
    salvando.value = false
  }
}

function descartar() {
  preencher(noticia.value)
  erros.value = {}
  erroGeral.value = ''
}

onBeforeRouteLeave(() => {
  if (mudou.value && !salvando.value) return window.confirm('Há mudanças sem salvar. Sair mesmo assim?')
  return true
})
</script>

<template>
  <LayoutEquipe @pronto="iniciar">
    <RouterLink :to="{ name: 'fila' }" class="voltar"><span class="icone" aria-hidden="true">arrow_back</span>Voltar à fila</RouterLink>

    <p v-if="!noticia && !erroGeral" class="texto-2">Carregando…</p>
    <p v-else-if="!noticia" class="erro" role="alert">{{ erroGeral }}</p>

    <template v-else>
      <header>
        <h1>Editar notícia</h1>
        <p class="texto-2">
          <span class="status">{{ nomeDoStatus(noticia.status) }}</span>
          nº {{ noticia.id }} · criada em {{ dataHora(noticia.criado_em) }}
          <template v-if="noticia.alterado_em"> · alterada em {{ dataHora(noticia.alterado_em) }}</template>
          <template v-if="noticia.status === 'publicada'">
            · <RouterLink :to="{ name: 'noticia', params: { slug: noticia.slug } }">ver no portal</RouterLink>
          </template>
        </p>
      </header>

      <p v-if="!podeEditar" class="cartao bloqueio" role="status">
        Notícia {{ nomeDoStatus(noticia.status).toLowerCase() }} não é editada. Só rascunho, aprovada ou publicada.
      </p>
      <p v-if="aviso" class="aviso" role="status"><span class="icone" aria-hidden="true">check_circle</span>{{ aviso }}</p>
      <div v-if="erroGeral" class="resumo-erros" role="alert" tabindex="-1">
        <span class="icone" aria-hidden="true">error</span>
        <div>
          <strong>{{ erroGeral }}</strong>
          <p v-if="Object.keys(erros).length > 1" class="texto-2">{{ Object.keys(erros).length }} campos precisam de ajuste.</p>
        </div>
      </div>

      <!-- novalidate: quem confere e o servidor (a tela so ajuda com os contadores) -->
      <form class="cartao formulario" novalidate @submit.prevent="salvar()">
        <fieldset :disabled="!podeEditar || salvando">
          <div class="campo">
            <label for="ed-titulo">Título</label>
            <input
              id="ed-titulo" v-model="form.titulo" type="text" class="serifa titulo"
              :aria-invalid="!!erros.titulo" aria-describedby="ajuda-titulo erro-titulo"
            >
            <div class="linha-ajuda">
              <span id="ajuda-titulo" class="texto-2">
                <template v-if="noticia.status === 'publicada'">O endereço da notícia não muda depois de publicada.</template>
                <template v-else>O endereço (slug) acompanha o título até a publicação.</template>
              </span>
              <span class="contador" :class="{ passou: form.titulo.length > LIMITES.titulo }">{{ form.titulo.length }} / {{ LIMITES.titulo }}</span>
            </div>
            <span v-if="erros.titulo" id="erro-titulo" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.titulo }}</span>
          </div>

          <div class="campo">
            <label for="ed-resumo">Resumo</label>
            <textarea id="ed-resumo" v-model="form.resumo" rows="3" :aria-invalid="!!erros.resumo" aria-describedby="ajuda-resumo erro-resumo"></textarea>
            <div class="linha-ajuda">
              <span id="ajuda-resumo" class="texto-2">Aparece no cartão da página inicial.</span>
              <span class="contador" :class="{ passou: form.resumo.length > LIMITES.resumo }">{{ form.resumo.length }} / {{ LIMITES.resumo }}</span>
            </div>
            <span v-if="erros.resumo" id="erro-resumo" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.resumo }}</span>
          </div>

          <div class="campo">
            <label for="ed-cod_tema">Tema principal</label>
            <select id="ed-cod_tema" v-model="form.cod_tema" :aria-invalid="!!erros.cod_tema" aria-describedby="erro-cod_tema">
              <option v-for="t in temas" :key="t.cod_tema" :value="t.cod_tema">{{ t.nome }}</option>
            </select>
            <span v-if="erros.cod_tema" id="erro-cod_tema" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.cod_tema }}</span>
          </div>

          <div class="campo">
            <label for="ed-corpo">Corpo</label>
            <textarea id="ed-corpo" v-model="form.corpo" rows="18" class="corpo" :aria-invalid="!!erros.corpo" aria-describedby="ajuda-corpo erro-corpo"></textarea>
            <span id="ajuda-corpo" class="texto-2">Cada seção começa com "## " (por exemplo, "## O que propõe"), como na planta da notícia.</span>
            <span v-if="erros.corpo" id="erro-corpo" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.corpo }}</span>
          </div>
        </fieldset>

        <div class="acoes">
          <button type="submit" class="botao botao-principal" :disabled="!podeEditar || salvando || !mudou">{{ salvando ? 'Salvando…' : 'Salvar' }}</button>
          <button type="button" class="botao botao-contorno" :disabled="!podeEditar || salvando || !mudou" @click="salvar('voltar')">Salvar e voltar à fila</button>
          <button type="button" class="botao botao-perigo" :disabled="salvando || !mudou" @click="descartar">Descartar mudanças</button>
          <span v-if="mudou" class="texto-2">Há mudanças sem salvar.</span>
        </div>
      </form>

      <details v-if="noticia.revisoes?.length" class="cartao historico">
        <summary>Histórico da revisão ({{ noticia.revisoes.length }})</summary>
        <ul>
          <li v-for="(r, i) in noticia.revisoes" :key="i">
            <strong>{{ r.acao }}</strong> por {{ r.administrador || 'equipe' }}, {{ dataHora(r.data_hora) }}
            <template v-if="r.comentario">: {{ r.comentario }}</template>
          </li>
        </ul>
      </details>
    </template>
  </LayoutEquipe>
</template>

<style scoped>
.voltar { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 500; align-self: flex-start; }
.voltar .icone { font-size: 18px; }
h1 { margin: 0; font-size: 28px; }
header p { margin: 6px 0 0; font-size: 14px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.status { padding: 2px 10px; border-radius: 10px; background: var(--faixa); color: var(--texto); font-weight: 500; }

.bloqueio { margin: 0; border-left: 4px solid var(--erro); }
.aviso { margin: 0; display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 10px; background: var(--superficie); border-left: 4px solid var(--ok); }
.aviso .icone { color: var(--ok); }
.resumo-erros { display: flex; gap: 10px; padding: 12px 16px; border-radius: 10px; background: var(--superficie); border-left: 4px solid var(--erro); color: var(--erro); }
.resumo-erros p { margin: 4px 0 0; }

.formulario { max-width: 860px; display: flex; flex-direction: column; gap: 4px; }
fieldset { border: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 20px; }
.campo { display: flex; flex-direction: column; gap: 6px; }
label { font-size: 14px; font-weight: 600; }
input, textarea, select {
  border-radius: 8px;
  border: 1px solid var(--borda);
  background: var(--superficie-2);
  color: var(--texto);
  font: inherit;
  width: 100%;
}
input { min-height: 48px; padding: 0 12px; }
.titulo { font-size: 20px; font-weight: 600; }
select { min-height: 44px; padding: 0 12px; max-width: 420px; }
textarea { padding: 10px 12px; line-height: 1.55; resize: vertical; }
.corpo { font-family: ui-monospace, 'SFMono-Regular', Menlo, monospace; font-size: 14px; }
[aria-invalid='true'] { border: 2px solid var(--erro); }
.linha-ajuda { display: flex; justify-content: space-between; gap: 12px; font-size: 13px; }
.contador { font-size: 13px; color: var(--texto-2); white-space: nowrap; }
.contador.passou { color: var(--erro); font-weight: 700; }
.erro-campo { display: flex; align-items: center; gap: 6px; color: var(--erro); font-size: 14px; font-weight: 500; }
.erro-campo .icone { font-size: 18px; }
.erro { color: var(--erro); font-weight: 500; }
.acoes { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-top: 20px; }

.historico summary { cursor: pointer; font-weight: 500; color: var(--link); }
.historico ul { margin: 8px 0 0; padding-left: 20px; font-size: 14px; display: flex; flex-direction: column; gap: 4px; }
</style>
