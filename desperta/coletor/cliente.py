import time

import requests

STATUS_REPETIR = {429, 500, 502, 503, 504}
ESPERAS_PADRAO = (2, 4, 8, 16)


class ErroAPI(Exception):
    """A API nao respondeu com sucesso, mesmo depois das novas tentativas."""

    def __init__(self, url, mensagem, status=None):
        super().__init__(f"{url}: {mensagem}")
        self.url = url
        self.status = status


class TempoEsgotado(Exception):
    """O orcamento de tempo da rotina acabou. Nao e falha da API: o resto fica para a proxima coleta."""


# === ClienteCamara (chamadas HTTP com novas tentativas e paginacao) ===
class ClienteCamara:
    def __init__(
        self, url_base, timeout=30, esperas=ESPERAS_PADRAO, sessao=None, dormir=time.sleep, relogio=time.monotonic
    ):
        self.url_base = url_base.rstrip("/")
        self.timeout = timeout
        self.esperas = esperas
        self.sessao = sessao or requests.Session()
        self.dormir = dormir
        self.relogio = relogio
        self.prazo = None
        # Contadores gravados em coleta.requisicoes e coleta.erros_http
        self.requisicoes = 0
        self.erros_http = 0

    def definir_orcamento(self, segundos):
        """A partir daqui, nenhuma chamada comeca depois de passar esse tempo; None tira o limite."""
        self.prazo = None if segundos is None else self.relogio() + segundos

    def _conferir_orcamento(self):
        if self.prazo is not None and self.relogio() >= self.prazo:
            raise TempoEsgotado("Orcamento de tempo esgotado: o resto fica para a proxima coleta")

    def _chamar(self, url, params=None):
        """Faz a chamada e devolve o JSON; repete em 429, 5xx, timeout e queda de conexao."""
        ultimo_erro = None
        status = None
        for tentativa in range(len(self.esperas) + 1):
            if tentativa:
                self.dormir(self.esperas[tentativa - 1])
            self._conferir_orcamento()
            self.requisicoes += 1
            try:
                resposta = self.sessao.get(
                    url, params=params, headers={"Accept": "application/json"}, timeout=self.timeout
                )
            except requests.RequestException as erro:
                self.erros_http += 1
                ultimo_erro = f"{type(erro).__name__}: {erro}"
                status = None
                continue
            if resposta.status_code in STATUS_REPETIR:
                self.erros_http += 1
                ultimo_erro = f"HTTP {resposta.status_code}"
                status = resposta.status_code
                continue
            if resposta.status_code != 200:
                raise ErroAPI(url, f"HTTP {resposta.status_code}", resposta.status_code)
            try:
                return resposta.json()
            except ValueError as erro:
                raise ErroAPI(url, f"JSON invalido: {erro}", resposta.status_code) from erro
        raise ErroAPI(url, f"desistiu depois de {len(self.esperas) + 1} tentativas ({ultimo_erro})", status)

    def obter(self, caminho, params=None):
        """Chamada simples: devolve o conteudo de "dados"."""
        return self._chamar(f"{self.url_base}/{caminho.lstrip('/')}", params).get("dados")

    def paginar(self, caminho, params=None):
        """Percorre as paginas seguindo o link "next" e devolve cada item."""
        url = f"{self.url_base}/{caminho.lstrip('/')}"
        while url:
            corpo = self._chamar(url, params)
            yield from corpo.get("dados") or []
            # O link "next" ja traz todos os parametros
            params = None
            url = next((link["href"] for link in corpo.get("links", []) if link.get("rel") == "next"), None)
