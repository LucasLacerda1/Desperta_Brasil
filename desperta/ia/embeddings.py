LIMITE_TOKENS = 512
TAMANHO_LOTE = 16


# === ModeloEmbedding (RoBERTaLexPT: so faz embeddings, nao gera texto) ===
class ModeloEmbedding:
    """
    Carregado uma vez pelo modulo de IA, em segundo plano, e na CPU.
    torch e transformers ficam dentro dos metodos: a API Flask nao carrega o modelo.
    """

    def __init__(self, nome, tokenizador=None, modelo=None):
        self.nome = nome
        self.tokenizador = tokenizador
        self.modelo = modelo
        if tokenizador is None or modelo is None:
            self._carregar()

    def _carregar(self):
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging

        # O relatorio de pesos do modelo so fala da camada de pooler, que nao e usada aqui
        logging.set_verbosity_error()
        self.tokenizador = AutoTokenizer.from_pretrained(self.nome)
        self.modelo = AutoModel.from_pretrained(self.nome)
        self.modelo.eval()

    def dividir(self, texto, max_tokens, sobreposicao):
        """Devolve (texto, tokens) de cada trecho; texto curto fica num trecho so."""
        ids = self.tokenizador.encode(texto, add_special_tokens=False)
        if len(ids) <= max_tokens:
            return [(texto, len(ids))]
        trechos = []
        passo = max_tokens - sobreposicao
        for inicio in range(0, len(ids), passo):
            fim = inicio + max_tokens
            pedaco = ids[inicio:fim]
            trechos.append((self.tokenizador.decode(pedaco, skip_special_tokens=True), len(pedaco)))
            if fim >= len(ids):
                break
        return trechos

    def embutir(self, textos):
        """Devolve um embedding por texto, na mesma ordem: 768 float32 = 3.072 bytes."""
        # Textos de tamanho parecido no mesmo lote gastam menos com preenchimento
        ordem = sorted(range(len(textos)), key=lambda posicao: len(textos[posicao]))
        resultado = [None] * len(textos)
        for inicio in range(0, len(ordem), TAMANHO_LOTE):
            fim = inicio + TAMANHO_LOTE
            posicoes = ordem[inicio:fim]
            vetores = self._embutir_lote([textos[posicao] for posicao in posicoes])
            for posicao, vetor in zip(posicoes, vetores):
                resultado[posicao] = vetor
        return resultado

    def _embutir_lote(self, textos):
        import numpy
        import torch

        entrada = self.tokenizador(textos, padding=True, truncation=True, max_length=LIMITE_TOKENS, return_tensors="pt")
        with torch.no_grad():
            saida = self.modelo(**entrada).last_hidden_state
        # Mean pooling com a mascara de atencao + normalizacao L2
        mascara = entrada["attention_mask"].unsqueeze(-1).float()
        media = (saida * mascara).sum(dim=1) / mascara.sum(dim=1).clamp(min=1e-9)
        normalizados = torch.nn.functional.normalize(media, p=2, dim=1)
        return [numpy.float32(vetor).tobytes() for vetor in normalizados.numpy()]
