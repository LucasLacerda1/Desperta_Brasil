<script setup>
// Login da equipe (sessao Flask). O cookie de sessao e HttpOnly: o front nunca le a senha nem o cookie.
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { equipe, mensagemDeErro } from '../../services/api.js'

const rota = useRoute()
const roteador = useRouter()
const email = ref('')
const senha = ref('')
const erro = ref('')
const enviando = ref(false)

async function entrar() {
  erro.value = ''
  enviando.value = true
  try {
    await equipe.entrar(email.value, senha.value)
    // Volta para a tela da equipe que pediu o login (so enderecos da propria area)
    const volta = String(rota.query.volta || '')
    roteador.push(volta.startsWith('/equipe') ? volta : { name: 'fila' })
  } catch (e) {
    erro.value = mensagemDeErro(e)
  } finally {
    enviando.value = false
  }
}
</script>

<template>
  <main id="principal" class="flex min-h-screen items-center justify-center px-4 py-6">
    <form class="cartao flex w-full max-w-[400px] flex-col gap-2.5 p-8" @submit.prevent="entrar">
      <RouterLink to="/" class="flex items-center gap-2 text-[22px] font-bold text-texto no-underline hover:text-texto">
        <span class="icone text-[30px] text-destaque-forte" aria-hidden="true">wb_twilight</span>
        <span class="serifa">Desperta Brasil</span>
      </RouterLink>
      <h1 class="mt-2 mb-0 text-[24px]">Área da equipe</h1>
      <p class="texto-2 m-0 mb-2 text-[14px]">Só a equipe entra aqui. O portal não tem cadastro para visitantes.</p>

      <label for="e-email" class="mt-1 text-[14px] font-medium">E-mail</label>
      <input id="e-email" v-model="email" type="email" autocomplete="username" required class="campo-texto min-h-11 px-3">
      <label for="e-senha" class="mt-1 text-[14px] font-medium">Senha</label>
      <input id="e-senha" v-model="senha" type="password" autocomplete="current-password" required class="campo-texto min-h-11 px-3">

      <p v-if="erro" class="mt-1 mb-0 flex items-center gap-1.5 font-medium text-erro" role="alert"><span class="icone" aria-hidden="true">error</span>{{ erro }}</p>
      <button type="submit" class="botao botao-principal mt-3" :disabled="enviando">{{ enviando ? 'Entrando…' : 'Entrar' }}</button>
      <RouterLink to="/" class="mt-1 self-center text-[14px]">Voltar ao portal</RouterLink>
    </form>
  </main>
</template>
