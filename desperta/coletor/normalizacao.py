import hashlib
import json
import re
from datetime import date, datetime, timezone


def agora_utc():
    """Colunas tecnicas ficam em UTC, sem fuso (ver desperta/ext/db/mixins.py)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def id_da_uri(uri, recurso=None):
    """Extrai o id final de uma uri; com recurso, so aceita uri daquele recurso (ex.: deputados)."""
    if not uri:
        return None
    padrao = rf"/{recurso}/(\d+)/?$" if recurso else r"/(\d+)/?$"
    achado = re.search(padrao, uri)
    return int(achado.group(1)) if achado else None


def id_texto_da_uri(uri):
    """Id de votacao e texto, ex.: .../votacoes/2310837-8."""
    if not uri:
        return None
    return uri.rstrip("/").rsplit("/", 1)[-1] or None


def opcional(valor):
    """Coluna de texto opcional: vazio vira None."""
    if isinstance(valor, str) and not valor.strip():
        return None
    return valor


def para_int(valor):
    """Ids e codigos que a API manda como texto."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    return int(valor)


def para_texto(valor):
    """Codigos que vem como numero ou texto (cod_titulo, por exemplo) ficam em texto."""
    return None if valor is None else str(valor)


def para_bool(valor):
    """Campos 0/1 ou booleanos da API; ausente continua None."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, str):
        return valor.strip().lower() in ("1", "true", "sim")
    return bool(valor)


def para_data_hora(valor):
    """Datas da Camara: horario de Brasilia, sem fuso, como a API manda."""
    if not valor:
        return None
    return datetime.fromisoformat(valor.replace("Z", "")).replace(tzinfo=None)


def para_data(valor):
    if not valor:
        return None
    return date.fromisoformat(valor[:10])


def calcular_hash(valores):
    """SHA-256 dos valores que vao para as colunas do modelo, com chaves ordenadas."""
    texto = json.dumps(valores, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
