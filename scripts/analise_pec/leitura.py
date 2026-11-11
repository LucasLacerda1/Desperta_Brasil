"""
Leitura da PEC pela RoBERTaLexPT original, sem treino (docs/LEITURA_ENCADEADA.md).

Fora do pacote desperta: e um estudo e nao muda nada no portal. Nao treina nada.
"""

import re
from dataclasses import dataclass, field

import numpy

# Decisao 1: metade dos 512 tokens para o contexto e metade para o pedaco
# (1 <s> + 254 + 2 </s></s> + 254 + 1 </s> = 512)
METADE = 254
INICIO, FIM = 0, 2
TAMANHO_LOTE = 16
PALAVRAS_POR_PEDACO = 3
PALAVRAS_NA_MEMORIA = 5

# Palavras sem conteudo proprio: ficam fora do peso das palavras (testes E e memoria)
PALAVRAS_VAZIAS = set(
    """a o as os um uma uns umas de da do das dos e em no na nos nas que por para com sem se ao aos à às ou como
    mais é são foi ser seu sua seus suas pelo pela pelos pelas este esta estes estas esse essa esses essas isso
    nesse nessa desse dessa deste desta onde até também entre sobre já não nº art arts lhe lhes ter tem têm sido
    bem todos todas todo toda seja ainda mesmo quando qual cuja cujo cujas cujos""".split()
)
PALAVRA = re.compile(r"\w+(?:-\w+)*")


def normalizar(vetor):
    norma = numpy.linalg.norm(vetor)
    return vetor / norma if norma else vetor


def media(estados):
    """Mean pooling dos estados dos tokens + normalizacao L2, como no portal (embeddings.py)."""
    return normalizar(numpy.asarray(estados, dtype=numpy.float64).mean(axis=0))


def cosseno(a, b):
    return float(numpy.dot(a, b))


def palavras_de(texto):
    """(palavra em minusculas, inicio, fim) das palavras com conteudo."""
    return [
        (m.group(0).lower(), m.start(), m.end())
        for m in PALAVRA.finditer(texto)
        if len(m.group(0)) >= 3 and m.group(0).lower() not in PALAVRAS_VAZIAS
    ]


def sem_a_palavra(texto, inicio, fim):
    novo = texto[:inicio] + texto[fim:]
    novo = re.sub(r"\s{2,}", " ", novo)
    return re.sub(r"\s+([,.;:)])", r"\1", novo).strip()


