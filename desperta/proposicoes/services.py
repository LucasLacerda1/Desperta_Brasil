# ----------------------------------------------------------
# Transparencia (05/11/2026): campo que a Camara nao informou aparece como tal no portal.
# O banco guarda o que a API mandou ("", "." ou nulo); aqui o codigo reconhece e explica.
# ----------------------------------------------------------
# A API usa "." no lugar do regime e da apreciacao quando nao ha informacao
VALORES_SEM_INFORMACAO = ("", ".", "-")
NAO_INFORMADO = "não informado pela Câmara"
NAO_INFORMADA = "não informada pela Câmara"


def informado(valor):
    """Devolve o valor sem espacos, ou None se a Camara nao informou."""
    if valor is None:
        return None
    texto = str(valor).strip()
    return None if texto in VALORES_SEM_INFORMACAO else texto


def ou_nao_informado(valor, feminino=False):
    return informado(valor) or (NAO_INFORMADA if feminino else NAO_INFORMADO)
