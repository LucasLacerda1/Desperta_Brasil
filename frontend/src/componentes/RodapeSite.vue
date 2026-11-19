<template>
  <footer class="mt-12 bg-rodape text-rodape-texto">
    <div class="conteudo flex flex-wrap gap-x-12 gap-y-4 pt-8 pb-24 text-[14px] leading-relaxed">
      <div class="flex-[1_1_320px]">
        <strong class="serifa mb-1.5 block text-[20px] text-[#ffffff]">Desperta Brasil</strong>
        Sem propaganda e sem cadastro. Código aberto. Fonte dos dados: API de Dados Abertos da Câmara dos Deputados.
      </div>
      <nav aria-label="Rodapé" class="flex flex-col gap-1.5 [&_a]:text-[#ecc9a6] [&_a:hover]:text-[#ffffff]">
        <RouterLink to="/como-funciona">Como funciona</RouterLink>
        <RouterLink to="/temas">Todos os temas</RouterLink>
        <RouterLink to="/equipe">Área da equipe</RouterLink>
      </nav>
    </div>
  </footer>
</template>
