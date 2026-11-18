<script setup>
// Equipe (so admin, RF16): quem entra na area administrativa e com qual papel.
// Ninguem e apagado (decisao 10.4): quem sai fica desativado, para manter o historico.
import { reactive, ref } from 'vue'
import { equipe, errosDosCampos, mensagemDeErro } from '../../services/api.js'
import { dataHora } from '../../util/datas.js'
import LayoutEquipe from '../../componentes/LayoutEquipe.vue'

const eu = ref(null)
const membros = ref([])
const carregando = ref(true)
const erro = ref('')
const aviso = ref('')
const erroDaLinha = ref({}) // {id: mensagem}

const novo = reactive({ nome: '', email: '', senha: '', papel: 'editor' })
const erros = ref({})
const erroDoForm = ref('')
const enviando = ref(false)

async function iniciar(quem) {
  document.title = 'Equipe — Desperta Brasil'
  eu.value = quem
  await carregar()
}

async function carregar() {
  carregando.value = true
  try {
    membros.value = (await equipe.membros()).itens
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    carregando.value = false
  }
}

async function criar() {
  enviando.value = true
  erros.value = {}
  erroDoForm.value = ''
  aviso.value = ''
  try {
    const { administrador } = await equipe.criarMembro({ ...novo })
    aviso.value = `${administrador.nome} entrou na equipe como ${administrador.papel}.`
    Object.assign(novo, { nome: '', email: '', senha: '', papel: 'editor' })
    await carregar()
  } catch (e) {
    erros.value = errosDosCampos(e)
    erroDoForm.value = mensagemDeErro(e)
    const primeiro = ['nome', 'email', 'senha', 'papel'].find((c) => erros.value[c])
    if (primeiro) document.getElementById(`m-${primeiro}`)?.focus()
  } finally {
    enviando.value = false
  }
}

async function mudar(membro, dados, mensagem) {
  erroDaLinha.value = {}
  aviso.value = ''
  try {
    await equipe.editarMembro(membro.id, dados)
    aviso.value = mensagem
    await carregar()
  } catch (e) {
    erroDaLinha.value = { [membro.id]: mensagemDeErro(e) }
    await carregar()
  }
}
</script>

