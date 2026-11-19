<script setup>
// RF13 e LGPD: sem o aceite, nada e guardado sobre os temas lidos.
// Por enquanto a escolha fica so neste navegador; as rotas do visitante ainda nao existem (falta na Fase 4).
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
  <div v-if="!resposta" class="sticky bottom-0 z-10 border-t-[3px] border-destaque-forte bg-superficie shadow-[var(--sombra)]" role="region" aria-label="Aviso de cookies">
    <div class="conteudo flex flex-wrap items-center gap-x-6 gap-y-3 py-4">
      <p class="m-0 flex-[1_1_420px] text-[15px]">
        Podemos guardar um cookie anônimo para lembrar os temas que você mais lê e montar a página para você.
        Nada nele identifica você, e sem o aceite nada é guardado.
      </p>
      <div class="flex gap-3">
        <button type="button" class="botao botao-contorno" @click="responder('recusado')">Agora não</button>
        <button type="button" class="botao botao-principal" @click="responder('aceito')">Aceitar</button>
      </div>
    </div>
  </div>
</template>
