<template>
  <div class="conteudo pagina">
    <span class="icone" aria-hidden="true">travel_explore</span>
    <h1 class="serifa">Página não encontrada</h1>
    <p class="texto-2">O endereço pode ter mudado ou a notícia pode ter sido arquivada.</p>
    <RouterLink to="/" class="botao botao-principal">Voltar ao início</RouterLink>
  </div>
</template>

<style scoped>
.pagina { padding-block: 72px; display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
.icone { font-size: 56px; color: var(--destaque); }
h1 { margin: 0; }
p { margin: 0 0 12px; }
</style>
