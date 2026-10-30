import json
import os
import signal
import sys
from datetime import datetime, timedelta, timezone

HORAS_ABANDONO = 6


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _abandonada(caminho, agora):
    """Trava ilegivel ou com mais de 6 horas nao segura mais ninguem."""
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            inicio = datetime.fromisoformat(json.load(arquivo)["inicio"])
    except (OSError, ValueError, KeyError, TypeError):
        return True
    return agora - inicio > timedelta(hours=HORAS_ABANDONO)


def adquirir(caminho, agora=None):
    """Cria a trava em arquivo; devolve False se outra coleta esta rodando."""
    agora = agora or _agora()
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    for _ in range(2):
        try:
            # O_EXCL garante que so um processo consegue criar o arquivo
            descritor = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if not _abandonada(caminho, agora):
                return False
            os.remove(caminho)
            continue
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            json.dump({"pid": os.getpid(), "inicio": agora.isoformat()}, arquivo)
        return True
    return False


def liberar(caminho):
    try:
        os.remove(caminho)
    except FileNotFoundError:
        pass


def _encerrar(numero, quadro):
    sys.exit(128 + numero)


def sair_limpo_em_sigterm():
    """Com SIGTERM (timeout, kill), a coleta fecha o registro e libera a trava antes de sair."""
    return signal.signal(signal.SIGTERM, _encerrar)