# === Leitor (a RoBERTaLexPT carregada uma vez) ===
class Leitor:
    def __init__(self, pasta, dispositivo):
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer
        from transformers.utils import logging

        logging.set_verbosity_error()
        self.torch = torch
        self.tokenizador = AutoTokenizer.from_pretrained(pasta, local_files_only=True)
        # Com a cabeca de lacunas (teste E); os vetores saem do encoder, sem calcular as 50 mil notas por token
        self.modelo = AutoModelForMaskedLM.from_pretrained(pasta, local_files_only=True).to(dispositivo).eval()
        self.dispositivo = dispositivo
        self.leituras = 0
        # Camadas de onde sai o vetor: None = so a ultima; senao, a media das camadas pedidas (1 a 12)
        self.camadas = None
        # Ajuste aplicado aos vetores na hora de comparar (por exemplo, o Whitening); None = nenhum
        self.transformar = None

    def modo_dropout(self, ligado):
        """Dropout ligado: cada leitura desliga ao acaso 10% das ligacoes (o mesmo texto da vetores diferentes)."""
        self.modelo.train() if ligado else self.modelo.eval()

    # --------------------------------------------------
    # TOKENS
    # --------------------------------------------------
    def ids(self, texto, espaco_antes=False):
        return self.tokenizador.encode((" " + texto) if espaco_antes else texto, add_special_tokens=False)

    def tokenizar_frases(self, frases):
        """
        Tokens do pedaco e o intervalo de cada frase. As frases juntas com um espaco formam o pedaco,
        e o BPE em bytes corta nos espacos: juntar os tokens de cada frase da o mesmo que tokenizar o pedaco.
        """
        ids, intervalos = [], []
        for posicao, (codigo, texto) in enumerate(frases):
            tokens = self.ids(texto, espaco_antes=posicao > 0)
            intervalos.append((codigo, len(ids), len(ids) + len(tokens)))
            ids.extend(tokens)
        return ids, intervalos

    def _entrada(self, contexto, texto):
        prefixo = [INICIO] + contexto + [FIM, FIM] if contexto else [INICIO]
        return prefixo + texto + [FIM], len(prefixo)

    # --------------------------------------------------
    # LEITURA
    # --------------------------------------------------
    def ler(self, entradas):
        """entradas: lista de (ids do contexto, ids do texto). Devolve os estados de cada token do texto."""
        torch = self.torch
        resultado = []
        for inicio in range(0, len(entradas), TAMANHO_LOTE):
            fim = inicio + TAMANHO_LOTE
            lote = entradas[inicio:fim]
            montadas = [self._entrada(contexto, texto) for contexto, texto in lote]
            maior = max(len(sequencia) for sequencia, _ in montadas)
            ids = torch.full((len(lote), maior), self.tokenizador.pad_token_id, dtype=torch.long)
            mascara = torch.zeros_like(ids)
            for linha, (sequencia, _) in enumerate(montadas):
                ids[linha, : len(sequencia)] = torch.tensor(sequencia)
                mascara[linha, : len(sequencia)] = 1
            with torch.no_grad():
                saida = self.modelo.roberta(
                    input_ids=ids.to(self.dispositivo),
                    attention_mask=mascara.to(self.dispositivo),
                    output_hidden_states=self.camadas is not None,
                )
            if self.camadas is None:
                estados = saida.last_hidden_state
            else:
                estados = torch.stack([saida.hidden_states[c] for c in self.camadas]).mean(dim=0)
            estados = estados.float().cpu().numpy()
            for linha, ((_, texto), (_, comeco)) in enumerate(zip(lote, montadas)):
                ultimo = comeco + len(texto)
                resultado.append(estados[linha, comeco:ultimo])
            self.leituras += len(lote)
        return resultado

    def vetores(self, textos):
        """Cada texto lido sozinho: um vetor por texto."""
        vetores = [media(estados) for estados in self.ler([([], self.ids(texto)[: 2 * METADE]) for texto in textos])]
        return [self.ajustar(v) for v in vetores]

    def ajustar(self, vetor):
        """Aplica o ajuste das comparacoes (whitening), se houver; sem ajuste, devolve o vetor como esta."""
        return self.transformar(vetor) if self.transformar else vetor

    def palpites(self, contexto, texto_ids, posicao, quantos=5):
        """Os tokens mais provaveis para a lacuna em texto_ids[posicao]."""
        torch = self.torch
        sequencia, comeco = self._entrada(contexto, texto_ids)
        with torch.no_grad():
            estados = self.modelo.roberta(
                input_ids=torch.tensor([sequencia], device=self.dispositivo)
            ).last_hidden_state
            notas = self.modelo.lm_head(estados[0, comeco + posicao])
        self.leituras += 1
        return notas.topk(quantos).indices.tolist()

    def surpresas(self, contexto, texto):
        """
        Quao dificil e adivinhar cada palavra escondida: -log da probabilidade de cada token da palavra,
        escondendo um token de cada vez, com o mesmo contexto (media dos tokens; maior valor entre as
        ocorrencias). Usa a cabeca de lacunas sobre a ultima camada.
        """
        torch = self.torch
        codificado = self.tokenizador(texto, return_offsets_mapping=True, add_special_tokens=False)
        ids, posicoes = codificado["input_ids"][:METADE], codificado["offset_mapping"][:METADE]
        ocorrencias = []
        for palavra, inicio, fim in palavras_de(texto):
            tokens = [i for i, (a, b) in enumerate(posicoes) if a < fim and b > inicio]
            if tokens:
                ocorrencias.append((palavra, tokens))
        pedidos = [(o, t) for o, (_, tokens) in enumerate(ocorrencias) for t in tokens]
        notas = [0.0] * len(pedidos)
        mascara_id = self.tokenizador.mask_token_id
        for inicio in range(0, len(pedidos), TAMANHO_LOTE):
            fim = inicio + TAMANHO_LOTE
            lote = pedidos[inicio:fim]
            montadas = []
            for _, token in lote:
                variante = list(ids)
                variante[token] = mascara_id
                montadas.append(self._entrada(contexto, variante))
            maior = max(len(seq) for seq, _ in montadas)
            entrada = torch.full((len(lote), maior), self.tokenizador.pad_token_id, dtype=torch.long)
            atencao = torch.zeros_like(entrada)
            for linha, (seq, _) in enumerate(montadas):
                entrada[linha, : len(seq)] = torch.tensor(seq)
                atencao[linha, : len(seq)] = 1
            with torch.no_grad():
                estados = self.modelo.roberta(
                    input_ids=entrada.to(self.dispositivo), attention_mask=atencao.to(self.dispositivo)
                ).last_hidden_state
                linhas = torch.arange(len(lote))
                colunas = torch.tensor([comeco + token for (_, token), (_, comeco) in zip(lote, montadas)])
                logp = torch.log_softmax(self.modelo.lm_head(estados[linhas, colunas]), dim=-1)
                originais = torch.tensor([ids[token] for _, token in lote], device=logp.device)
                valores = (-logp[linhas, originais]).float().cpu().tolist()
            for posicao, valor in enumerate(valores):
                notas[inicio + posicao] = valor
            self.leituras += len(lote)
        por_ocorrencia = {}
        for (ocorrencia, _), valor in zip(pedidos, notas):
            por_ocorrencia.setdefault(ocorrencia, []).append(valor)
        resultado = {}
        for ocorrencia, valores in por_ocorrencia.items():
            palavra = ocorrencias[ocorrencia][0]
            resultado[palavra] = max(resultado.get(palavra, 0.0), sum(valores) / len(valores))
        return resultado

    def pesos_das_palavras(self, contexto, texto, vetor_original):
        """
        Quanto o vetor do texto muda quando cada palavra sai (relendo com o mesmo contexto).
        Num texto curto, tirar qualquer palavra muda muito a media; por isso o peso e multiplicado pelo
        numero de tokens do texto, para comparar palavras de textos de tamanhos diferentes. Dentro de um
        mesmo texto, a ordem das palavras nao muda.
        """
        ocorrencias = palavras_de(texto)
        tamanho = len(self.ids(texto))
        variantes = [self.ids(sem_a_palavra(texto, inicio, fim))[:METADE] for _, inicio, fim in ocorrencias]
        estados = self.ler([(contexto, ids) for ids in variantes])
        pesos = {}
        for (palavra, _, _), estado in zip(ocorrencias, estados):
            peso = (1.0 - cosseno(media(estado), vetor_original)) * tamanho
            pesos[palavra] = max(pesos.get(palavra, 0.0), peso)
        return pesos


