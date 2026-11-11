import os

from flask import current_app

from desperta.ext.db import db

from .models import TrechoRAG

# Experimento da decisao 16.1: trecho_rag guarda o embedding original; so o indice e a consulta sao centralizados
ARQUIVO = "vetor_medio.npy"
LOTE = 1000


def _caminho():
    return os.path.join(current_app.instance_path, ARQUIVO)


def calcular(nome_modelo):
    """Calcula o vetor medio de todos os trechos e grava em instance/; devolve quantos trechos entraram."""
    import numpy

    soma = numpy.zeros(768, dtype=numpy.float64)
    total = 0
    ultimo = 0
    while True:
        linhas = db.session.execute(
            db.select(TrechoRAG.id, TrechoRAG.embedding)
            .where(TrechoRAG.modelo_embedding == nome_modelo, TrechoRAG.id > ultimo)
            .order_by(TrechoRAG.id)
            .limit(LOTE)
        ).all()
        if not linhas:
            break
        for id_trecho, embedding in linhas:
            soma += numpy.frombuffer(embedding, dtype=numpy.float32)
            total += 1
            ultimo = id_trecho
    if total:
        os.makedirs(current_app.instance_path, exist_ok=True)
        numpy.save(_caminho(), (soma / total).astype(numpy.float32))
    return total


def transformador():
    """Funcao que prepara um embedding para o indice; com RAG_CENTRALIZAR desligado, nao muda nada."""
    if not current_app.config["RAG_CENTRALIZAR"]:
        return lambda embedding: embedding

    import numpy

    medio = numpy.load(_caminho())

    def centralizar(embedding):
        vetor = numpy.frombuffer(embedding, dtype=numpy.float32) - medio
        return (vetor / (numpy.linalg.norm(vetor) or 1.0)).astype(numpy.float32).tobytes()

    return centralizar
