<script setup>
// RF13 e LGPD: sem o aceite, nada e guardado sobre os temas lidos.
// Prototipo: a escolha fica so neste navegador; as rotas do visitante ainda nao existem (falta na Fase 4).
import { ref } from 'vue'

const CHAVE = 'desperta-cookies'
function lida() {
  try {
    return localStorage.getItem(CHAVE)
  } catch {
    return null
  }
}
const resposta = ref(lida())

function responder(valor) {
  resposta.value = valor
  try {
    localStorage.setItem(CHAVE, valor)
  } catch {
    // sem localStorage: o aviso volta na proxima visita
  }
}
</script>

<template>
  <div v-if="!resposta" class="aviso" role="region" aria-label="Aviso de cookies">
    <div class="conteudo linha">
      <p>
        Podemos guardar um cookie anônimo para lembrar os temas que você mais lê e montar a página para você.
        Nada nele identifica você, e sem o aceite nada é guardado.
      </p>
      <div class="botoes">
        <button type="button" class="botao botao-contorno" @click="responder('recusado')">Agora não</button>
        <button type="button" class="botao botao-principal" @click="responder('aceito')">Aceitar</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.aviso {
  position: sticky;
  bottom: 0;
  background: var(--superficie);
  border-top: 3px solid var(--destaque-forte);
  box-shadow: var(--sombra);
  z-index: 10;
}
.linha { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 24px; padding-block: 16px; }
p { margin: 0; flex: 1 1 420px; font-size: 15px; }
.botoes { display: flex; gap: 12px; }
</style>