# ======================================================
# LEITURA COM AS FRASES SOZINHAS (rodada base)
# ======================================================
def ler_frases_soltas(leitor, frases):
    """Cada frase lida sozinha. Vetor da PEC = media dos vetores das frases."""
    codigos = [codigo for codigo, _ in frases]
    ids = [leitor.ids(texto)[: 2 * METADE] for _, texto in frases]
    estados = leitor.ler([([], i) for i in ids])
    vetor_frase = {codigo: media(estado) for codigo, estado in zip(codigos, estados)}
    pesos = {}
    for codigo, texto in frases:
        for palavra, peso in leitor.pesos_das_palavras([], texto, vetor_frase[codigo]).items():
            pesos[palavra] = max(pesos.get(palavra, 0.0), peso)
    contexto_da_frase = {codigo: [] for codigo in codigos}
    return Leitura(
        vetor_frase=vetor_frase,
        vetor_pec=media(list(vetor_frase.values())),
        pesos_palavras=pesos,
        contexto_da_frase=contexto_da_frase,
    )


def ler_frases_votacao(leitor, frases, leituras, por_vez=50):
    """
    A PEC lida `leituras` vezes com o dropout ligado (frase por frase): o vetor de cada frase e a media dos
    seus vetores nas leituras. Sem treino: os pesos nao mudam; a votacao so tira a media das duvidas da rede.
    Os pesos das palavras e as lacunas (teste E) vem da leitura normal, sem dropout.
    """
    normal = ler_frases_soltas(leitor, frases)
    ids = [leitor.ids(texto)[: 2 * METADE] for _, texto in frases]
    somas = numpy.zeros((len(frases), len(next(iter(normal.vetor_frase.values())))))
    leitor.modo_dropout(True)
    try:
        feitas = 0
        while feitas < leituras:
            vezes = min(por_vez, leituras - feitas)
            estados = leitor.ler([([], i) for _ in range(vezes) for i in ids])
            for posicao, estado in enumerate(estados):
                somas[posicao % len(frases)] += media(estado)
            feitas += vezes
    finally:
        leitor.modo_dropout(False)
    vetor_frase = {codigo: normalizar(soma) for (codigo, _), soma in zip(frases, somas)}
    return Leitura(
        vetor_frase=vetor_frase,
        vetor_pec=media(list(vetor_frase.values())),
        pesos_palavras=normal.pesos_palavras,
        contexto_da_frase=normal.contexto_da_frase,
    )


