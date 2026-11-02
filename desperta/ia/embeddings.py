import hashlib
import os
import shutil

LIMITE_TOKENS = 512
TAMANHO_LOTE = 16
# Decisao 21.2: sem estes o modelo nao carrega sem internet; o tokenizador pode vir em tokenizer.json ou nos dois outros
ARQUIVOS_DO_MODELO = ("config.json", "model.safetensors", "tokenizer_config.json")
ARQUIVOS_DO_TOKENIZADOR = (("tokenizer.json",), ("vocab.json", "merges.txt"))
PREFERENCIAS_DE_DISPOSITIVO = ("auto", "cuda", "cpu")


class RobertaAusente(Exception):
    """A pasta da RoBERTaLexPT nao existe ou esta incompleta (decisao 21.3)."""


class DispositivoIndisponivel(Exception):
    """IA_DISPOSITIVO=cuda, mas a placa nao aparece (decisao 20.2)."""


def caminho_no_projeto(app, caminho):
    """Caminho relativo vale a partir da raiz do projeto; nenhum caminho do PC fica no codigo (21.4)."""
    return os.path.join(os.path.dirname(app.instance_path), caminho)


def preparar_ambiente(app, offline=None):
    """Vale antes de importar o transformers, que le esta variavel ao carregar."""
    os.environ["HF_HUB_OFFLINE"] = app.config["HF_HUB_OFFLINE"] if offline is None else ("1" if offline else "0")


def arquivos_faltando(pasta):
    """Vazio se a pasta tem o modelo inteiro, com pesos, configuracao e tokenizador."""
    faltando = [nome for nome in ARQUIVOS_DO_MODELO if not os.path.isfile(os.path.join(pasta, nome))]
    if not any(all(os.path.isfile(os.path.join(pasta, nome)) for nome in opcao) for opcao in ARQUIVOS_DO_TOKENIZADOR):
        faltando.append("tokenizer.json")
    return faltando


def tamanho_em_mb(pasta):
    caminhos = (os.path.join(pasta, nome) for nome in os.listdir(pasta))
    return sum(os.path.getsize(caminho) for caminho in caminhos if os.path.isfile(caminho)) // 1_000_000


def salvar_modelo(nome, pasta, cache_dir):
    """Salva em pasta simples, sem os links do cache do Hugging Face, que pendrive em exFAT ou FAT32 nao aceita."""
    from transformers import AutoModelForMaskedLM, AutoTokenizer
    from transformers.utils import logging

    logging.set_verbosity_error()
    tokenizador = AutoTokenizer.from_pretrained(nome, cache_dir=cache_dir)
    # MaskedLM guarda tambem a cabeca de preenchimento: o modelo fica inteiro, como foi publicado
    modelo = AutoModelForMaskedLM.from_pretrained(nome, cache_dir=cache_dir)
    os.makedirs(pasta, exist_ok=True)
    tokenizador.save_pretrained(pasta)
    modelo.save_pretrained(pasta)


def _hash_do_arquivo(caminho):
    resumo = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def copiar_modelo(origem, destino):
    """Copia e confere byte a byte; a origem nao e apagada: isso e decisao do Lucas (21.2)."""
    os.makedirs(destino, exist_ok=True)
    if os.listdir(destino):
        raise ValueError(f"A pasta {destino} nao esta vazia.")
    nomes = sorted(nome for nome in os.listdir(origem) if os.path.isfile(os.path.join(origem, nome)))
    for nome in nomes:
        # copyfile nao tenta copiar permissoes, que exFAT e FAT32 nao guardam
        shutil.copyfile(os.path.join(origem, nome), os.path.join(destino, nome))
        if _hash_do_arquivo(os.path.join(origem, nome)) != _hash_do_arquivo(os.path.join(destino, nome)):
            raise ValueError(f"A copia de {nome} ficou diferente do original.")
    return nomes


def escolher_dispositivo(preferencia):
    """Decisao 20.2: auto usa a placa se existir; cuda exige a placa; cpu nunca a usa."""
    if preferencia not in PREFERENCIAS_DE_DISPOSITIVO:
        raise ValueError(f"IA_DISPOSITIVO desconhecido: {preferencia}")
    if preferencia == "cpu":
        return "cpu"

    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    if preferencia == "cuda":
        raise DispositivoIndisponivel("IA_DISPOSITIVO=cuda, mas o CUDA nao esta disponivel.")
    return "cpu"


def nome_do_dispositivo(dispositivo):
    if dispositivo == "cpu":
        return "cpu"

    import torch

    return f"{dispositivo} ({torch.cuda.get_device_name(0)})"


# === ModeloEmbedding (RoBERTaLexPT original: so faz embeddings, nao gera texto) ===
class ModeloEmbedding:
    """
    Carregado uma vez pelo modulo de IA, em segundo plano.
    torch e transformers ficam dentro dos metodos: a API Flask nao carrega o modelo.
    """

    def __init__(self, nome, pasta=None, tokenizador=None, modelo=None, dispositivo="cpu"):
        self.nome = nome
        self.pasta = pasta
        self.tokenizador = tokenizador
        self.modelo = modelo
        self.dispositivo = dispositivo
        if tokenizador is None or modelo is None:
            self._carregar()

    def _carregar(self):
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging

        # O relatorio de pesos do modelo so fala da camada de pooler, que nao e usada aqui
        logging.set_verbosity_error()
        self.tokenizador = AutoTokenizer.from_pretrained(self.pasta, local_files_only=True)
        self.modelo = AutoModel.from_pretrained(self.pasta, local_files_only=True).to(self.dispositivo)
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
        entrada = {nome: tensor.to(self.dispositivo) for nome, tensor in entrada.items()}
        with torch.no_grad():
            saida = self.modelo(**entrada).last_hidden_state
        # Mean pooling com a mascara de atencao + normalizacao L2
        mascara = entrada["attention_mask"].unsqueeze(-1).float()
        media = (saida * mascara).sum(dim=1) / mascara.sum(dim=1).clamp(min=1e-9)
        normalizados = torch.nn.functional.normalize(media, p=2, dim=1)
        return [numpy.float32(vetor).tobytes() for vetor in normalizados.cpu().numpy()]
