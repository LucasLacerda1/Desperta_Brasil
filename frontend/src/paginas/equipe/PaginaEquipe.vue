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
      <h1>Equipe</h1>
      <p class="texto-2">Quem entra na área administrativa. Editor revisa e publica; admin também cuida da equipe, das coletas e do log.</p>
    </header>

    <p v-if="aviso" class="aviso" role="status"><span class="icone" aria-hidden="true">check_circle</span>{{ aviso }}</p>
    <p v-if="erro" class="erro" role="alert">{{ erro }}</p>

    <section class="cartao tabela-cartao" aria-labelledby="t-membros">
      <h2 id="t-membros">Membros ({{ membros.length }})</h2>
      <p v-if="carregando" class="texto-2">Carregando…</p>
      <div v-else class="rolagem">
        <table>
          <thead>
            <tr><th scope="col">Nome</th><th scope="col">E-mail</th><th scope="col">Papel</th><th scope="col">Situação</th><th scope="col">Último acesso</th><th scope="col"><span class="so-leitor">Ações</span></th></tr>
          </thead>
          <tbody>
            <template v-for="m in membros" :key="m.id">
              <tr :class="{ inativo: !m.ativo }">
                <td>{{ m.nome }} <span v-if="m.id === eu?.id" class="texto-2">(você)</span></td>
                <td class="quebra">{{ m.email }}</td>
                <td>
                  <label class="so-leitor" :for="`papel-${m.id}`">Papel de {{ m.nome }}</label>
                  <select :id="`papel-${m.id}`" :value="m.papel" @change="mudar(m, { papel: $event.target.value }, `${m.nome} agora é ${$event.target.value}.`)">
                    <option value="editor">editor</option>
                    <option value="admin">admin</option>
                  </select>
                </td>
                <td><span class="selo" :class="m.ativo ? 'ok' : 'off'">{{ m.ativo ? 'Ativo' : 'Desativado' }}</span></td>
                <td>{{ m.ultimo_acesso ? dataHora(m.ultimo_acesso) : 'nunca entrou' }}</td>
                <td>
                  <button
                    type="button" class="botao baixo" :class="m.ativo ? 'botao-perigo' : 'botao-contorno'"
                    @click="mudar(m, { ativo: !m.ativo }, m.ativo ? `${m.nome} foi desativado.` : `${m.nome} foi ativado.`)"
                  >{{ m.ativo ? 'Desativar' : 'Ativar' }}</button>
                </td>
              </tr>
              <tr v-if="erroDaLinha[m.id]" class="linha-erro"><td colspan="6" role="alert">{{ erroDaLinha[m.id] }}</td></tr>
            </template>
          </tbody>
        </table>
      </div>
    </section>

    <section class="cartao" aria-labelledby="t-novo">
      <h2 id="t-novo">Adicionar à equipe</h2>
      <p class="texto-2">O servidor confere tudo antes de gravar: nome (até 100 caracteres), e-mail válido e sem repetir, senha de 8 a 200 caracteres e papel.</p>
      <p v-if="erroDoForm" class="resumo-erros" role="alert"><span class="icone" aria-hidden="true">error</span>{{ erroDoForm }}</p>
      <!-- novalidate: a validacao que vale e a do Flask -->
      <form class="grade" novalidate @submit.prevent="criar">
        <div class="campo">
          <label for="m-nome">Nome</label>
          <input id="m-nome" v-model="novo.nome" type="text" autocomplete="off" :aria-invalid="!!erros.nome" aria-describedby="erro-m-nome">
          <span v-if="erros.nome" id="erro-m-nome" class="erro-campo">{{ erros.nome }}</span>
        </div>
        <div class="campo">
          <label for="m-email">E-mail</label>
          <input id="m-email" v-model="novo.email" type="email" autocomplete="off" :aria-invalid="!!erros.email" aria-describedby="erro-m-email">
          <span v-if="erros.email" id="erro-m-email" class="erro-campo">{{ erros.email }}</span>
        </div>
        <div class="campo">
          <label for="m-senha">Senha inicial</label>
          <input id="m-senha" v-model="novo.senha" type="password" autocomplete="new-password" :aria-invalid="!!erros.senha" aria-describedby="erro-m-senha">
          <span v-if="erros.senha" id="erro-m-senha" class="erro-campo">{{ erros.senha }}</span>
        </div>
        <div class="campo">
          <label for="m-papel">Papel</label>
          <select id="m-papel" v-model="novo.papel" :aria-invalid="!!erros.papel" aria-describedby="erro-m-papel">
            <option value="editor">editor</option>
            <option value="admin">admin</option>
          </select>
          <span v-if="erros.papel" id="erro-m-papel" class="erro-campo">{{ erros.papel }}</span>
        </div>
        <div class="enviar">
          <button type="submit" class="botao botao-principal" :disabled="enviando">{{ enviando ? 'Gravando…' : 'Adicionar' }}</button>
        </div>
      </form>
    </section>
  </LayoutEquipe>
</template>

<style scoped>
h1 { margin: 0; font-size: 28px; }
h2 { margin: 0 0 12px; font-size: 19px; }
header p { margin: 6px 0 0; font-size: 15px; max-width: 70ch; }
.aviso { margin: 0; display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 10px; background: var(--superficie); border-left: 4px solid var(--ok); }
.aviso .icone { color: var(--ok); }
.erro { margin: 0; color: var(--erro); font-weight: 500; }
.resumo-erros { display: flex; align-items: center; gap: 8px; color: var(--erro); font-weight: 600; margin: 0 0 12px; }

.rolagem { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; font-size: 13px; color: var(--texto-2); font-weight: 600; padding: 8px 10px; border-bottom: 2px solid var(--linha); white-space: nowrap; }
td { padding: 10px; border-bottom: 1px solid var(--linha); vertical-align: middle; }
.quebra { word-break: break-all; }
tr.inativo td { color: var(--texto-2); }
.linha-erro td { color: var(--erro); font-weight: 500; border-bottom: 1px solid var(--linha); }
.selo { padding: 2px 10px; border-radius: 999px; font-size: 13px; font-weight: 600; white-space: nowrap; }
.selo.ok { color: var(--ok); border: 1px solid var(--ok); }
.selo.off { color: var(--texto-2); border: 1px solid var(--linha); }
.baixo { min-height: 36px; padding: 0 14px; }

.grade { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; align-items: start; }
.campo { display: flex; flex-direction: column; gap: 6px; }
label { font-size: 14px; font-weight: 600; }
input, select {
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--borda);
  background: var(--superficie-2);
  color: var(--texto);
  font: inherit;
}
td select { min-height: 36px; }
[aria-invalid='true'] { border: 2px solid var(--erro); }
.erro-campo { color: var(--erro); font-size: 14px; font-weight: 500; }
.enviar { grid-column: 1 / -1; }
</style>
