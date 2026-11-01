import json
import os
import signal
import sys
from datetime import datetime, timedelta, timezone

HORAS_ABANDONO = 6


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _processo_existe(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Existe, mas e de outro usuario
        return True
    return True


def _motivo_abandono(caminho, agora):
    """Devolve por que a trava esta abandonada, ou None se ela ainda vale."""
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        inicio = datetime.fromisoformat(dados["inicio"])
        pid = int(dados["pid"])
    except (OSError, ValueError, KeyError, TypeError):
        return "arquivo ilegivel"
    # O limite de horas vem primeiro: o numero do PID pode ter sido reaproveitado por outro programa
    if agora - inicio > timedelta(hours=HORAS_ABANDONO):
        return f"mais de {HORAS_ABANDONO} horas"
    if not _processo_existe(pid):
        return f"o processo {pid} nao existe mais"
    return None


def adquirir(caminho, agora=None, ao_abandonar=None):
    """
    Cria a trava em arquivo; devolve False se outra coleta esta rodando.
    ao_abandonar(motivo) e chamada quando uma trava abandonada e removida.
    """
    agora = agora or _agora()
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    for _ in range(2):
        try:
            # O_EXCL garante que so um processo consegue criar o arquivo
            descritor = os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            motivo = _motivo_abandono(caminho, agora)
            if motivo is None:
                return False
            os.remove(caminho)
            if ao_abandonar:
                ao_abandonar(motivo)
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
