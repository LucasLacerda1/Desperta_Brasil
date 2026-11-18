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
    <RouterLink :to="{ name: 'fila' }" class="inline-flex items-center gap-1.5 self-start text-[14px] font-medium [&_.icone]:text-[18px]"><span class="icone" aria-hidden="true">arrow_back</span>Voltar à fila</RouterLink>

    <p v-if="!noticia && !erroGeral" class="texto-2">Carregando…</p>
    <p v-else-if="!noticia" class="texto-erro" role="alert">{{ erroGeral }}</p>

    <template v-else>
      <header>
        <h1 class="m-0 text-[28px]">Editar notícia</h1>
        <p class="texto-2 mt-1.5 mb-0 flex flex-wrap items-center gap-1.5 text-[14px]">
          <span class="rounded-[10px] bg-faixa px-2.5 py-0.5 font-medium text-texto">{{ nomeDoStatus(noticia.status) }}</span>
          nº {{ noticia.id }} · criada em {{ dataHora(noticia.criado_em) }}
          <template v-if="noticia.alterado_em"> · alterada em {{ dataHora(noticia.alterado_em) }}</template>
          <template v-if="noticia.status === 'publicada'">
            · <RouterLink :to="{ name: 'noticia', params: { slug: noticia.slug } }">ver no portal</RouterLink>
          </template>
        </p>
      </header>

      <p v-if="!podeEditar" class="cartao m-0 border-l-4 border-erro" role="status">
        Notícia {{ nomeDoStatus(noticia.status).toLowerCase() }} não é editada. Só rascunho, aprovada ou publicada.
      </p>
      <p v-if="aviso" class="aviso-ok" role="status"><span class="icone" aria-hidden="true">check_circle</span>{{ aviso }}</p>
      <div v-if="erroGeral" class="flex gap-2.5 rounded-[10px] border-l-4 border-erro bg-superficie px-4 py-3 text-erro [&_p]:mt-1 [&_p]:mb-0" role="alert" tabindex="-1">
        <span class="icone" aria-hidden="true">error</span>
        <div>
          <strong>{{ erroGeral }}</strong>
          <p v-if="Object.keys(erros).length > 1" class="texto-2">{{ Object.keys(erros).length }} campos precisam de ajuste.</p>
        </div>
      </div>

      <!-- novalidate: quem confere e o servidor (a tela so ajuda com os contadores) -->
      <form class="cartao flex max-w-[860px] flex-col gap-1" novalidate @submit.prevent="salvar()">
        <fieldset class="m-0 flex flex-col gap-5 border-none p-0 [&_label]:text-[14px] [&_label]:font-semibold" :disabled="!podeEditar || salvando">
          <div class="flex flex-col gap-1.5">
            <label for="ed-titulo">Título</label>
            <input
              id="ed-titulo" v-model="form.titulo" type="text" class="campo-texto font-serifa min-h-12 w-full px-3 text-[20px] font-semibold"
              :aria-invalid="!!erros.titulo" aria-describedby="ajuda-titulo erro-titulo"
            >
            <div class="flex justify-between gap-3 text-[13px]">
              <span id="ajuda-titulo" class="texto-2">
                <template v-if="noticia.status === 'publicada'">O endereço da notícia não muda depois de publicada.</template>
                <template v-else>O endereço (slug) acompanha o título até a publicação.</template>
              </span>
              <span class="text-[13px] whitespace-nowrap" :class="form.titulo.length > LIMITES.titulo ? 'font-bold text-erro' : 'text-texto-2'">{{ form.titulo.length }} / {{ LIMITES.titulo }}</span>
            </div>
            <span v-if="erros.titulo" id="erro-titulo" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.titulo }}</span>
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="ed-resumo">Resumo</label>
            <textarea id="ed-resumo" v-model="form.resumo" rows="3" class="campo-texto w-full resize-y px-3 py-2.5 leading-[1.55]" :aria-invalid="!!erros.resumo" aria-describedby="ajuda-resumo erro-resumo"></textarea>
            <div class="flex justify-between gap-3 text-[13px]">
              <span id="ajuda-resumo" class="texto-2">Aparece no cartão da página inicial.</span>
              <span class="text-[13px] whitespace-nowrap" :class="form.resumo.length > LIMITES.resumo ? 'font-bold text-erro' : 'text-texto-2'">{{ form.resumo.length }} / {{ LIMITES.resumo }}</span>
            </div>
            <span v-if="erros.resumo" id="erro-resumo" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.resumo }}</span>
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="ed-cod_tema">Tema principal</label>
            <select id="ed-cod_tema" v-model="form.cod_tema" class="campo-texto min-h-11 w-full max-w-[420px] px-3" :aria-invalid="!!erros.cod_tema" aria-describedby="erro-cod_tema">
              <option v-for="t in temas" :key="t.cod_tema" :value="t.cod_tema">{{ t.nome }}</option>
            </select>
            <span v-if="erros.cod_tema" id="erro-cod_tema" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.cod_tema }}</span>
          </div>

          <div class="flex flex-col gap-1.5">
            <label for="ed-corpo">Corpo</label>
            <textarea id="ed-corpo" v-model="form.corpo" rows="18" class="campo-texto w-full resize-y px-3 py-2.5 font-mono text-[14px] leading-[1.55]" :aria-invalid="!!erros.corpo" aria-describedby="ajuda-corpo erro-corpo"></textarea>
            <span id="ajuda-corpo" class="texto-2 text-[13px]">Cada seção começa com "## " (por exemplo, "## O que propõe"), como na planta da notícia.</span>
            <span v-if="erros.corpo" id="erro-corpo" class="erro-campo"><span class="icone" aria-hidden="true">error</span>{{ erros.corpo }}</span>
          </div>
        </fieldset>

        <div class="mt-5 flex flex-wrap items-center gap-2.5">
          <button type="submit" class="botao botao-principal" :disabled="!podeEditar || salvando || !mudou">{{ salvando ? 'Salvando…' : 'Salvar' }}</button>
          <button type="button" class="botao botao-contorno" :disabled="!podeEditar || salvando || !mudou" @click="salvar('voltar')">Salvar e voltar à fila</button>
          <button type="button" class="botao botao-perigo" :disabled="salvando || !mudou" @click="descartar">Descartar mudanças</button>
          <span v-if="mudou" class="texto-2">Há mudanças sem salvar.</span>
        </div>
      </form>

      <details v-if="noticia.revisoes?.length" class="cartao max-w-[860px] [&_summary]:cursor-pointer [&_summary]:font-medium [&_summary]:text-link">
        <summary>Histórico da revisão ({{ noticia.revisoes.length }})</summary>
        <ul class="mt-2 mb-0 flex flex-col gap-1 pl-5 text-[14px]">
          <li v-for="(r, i) in noticia.revisoes" :key="i">
            <strong>{{ r.acao }}</strong> por {{ r.administrador || 'equipe' }}, {{ dataHora(r.data_hora) }}
            <template v-if="r.comentario">: {{ r.comentario }}</template>
          </li>
        </ul>
      </details>
    </template>
  </LayoutEquipe>
</template>
