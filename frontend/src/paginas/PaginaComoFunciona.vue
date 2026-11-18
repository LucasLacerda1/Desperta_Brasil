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
  <div class="conteudo pagina">
    <header class="abertura">
      <p class="sobretitulo">Transparência</p>
      <h1 class="serifa">Como o Desperta Brasil funciona</h1>
      <p class="lide">
        Acompanhamos a Câmara dos Deputados e contamos, em linguagem simples, o que foi votado, o que foi apresentado e em que pé está cada proposta.
        Esta página explica de onde vêm os dados, como cada notícia é escrita e o que fazemos quando falta alguma informação.
      </p>
    </header>

    <ol class="etapas">
      <li class="cartao">
        <span class="icone grande" aria-hidden="true">cloud_download</span>
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

      <li class="cartao">
        <span class="icone grande" aria-hidden="true">edit_note</span>
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

      <li class="cartao">
        <span class="icone grande" aria-hidden="true">fact_check</span>
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

      <li class="cartao">
        <span class="icone grande" aria-hidden="true">update</span>
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

    <section class="cartao planta" aria-labelledby="t-planta">
      <h2 id="t-planta" class="serifa">As partes de toda notícia</h2>
      <dl class="secoes">
        <div v-for="s in SECOES_DA_NOTICIA" :key="s.titulo">
          <dt>{{ s.titulo }}</dt>
          <dd>{{ s.texto }}</dd>
        </div>
      </dl>
    </section>

    <section class="cartao lacunas" aria-labelledby="t-lacunas">
      <span class="icone grande" aria-hidden="true">help</span>
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
      <ul class="lista-confira">
        <li><span class="icone" aria-hidden="true">link</span>Toda notícia tem o link da <strong>fonte oficial</strong> na Câmara e do texto completo da proposta.</li>
        <li><span class="icone" aria-hidden="true">info</span>No fim de cada notícia, a parte <strong>"Como esta notícia foi feita"</strong> mostra os dados usados e como ela foi conferida.</li>
        <li><span class="icone" aria-hidden="true">how_to_vote</span>Nas votações nominais, você vê o voto de cada deputado e a orientação de cada partido.</li>
      </ul>
    </section>

    <section class="cartao" aria-labelledby="t-nao">
      <h2 id="t-nao" class="serifa">O que o Desperta Brasil não faz</h2>
      <ul class="lista-nao">
        <li>Não tem propaganda.</li>
        <li>Não pede cadastro nem dados pessoais para ler.</li>
        <li>Não dá opinião: conta o fato, de forma imparcial, e mostra a fonte.</li>
        <li>Não cobre ainda o Senado, o STF nem as assembleias estaduais. Por enquanto, só a Câmara dos Deputados.</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.pagina { display: flex; flex-direction: column; gap: 24px; padding-block: 24px 0; max-width: 900px; }
.abertura { display: flex; flex-direction: column; gap: 12px; }
.sobretitulo { margin: 0; font-size: 14px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: var(--destaque); }
h1 { margin: 0; font-size: clamp(30px, 4.4vw, 44px); }
.lide { margin: 0; font-size: 19px; line-height: 1.6; color: var(--texto-2); }

.etapas { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 16px; }
.etapas li, .lacunas { display: flex; gap: 20px; align-items: flex-start; }
.grande { font-size: 36px; color: var(--destaque-forte); flex: none; }
h2 { margin: 0 0 8px; font-size: 22px; }
p { margin: 0 0 10px; line-height: 1.65; font-size: 17px; }
p:last-child { margin-bottom: 0; }

.planta h2 { margin-bottom: 16px; }
.secoes { margin: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px 24px; }
.secoes div { border-left: 3px solid var(--marca); padding-left: 12px; }
dt { font-weight: 700; }
dd { margin: 4px 0 0; color: var(--texto-2); line-height: 1.5; }

.lacunas { border-left: 4px solid var(--destaque-forte); }

.lista-confira, .lista-nao { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; font-size: 17px; line-height: 1.55; }
.lista-confira li { display: flex; gap: 10px; align-items: flex-start; }
.lista-confira .icone { color: var(--link); }
.lista-nao li { padding-left: 20px; position: relative; }
.lista-nao li::before { content: '—'; position: absolute; left: 0; color: var(--destaque); }

@media (max-width: 560px) {
  .etapas li, .lacunas { flex-direction: column; gap: 8px; }
}
</style>