# === Whitening (ajuste dos vetores, sem treino) ===
class Whitening:
    """
    Su et al. (2021): tira a media e iguala o peso de todas as direcoes dos vetores, calculado uma vez sobre
    muitos textos do mesmo tipo (aqui, os trechos do RAG). Nao muda a Roberta: so os numeros que saem dela.
    """

    def __init__(self, amostra):
        amostra = numpy.asarray(amostra, dtype=numpy.float64)
        self.media = amostra.mean(axis=0)
        direcoes, variancias, _ = numpy.linalg.svd(numpy.cov((amostra - self.media).T))
        self.matriz = direcoes / numpy.sqrt(numpy.maximum(variancias, 1e-12))

    def __call__(self, vetor):
        return normalizar((numpy.asarray(vetor, dtype=numpy.float64) - self.media) @ self.matriz)


def ajustar_leitura(lida, transformar):
    """A mesma leitura com os vetores das frases ajustados; o vetor da PEC e refeito com eles."""
    vetor_frase = {codigo: transformar(v) for codigo, v in lida.vetor_frase.items()}
    return Leitura(
        vetor_frase=vetor_frase,
        vetor_pec=media(list(vetor_frase.values())),
        pesos_palavras=lida.pesos_palavras,
        contexto_da_frase=lida.contexto_da_frase,
        por_pedaco=lida.por_pedaco,
    )


# === Leitura (o que sai de uma leitura da PEC) ===
@dataclass
class Leitura:
    vetor_frase: dict
    vetor_pec: numpy.ndarray
    pesos_palavras: dict
    # Para o teste E: com que contexto cada frase foi lida
    contexto_da_frase: dict
    por_pedaco: list = field(default_factory=list)


# ======================================================
# LEITURA ENCADEADA
# ======================================================
@dataclass
class Memoria:
    """As interpretacoes da Roberta levadas de um pedaco para o outro, em texto."""

    frases: list = field(default_factory=list)  # (codigo, texto, vetor)
    palavras: dict = field(default_factory=dict)  # palavra -> peso

    def texto(self):
        partes = [texto for _, texto, _ in self.frases]
        if self.palavras:
            melhores = sorted(self.palavras, key=lambda p: -self.palavras[p])[:PALAVRAS_NA_MEMORIA]
            partes.append("Palavras: " + ", ".join(melhores) + ".")
        return " ".join(partes)


