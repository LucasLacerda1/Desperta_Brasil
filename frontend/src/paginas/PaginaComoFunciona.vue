<script setup>
// Como funciona (transparencia, decisao 22.5): de onde vem os dados, como a noticia e escrita,
// conferida e publicada, e o que fazemos quando a Camara nao informa algo.
import { onMounted } from 'vue'

const SECOES_DA_NOTICIA = [
  { titulo: 'Parágrafo principal', texto: 'Só o fato: o que aconteceu, com qual proposta e quando.' },
  { titulo: 'O que propõe', texto: 'A ementa da proposta em linguagem simples, com o link do texto completo.' },
  { titulo: 'Resultado da votação', texto: 'Quando houve votação: placar, voto de cada deputado e orientação dos partidos, se a Câmara publicou.' },
  { titulo: 'Onde está na Câmara', texto: 'A situação atual da proposta, explicada, e os últimos passos do andamento.' },
  { titulo: 'O que a Câmara não informou', texto: 'Os dados que faltam na fonte oficial, com o endereço onde conferimos.' },
  { titulo: 'Atualizações', texto: 'Os fatos novos sobre a mesma proposta, do mais recente para o mais antigo.' },
]

onMounted(() => {
  document.title = 'Como funciona — Desperta Brasil'
})
</script>

