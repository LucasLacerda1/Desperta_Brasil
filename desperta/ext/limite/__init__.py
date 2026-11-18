"""
Limite de requisicoes nas rotas da API (RNF10, decisao 25.4).

Conta as requisicoes de cada endereco (IP) numa janela de tempo. Acima do limite, a API
responde 429 com a mensagem e o cabecalho Retry-After, em vez de processar o pedido.
A busca tem um limite proprio, menor, porque e a rota mais pesada.

A contagem fica na memoria do processo, como o limite do login: basta para um servidor com
um processo do Flask. Com varios processos do Gunicorn, cada um conta as suas requisicoes
(o limite real fica multiplicado por eles). Sem Redis no MVP.
"""

import threading
import time
from collections import defaultdict, deque

from flask import current_app, request, session

from desperta.ext.erros import MuitasTentativas

PREFIXO_DA_API = "/api/"
ROTA_DA_BUSCA = "/api/noticias/busca"
# A cada tantas requisicoes, as contagens de quem parou de acessar saem da memoria
LIMPAR_A_CADA = 1000


# === Contador (requisicoes recentes por grupo e endereco) ===
class Contador:
    def __init__(self):
        self.recentes = defaultdict(deque)
        self.trava = threading.Lock()
        self.vistas = 0

    def passar(self, chave, limite, janela_s, agora):
        """Anota a requisicao e devolve 0; acima do limite nao anota e devolve os segundos de espera."""
        with self.trava:
            self.vistas += 1
            if self.vistas % LIMPAR_A_CADA == 0:
                self._limpar(janela_s, agora)
            fila = self.recentes[chave]
            while fila and agora - fila[0] >= janela_s:
                fila.popleft()
            if len(fila) >= limite:
                return max(1, int(janela_s - (agora - fila[0])) + 1)
            fila.append(agora)
            return 0

    def _limpar(self, janela_s, agora):
        for chave in [c for c, fila in self.recentes.items() if not fila or agora - fila[-1] >= janela_s]:
            del self.recentes[chave]

    def zerar(self):
        with self.trava:
            self.recentes.clear()


def _da_equipe():
    """Quem esta logado na area da equipe nao entra no limite; o cookie de sessao e assinado."""
    # Import tardio: a extensao nao depende do dominio na carga do modulo
    from desperta.auth.sessao import CHAVE_ID

    return session.get(CHAVE_ID) is not None


def _conferir():
    if not request.path.startswith(PREFIXO_DA_API) or request.method == "OPTIONS":
        return
    config = current_app.config
    na_busca = request.path.startswith(ROTA_DA_BUSCA)
    limite = config["LIMITE_BUSCA"] if na_busca else config["LIMITE_GERAL"]
    if limite <= 0 or _da_equipe():
        return
    grupo = "busca" if na_busca else "geral"
    endereco = request.remote_addr or "desconhecido"
    contador = current_app.extensions["limite"]
    espera = contador.passar((grupo, endereco), limite, config["LIMITE_JANELA_S"], time.monotonic())
    if espera:
        raise MuitasTentativas(f"Muitas requisições. Tente de novo em {espera} segundos.", esperar_s=espera)


def init_app(app):
    # Um contador por app: cada processo (e cada teste) tem a sua contagem
    app.extensions["limite"] = Contador()
    app.before_request(_conferir)
