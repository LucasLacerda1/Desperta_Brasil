<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { alternarTema, temaAtual } from '../util/tema.js'

const rota = useRoute()
const roteador = useRouter()
const termo = ref(rota.query.q || '')
const tema = ref(temaAtual())
const avisoVoz = ref(false)

watch(() => rota.query.q, (q) => { termo.value = q || '' })

function buscar() {
  const q = termo.value.trim()
  if (q) roteador.push({ name: 'busca', query: { q } })
}

function trocarTema() {
  tema.value = alternarTema()
}
</script>

<template>
  <header class="cabecalho">
    <div class="conteudo linha">
      <RouterLink to="/" class="marca">
        <span class="icone sol" aria-hidden="true">wb_twilight</span>
        <span class="nomes">
          <span class="nome serifa">Desperta Brasil</span>
          <span class="lema">A Câmara dos Deputados em linguagem simples</span>
        </span>
      </RouterLink>

      <form class="busca" role="search" @submit.prevent="buscar">
        <label for="busca-topo" class="so-leitor">Buscar notícias</label>
        <span class="icone lupa" aria-hidden="true">search</span>
        <input id="busca-topo" v-model="termo" type="search" placeholder="Busque um assunto: salário mínimo, vacinas, escolas…">
        <button type="button" class="mic" aria-label="Buscar por voz" @click="avisoVoz = !avisoVoz">
          <span class="icone" aria-hidden="true">mic</span>
        </button>
      </form>

      <nav class="menu" aria-label="Principal">
        <RouterLink to="/temas">Temas</RouterLink>
        <RouterLink :to="{ path: '/', hash: '#como-funciona' }">Como funciona</RouterLink>
        <button type="button" class="botao-tema" :aria-label="tema === 'escuro' ? 'Mudar para o tema claro' : 'Mudar para o tema escuro'" @click="trocarTema">
          <span class="icone" aria-hidden="true">{{ tema === 'escuro' ? 'light_mode' : 'dark_mode' }}</span>
        </button>
      </nav>
    </div>
    <p v-if="avisoVoz" class="conteudo aviso-voz" role="status">
      A busca por voz (Whisper) entra na Fase 5. Neste protótipo, digite o assunto.
    </p>
  </header>
</template>

<style scoped>
.cabecalho { background: var(--cabecalho); color: var(--cabecalho-texto); }
.linha { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 32px; padding-block: 14px; }
.marca { display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--cabecalho-texto); }
.sol { font-size: 34px; color: var(--marca); }
.nomes { display: flex; flex-direction: column; line-height: 1.1; }
.nome { font-size: 26px; font-weight: 700; }
.lema { font-size: 13px; color: var(--cabecalho-texto-2); }

.busca {
  flex: 1 1 320px;
  max-width: 560px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--superficie);
  border: 1px solid var(--borda);
  border-radius: 28px;
  padding: 4px 6px 4px 18px;
}
.lupa { color: var(--texto-2); }
.busca input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  font: inherit;
  color: var(--texto);
  padding: 10px 0;
}
.busca input:focus { outline: none; }
.busca:focus-within { outline: 3px solid var(--foco); outline-offset: 2px; }
.mic {
  width: 44px;
  height: 44px;
  border-radius: 22px;
  border: none;
  background: var(--principal);
  color: var(--sobre-principal);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu { display: flex; align-items: center; gap: 20px; font-size: 15px; font-weight: 500; }
.menu a { color: var(--cabecalho-texto); text-decoration: none; }
.menu a:hover { text-decoration: underline; }
.botao-tema {
  width: 44px;
  height: 44px;
  border-radius: 22px;
  border: 1px solid var(--cabecalho-texto-2);
  background: transparent;
  color: var(--cabecalho-texto);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.aviso-voz { margin: 0 auto; padding-bottom: 12px; font-size: 14px; color: var(--cabecalho-texto-2); }

@media (max-width: 600px) {
  .lema { display: none; }
  .nome { font-size: 22px; }
  .menu { margin-left: auto; gap: 14px; }
  .linha { gap: 10px 16px; }
  .busca { order: 3; flex-basis: 100%; max-width: none; }
}
</style>