<template>
  <div class="conteudo flex max-w-[900px] flex-col gap-6 pt-6 [&_h2]:m-0 [&_h2]:mb-2 [&_h2]:text-[22px] [&_p]:m-0 [&_p]:mb-2.5 [&_p]:text-[17px] [&_p]:leading-[1.65] [&_p:last-child]:mb-0">
    <header class="flex flex-col gap-3">
      <p class="mb-0! text-[14px]! font-semibold tracking-[0.06em] text-destaque uppercase">Transparência</p>
      <h1 class="serifa m-0 text-[clamp(30px,4.4vw,44px)]">Como o Desperta Brasil funciona</h1>
      <p class="mb-0! text-[19px]! leading-[1.6]! text-texto-2">
        Acompanhamos a Câmara dos Deputados e contamos, em linguagem simples, o que foi votado, o que foi apresentado e em que pé está cada proposta.
        Esta página explica de onde vêm os dados, como cada notícia é escrita e o que fazemos quando falta alguma informação.
      </p>
    </header>

    <ol class="m-0 flex list-none flex-col gap-4 p-0">
      <li class="cartao flex flex-col items-start gap-2 sm:flex-row sm:gap-5">
        <span class="icone flex-none text-[36px] text-destaque-forte" aria-hidden="true">cloud_download</span>
        <div>
          <h2 class="serifa">1. Os dados vêm da Câmara</h2>
          <p>
            A única fonte é a <a href="https://dadosabertos.camara.leg.br/" target="_blank" rel="noopener">API de Dados Abertos da Câmara dos Deputados</a>,
            pública e gratuita. Um programa busca as votações, as reuniões e os projetos <strong>de hora em hora</strong>, confere tudo de novo
            <strong>toda madrugada</strong> e atualiza deputados, partidos e comissões <strong>uma vez por semana</strong>.
          </p>
          <p>
            Guardamos uma cópia dos dados exatamente como a Câmara mandou. Por isso o site continua no ar mesmo quando a API da Câmara cai.
            Nesse caso, o topo da página avisa que os dados podem estar desatualizados e mostra a hora da última coleta.
          </p>
        </div>
      </li>

      <li class="cartao flex flex-col items-start gap-2 sm:flex-row sm:gap-5">
        <span class="icone flex-none text-[36px] text-destaque-forte" aria-hidden="true">edit_note</span>
        <div>
          <h2 class="serifa">2. O sistema escreve um rascunho</h2>
          <p>
            Quando acontece um fato (uma votação, uma mudança na situação de uma proposta, um projeto novo), o sistema monta um rascunho
            com <strong>frases prontas preenchidas só com os dados oficiais</strong>. Ele nunca inventa número, nome ou data.
          </p>
          <p>
            Para juntar os dados ligados ao fato, usamos uma busca que combina as palavras do texto com uma rede neural que compara o sentido das frases.
            Tudo roda nos nossos computadores, com programas de código aberto, sem serviço pago de inteligência artificial.
          </p>
        </div>
      </li>

      <li class="cartao flex flex-col items-start gap-2 sm:flex-row sm:gap-5">
        <span class="icone flex-none text-[36px] text-destaque-forte" aria-hidden="true">fact_check</span>
        <div>
          <h2 class="serifa">3. A notícia é conferida antes de sair</h2>
          <p>
            Todo rascunho passa pela <strong>planta da notícia</strong>: uma lista de regras que confere se o texto tem todas as partes,
            se o título diz de qual proposta se trata, se as siglas estão explicadas e se não há palavra de opinião.
            Também confere se os dados da Câmara vieram com alguma falha grave.
            O que falha em qualquer regra vai para a revisão da equipe, que pode corrigir, publicar ou rejeitar.
            Cada notícia guarda o histórico de quem mexeu e quando.
          </p>
        </div>
      </li>

      <li class="cartao flex flex-col items-start gap-2 sm:flex-row sm:gap-5">
        <span class="icone flex-none text-[36px] text-destaque-forte" aria-hidden="true">update</span>
        <div>
          <h2 class="serifa">4. Uma notícia por proposta, sempre atualizada</h2>
          <p>
            Cada proposta tem uma notícia só. O fato que a abriu fica no topo e o título não muda. Quando acontece algo novo
            (o projeto foi votado, mudou de comissão, foi para o Senado), o fato entra na parte <strong>Atualizações</strong> da mesma notícia,
            com a data. Assim você acompanha a história inteira num lugar só.
          </p>
        </div>
      </li>
    </ol>

    <section class="cartao" aria-labelledby="t-planta">
      <h2 id="t-planta" class="serifa mb-4!">As partes de toda notícia</h2>
      <dl class="m-0 grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        <div v-for="s in SECOES_DA_NOTICIA" :key="s.titulo" class="border-l-[3px] border-marca pl-3">
          <dt class="font-bold">{{ s.titulo }}</dt>
          <dd class="m-0 mt-1 leading-normal text-texto-2">{{ s.texto }}</dd>
        </div>
      </dl>
    </section>

    <section class="cartao flex flex-col items-start gap-2 border-l-4 border-destaque-forte sm:flex-row sm:gap-5" aria-labelledby="t-lacunas">
      <span class="icone flex-none text-[36px] text-destaque-forte" aria-hidden="true">help</span>
      <div>
        <h2 id="t-lacunas" class="serifa">Quando a Câmara não informa</h2>
        <p>
          A API da Câmara às vezes deixa campos vazios: uma proposta sem tema, uma votação só com o placar, uma situação em branco.
          Nós <strong>não preenchemos a lacuna com suposições</strong>. A notícia diz o que faltou, mostra onde conferimos e dá o link
          da ficha oficial da proposta, para você ver com os próprios olhos.
        </p>
        <p>
          Um exemplo: a Câmara demora a classificar os projetos novos por tema. Esses projetos aparecem no tema
          <RouterLink :to="{ name: 'tema', params: { cod: 0 } }">"Sem tema informado pela Câmara"</RouterLink> até ela classificar.
        </p>
      </div>
    </section>

    <section class="cartao" aria-labelledby="t-confira">
      <h2 id="t-confira" class="serifa">Confira você mesmo</h2>
      <ul class="m-0 flex list-none flex-col gap-2.5 p-0 text-[17px] leading-[1.55]">
        <li class="flex items-start gap-2.5"><span class="icone text-link" aria-hidden="true">link</span><span>Toda notícia tem o link da <strong>fonte oficial</strong> na Câmara e do texto completo da proposta.</span></li>
        <li class="flex items-start gap-2.5"><span class="icone text-link" aria-hidden="true">info</span><span>No fim de cada notícia, a parte <strong>"Como esta notícia foi feita"</strong> mostra os dados usados e como ela foi conferida.</span></li>
        <li class="flex items-start gap-2.5"><span class="icone text-link" aria-hidden="true">how_to_vote</span><span>Nas votações nominais, você vê o voto de cada deputado e a orientação de cada partido.</span></li>
      </ul>
    </section>

    <section class="cartao" aria-labelledby="t-nao">
      <h2 id="t-nao" class="serifa">O que o Desperta Brasil não faz</h2>
      <ul class="m-0 flex list-none flex-col gap-2.5 p-0 text-[17px] leading-[1.55] [&_li]:relative [&_li]:pl-5 [&_li]:before:absolute [&_li]:before:left-0 [&_li]:before:text-destaque [&_li]:before:content-['—']">
        <li>Não tem propaganda.</li>
        <li>Não pede cadastro nem dados pessoais para ler.</li>
        <li>Não dá opinião: conta o fato, de forma imparcial, e mostra a fonte.</li>
        <li>Não cobre ainda o Senado, o STF nem as assembleias estaduais. Por enquanto, só a Câmara dos Deputados.</li>
      </ul>
    </section>
  </div>
</template>