def montar_contexto(leitor, prefixo, memoria, acumulado):
    """
    Prefixo (bloco da planta e contexto inicial) + memoria, em ate METADE tokens. Quando falta espaco,
    sai a frase da memoria mais longe do vetor acumulado; o prefixo nunca sai. Uma frase sozinha que
    ainda nao cabe e cortada no fim.
    """
    ids_prefixo = leitor.ids(prefixo) if prefixo else []
    espaco = METADE - len(ids_prefixo)
    saiu = []
    while True:
        texto = memoria.texto()
        ids_memoria = leitor.ids(texto, espaco_antes=bool(prefixo)) if texto else []
        if len(ids_memoria) <= espaco or len(memoria.frases) <= 1 or acumulado is None:
            break
        mais_longe = min(memoria.frases, key=lambda frase: cosseno(frase[2], acumulado))
        memoria.frases.remove(mais_longe)
        saiu.append(mais_longe[0])
    ids_memoria = ids_memoria[: max(espaco, 0)]
    return (ids_prefixo + ids_memoria)[:METADE], saiu


def ler_encadeada(leitor, pedacos, prefixo_do_pedaco, sorteio=None):
    """
    pedacos: lista de pedacos, cada um uma lista de (codigo, texto) das suas frases.
    prefixo_do_pedaco(i): o texto fixo antes da memoria (bloco da planta e contexto inicial).
    sorteio: um random.Random para a rodada de controle (memoria com frases e palavras sorteadas).
    """
    memoria = Memoria()
    vetores_pedaco, vetor_frase, pesos_todos, contexto_da_frase, tabela = [], {}, {}, {}, []
    lidas = []
    for numero, frases in enumerate(pedacos):
        acumulado = media(vetores_pedaco) if vetores_pedaco else None
        contexto, saiu = montar_contexto(leitor, prefixo_do_pedaco(numero), memoria, acumulado)
        ids, intervalos = leitor.tokenizar_frases(frases)
        texto = " ".join(t for _, t in frases)

        # Decisao 4: pedaco maior que a metade e cortado onde cair; o resto e a leitura seguinte
        estados = []
        for inicio in range(0, len(ids), METADE):
            fim = inicio + METADE
            estados.extend(leitor.ler([(contexto, ids[inicio:fim])])[0])
        estados = numpy.asarray(estados)
        vetor = media(estados)
        for codigo, inicio, fim in intervalos:
            vetor_frase[codigo] = media(estados[inicio:fim])
            contexto_da_frase[codigo] = contexto

        pesos = leitor.pesos_das_palavras(contexto, texto, vetor)
        for palavra, peso in pesos.items():
            pesos_todos[palavra] = max(pesos_todos.get(palavra, 0.0), peso)
        lidas.extend(frases)

        if sorteio is None:
            escolhida = max(frases, key=lambda frase: cosseno(vetor_frase[frase[0]], vetor))
            palavras = sorted(pesos, key=lambda p: -pesos[p])[:PALAVRAS_POR_PEDACO]
        else:
            escolhida = sorteio.choice(lidas)
            palavras = sorteio.sample(sorted(pesos), min(PALAVRAS_POR_PEDACO, len(pesos)))
        memoria.frases.append((escolhida[0], escolhida[1], vetor_frase[escolhida[0]]))
        for palavra in palavras:
            memoria.palavras[palavra] = max(memoria.palavras.get(palavra, 0.0), pesos.get(palavra, 0.0))
        vetores_pedaco.append(vetor)
        tabela.append(
            {
                "pedaco": numero + 1,
                "contexto": leitor.tokenizador.decode(contexto),
                "tokens_contexto": len(contexto),
                "tokens_pedaco": len(ids),
                "saiu_da_memoria": saiu,
                "frase_escolhida": escolhida[0],
                "palavras": palavras,
            }
        )
    return Leitura(
        vetor_frase=vetor_frase,
        vetor_pec=media(vetores_pedaco),
        pesos_palavras=pesos_todos,
        contexto_da_frase=contexto_da_frase,
        por_pedaco=tabela,
    )
