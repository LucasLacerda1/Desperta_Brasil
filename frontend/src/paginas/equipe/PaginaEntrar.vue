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
  <main id="principal" class="tela">
    <form class="cartao caixa" @submit.prevent="entrar">
      <RouterLink to="/" class="marca">
        <span class="icone sol" aria-hidden="true">wb_twilight</span>
        <span class="serifa">Desperta Brasil</span>
      </RouterLink>
      <h1>Área da equipe</h1>
      <p class="texto-2">Só a equipe entra aqui. O portal não tem cadastro para visitantes.</p>

      <label for="e-email">E-mail</label>
      <input id="e-email" v-model="email" type="email" autocomplete="username" required>
      <label for="e-senha">Senha</label>
      <input id="e-senha" v-model="senha" type="password" autocomplete="current-password" required>

      <p v-if="erro" class="erro" role="alert"><span class="icone" aria-hidden="true">error</span>{{ erro }}</p>
      <button type="submit" class="botao botao-principal" :disabled="enviando">{{ enviando ? 'Entrando…' : 'Entrar' }}</button>
      <RouterLink to="/" class="voltar">Voltar ao portal</RouterLink>
    </form>
  </main>
</template>

<style scoped>
.tela { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px 16px; }
.caixa { width: 100%; max-width: 400px; padding: 32px; display: flex; flex-direction: column; gap: 10px; }
.marca { display: flex; align-items: center; gap: 8px; text-decoration: none; color: var(--texto); font-size: 22px; font-weight: 700; }
.sol { font-size: 30px; color: var(--destaque-forte); }
h1 { margin: 8px 0 0; font-size: 24px; }
p { margin: 0 0 8px; font-size: 14px; }
label { font-size: 14px; font-weight: 500; margin-top: 4px; }
input {
  min-height: 44px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--borda);
  background: var(--superficie-2);
  color: var(--texto);
  font: inherit;
}
.erro { display: flex; align-items: center; gap: 6px; color: var(--erro); font-weight: 500; margin: 4px 0 0; }
.botao { margin-top: 12px; }
.voltar { align-self: center; font-size: 14px; margin-top: 4px; }
</style>
