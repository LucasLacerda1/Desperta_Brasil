<template>
  <footer class="rodape">
    <div class="conteudo linha">
      <div class="sobre">
        <strong class="serifa nome">Desperta Brasil</strong>
        Sem propaganda e sem cadastro. Código aberto. Fonte dos dados: API de Dados Abertos da Câmara dos Deputados.
      </div>
      <nav aria-label="Rodapé" class="links">
        <RouterLink :to="{ path: '/', hash: '#como-funciona' }">Como funciona</RouterLink>
        <RouterLink to="/temas">Todos os temas</RouterLink>
        <RouterLink to="/equipe">Área da equipe</RouterLink>
      </nav>
    </div>
  </footer>
</template>

<style scoped>
.rodape { background: var(--rodape); color: var(--rodape-texto); margin-top: 48px; }
.linha { display: flex; flex-wrap: wrap; gap: 16px 48px; padding-block: 32px 96px; font-size: 14px; line-height: 1.6; }
.sobre { flex: 1 1 320px; }
.nome { display: block; font-size: 20px; color: #f3eee6; margin-bottom: 6px; }
.links { display: flex; flex-direction: column; gap: 6px; }
.links a { color: #dcb48f; }
</style>