<template>
  <LayoutEquipe so-admin @pronto="iniciar">
    <header>
      <h1 class="m-0 text-[28px]">Equipe</h1>
      <p class="texto-2 mt-1.5 mb-0 max-w-[70ch] text-[15px]">Quem entra na área administrativa. Editor revisa e publica; admin também cuida da equipe, das coletas e do log.</p>
    </header>

    <p v-if="aviso" class="aviso-ok" role="status"><span class="icone" aria-hidden="true">check_circle</span>{{ aviso }}</p>
    <p v-if="erro" class="texto-erro" role="alert">{{ erro }}</p>

    <section class="cartao" aria-labelledby="t-membros">
      <h2 id="t-membros" class="m-0 mb-3 text-[19px]">Membros ({{ membros.length }})</h2>
      <p v-if="carregando" class="texto-2">Carregando…</p>
      <div v-else class="overflow-x-auto">
        <table class="tabela">
          <thead>
            <tr><th scope="col">Nome</th><th scope="col">E-mail</th><th scope="col">Papel</th><th scope="col">Situação</th><th scope="col">Último acesso</th><th scope="col"><span class="so-leitor">Ações</span></th></tr>
          </thead>
          <tbody>
            <template v-for="m in membros" :key="m.id">
              <tr :class="{ '[&_td]:text-texto-2': !m.ativo }">
                <td>{{ m.nome }} <span v-if="m.id === eu?.id" class="texto-2">(você)</span></td>
                <td class="break-all">{{ m.email }}</td>
                <td>
                  <label class="so-leitor" :for="`papel-${m.id}`">Papel de {{ m.nome }}</label>
                  <select :id="`papel-${m.id}`" class="campo-texto min-h-9 px-2" :value="m.papel" @change="mudar(m, { papel: $event.target.value }, `${m.nome} agora é ${$event.target.value}.`)">
                    <option value="editor">editor</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td><span class="selo" :class="m.ativo ? 'border-ok text-ok' : 'text-texto-2'">{{ m.ativo ? 'Ativo' : 'Desativado' }}</span></td>
                <td>{{ m.ultimo_acesso ? dataHora(m.ultimo_acesso) : 'nunca entrou' }}</td>
                <td>
                  <button
                    type="button" class="botao botao-baixo" :class="m.ativo ? 'botao-perigo' : 'botao-contorno'"
                    @click="mudar(m, { ativo: !m.ativo }, m.ativo ? `${m.nome} foi desativado.` : `${m.nome} foi ativado.`)"
                  >{{ m.ativo ? 'Desativar' : 'Ativar' }}</button>
                </td>
              </tr>
              <tr v-if="erroDaLinha[m.id]" class="[&_td]:font-medium [&_td]:text-erro"><td colspan="6" role="alert">{{ erroDaLinha[m.id] }}</td></tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <section class="cartao" aria-labelledby="t-novo">
      <h2 id="t-novo" class="m-0 mb-3 text-[19px]">Adicionar à equipe</h2>
      <p class="texto-2">O servidor confere tudo antes de gravar: nome (até 100 caracteres), e-mail válido e sem repetir, senha de 8 a 200 caracteres e papel.</p>
      <p v-if="erroDoForm" class="m-0 mb-3 flex items-center gap-2 font-semibold text-erro" role="alert"><span class="icone" aria-hidden="true">error</span>{{ erroDoForm }}</p>
      <!-- novalidate: a validacao que vale e a do Flask -->
      <form class="grid grid-cols-1 items-start gap-4 sm:grid-cols-2 lg:grid-cols-4 [&_label]:text-[14px] [&_label]:font-semibold" novalidate @submit.prevent="criar">
        <div class="flex flex-col gap-1.5">
          <label for="m-nome">Nome</label>
          <input id="m-nome" class="campo-texto min-h-11 px-3" v-model="novo.nome" type="text" autocomplete="off" :aria-invalid="!!erros.nome" aria-describedby="erro-m-nome">
          <span v-if="erros.nome" id="erro-m-nome" class="erro-campo">{{ erros.nome }}</span>
        </div>
        <div class="flex flex-col gap-1.5">
          <label for="m-email">E-mail</label>
          <input id="m-email" class="campo-texto min-h-11 px-3" v-model="novo.email" type="email" autocomplete="off" :aria-invalid="!!erros.email" aria-describedby="erro-m-email">
          <span v-if="erros.email" id="erro-m-email" class="erro-campo">{{ erros.email }}</span>
        </div>
        <div class="flex flex-col gap-1.5">
          <label for="m-senha">Senha inicial</label>
          <input id="m-senha" class="campo-texto min-h-11 px-3" v-model="novo.senha" type="password" autocomplete="new-password" :aria-invalid="!!erros.senha" aria-describedby="erro-m-senha">
          <span v-if="erros.senha" id="erro-m-senha" class="erro-campo">{{ erros.senha }}</span>
        </div>
        <div class="flex flex-col gap-1.5">
          <label for="m-papel">Papel</label>
          <select id="m-papel" class="campo-texto min-h-11 px-3" v-model="novo.papel" :aria-invalid="!!erros.papel" aria-describedby="erro-m-papel">
            <option value="editor">editor</option>
            <option value="admin">admin</option>
          </select>
          <span v-if="erros.papel" id="erro-m-papel" class="erro-campo">{{ erros.papel }}</span>
        </div>
        <div class="col-span-full">
          <button type="submit" class="botao botao-principal" :disabled="enviando">{{ enviando ? 'Gravando…' : 'Adicionar' }}</button>
        </div>
      </form>
    </section>
  </LayoutEquipe>
</template>
