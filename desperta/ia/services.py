import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from flask import current_app

from desperta.ext.db import db
from desperta.orgaos.models import Evento, PautaItem
from desperta.proposicoes.models import Proposicao, Tramitacao
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao

from . import centralizacao, palavras, trechos, vetores
from .models import GeracaoTrecho, TrechoRAG

LOTE_INDEXACAO = 64
MODOS_BUSCA = ("hibrida", "vetorial", "palavras")


@dataclass
class ResultadoBusca:
    posicao: int
    similaridade: float
    trecho: TrechoRAG


def _hash(texto):
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _existentes(nome_modelo, tipos):
    consulta = db.select(TrechoRAG.tipo, TrechoRAG.ref_id, TrechoRAG.parte, TrechoRAG.id, TrechoRAG.hash_texto).where(
        TrechoRAG.modelo_embedding == nome_modelo
    )
    if tipos:
        consulta = consulta.where(TrechoRAG.tipo.in_(tipos))
    return {(tipo, ref_id, parte): (id_, hash_) for tipo, ref_id, parte, id_, hash_ in db.session.execute(consulta)}


def _gravar_lote(modelo, lote, existentes, preparar):
    """Gera os embeddings fora da transacao, grava e confirma: parar no meio nao perde o que ja foi feito."""
    embeddings = modelo.embutir([item["texto"] for item in lote])
    for item, embedding in zip(lote, embeddings):
        chave = (item["tipo"], item["ref_id"], item["parte"])
        trecho = db.session.get(TrechoRAG, existentes[chave][0]) if chave in existentes else None
        if trecho is None:
            trecho = TrechoRAG(tipo=item["tipo"], ref_id=item["ref_id"], parte=item["parte"])
            db.session.add(trecho)
        trecho.texto = item["texto"]
        trecho.tokens = item["tokens"]
        trecho.hash_texto = item["hash"]
        trecho.embedding = embedding
        trecho.modelo_embedding = modelo.nome
        db.session.flush()
        vetores.gravar(trecho.id, preparar(embedding))
    db.session.commit()
    db.session.expunge_all()


def _remover_sobras(sobras):
    """Registro ou parte que sumiu da origem; o trecho usado por uma geracao fica, para o historico."""
    removidos = mantidos = 0
    for trecho_id in sobras:
        if db.session.scalar(db.select(GeracaoTrecho.trecho_id).where(GeracaoTrecho.trecho_id == trecho_id).limit(1)):
            mantidos += 1
            continue
        vetores.remover(trecho_id)
        db.session.execute(db.delete(TrechoRAG).where(TrechoRAG.id == trecho_id))
        removidos += 1
    db.session.commit()
    return removidos, mantidos


def indexar(modelo, tipos=None, limite=None):
    """
    Secao 6.1: so registro novo ou com hash_texto diferente recebe embedding.
    limite e o maximo de trechos com embedding novo nesta execucao; o resto fica para a proxima.
    """
    config = current_app.config
    resumo = Counter()
    vetores.criar_indice()
    palavras.criar_indice()
    db.session.commit()
    preparar = centralizacao.transformador()
    existentes = _existentes(modelo.nome, tipos)
    vistos = set()
    lote = []

    for tipo, ref_id, texto in trechos.textos_de_origem(tipos):
        if limite is not None and resumo["indexados"] + len(lote) >= limite:
            resumo["interrompido"] = 1
            break
        # Texto que ja cabia num trecho so: nem precisa passar pelo tokenizador
        primeira = existentes.get((tipo, ref_id, 1))
        if primeira and primeira[1] == _hash(texto) and (tipo, ref_id, 2) not in existentes:
            vistos.add((tipo, ref_id, 1))
            resumo["iguais"] += 1
            continue
        partes = modelo.dividir(texto, config["RAG_TRECHO_TOKENS"], config["RAG_TRECHO_SOBREPOSICAO"])
        for parte, (texto_parte, tokens) in enumerate(partes, start=1):
            chave = (tipo, ref_id, parte)
            vistos.add(chave)
            hash_parte = _hash(texto_parte)
            if chave in existentes and existentes[chave][1] == hash_parte:
                resumo["iguais"] += 1
                continue
            lote.append(
                {
                    "tipo": tipo,
                    "ref_id": ref_id,
                    "parte": parte,
                    "texto": texto_parte,
                    "tokens": tokens,
                    "hash": hash_parte,
                }
            )
        if len(lote) >= LOTE_INDEXACAO:
            _gravar_lote(modelo, lote, existentes, preparar)
            resumo["indexados"] += len(lote)
            lote = []
    if lote:
        _gravar_lote(modelo, lote, existentes, preparar)
        resumo["indexados"] += len(lote)

    # Com limite, parte da origem nao foi lida: nao da para saber o que sumiu
    if not resumo["interrompido"]:
        sobras = [dados[0] for chave, dados in existentes.items() if chave not in vistos]
        resumo["removidos"], resumo["mantidos"] = _remover_sobras(sobras)

    db.session.add(
        LogSistema(
            nivel="info",
            modulo="IA",
            acao="indexar",
            descricao=(
                f"modelo={modelo.nome} indexados={resumo['indexados']} iguais={resumo['iguais']} "
                f"removidos={resumo['removidos']} mantidos={resumo['mantidos']}"
            ),
        )
    )
    db.session.commit()
    return resumo


def reconstruir_indice(nome_modelo):
    """Refaz os dois indices a partir de trecho_rag, sem gerar embeddings."""
    total = vetores.reconstruir(nome_modelo, centralizacao.transformador())
    palavras.criar_indice()
    palavras.reconstruir()
    db.session.add(
        LogSistema(nivel="info", modulo="IA", acao="reconstruir_indice", descricao=f"{total} trechos no indice")
    )
    db.session.commit()
    return total


def _ligado(tipo, ref_id):
    return db.and_(TrechoRAG.tipo == tipo, TrechoRAG.ref_id == ref_id)


def _ids_no_periodo(inicio, fim, tipos):
    """Trechos cujo registro de origem e do periodo; a data de cada tipo esta na sua tabela."""
    comeco = datetime.combine(inicio, time.min) if inicio else datetime.min
    # O fim do periodo vale o dia inteiro
    final = datetime.combine(fim + timedelta(days=1), time.min) if fim else datetime.max
    texto_id = db.cast(Proposicao.id, db.String)
    tramitacao_id = db.cast(Tramitacao.proposicao_id, db.String) + "/" + db.cast(Tramitacao.sequencia, db.String)
    pauta_id = db.cast(PautaItem.evento_id, db.String) + "/" + db.cast(PautaItem.ordem, db.String)
    por_tipo = {
        "proposicao": db.select(TrechoRAG.id)
        .join(Proposicao, _ligado("proposicao", texto_id))
        .where(Proposicao.data_apresentacao >= comeco, Proposicao.data_apresentacao < final),
        "tramitacao": db.select(TrechoRAG.id)
        .join(Tramitacao, _ligado("tramitacao", tramitacao_id))
        .where(Tramitacao.data_hora >= comeco, Tramitacao.data_hora < final),
        "votacao": db.select(TrechoRAG.id)
        .join(Votacao, _ligado("votacao", Votacao.id))
        .where(Votacao.data >= comeco.date(), Votacao.data < final.date()),
        "evento": db.select(TrechoRAG.id)
        .join(Evento, _ligado("evento", db.cast(Evento.id, db.String)))
        .where(Evento.data_hora_inicio >= comeco, Evento.data_hora_inicio < final),
        "pauta_item": db.select(TrechoRAG.id)
        .join(PautaItem, _ligado("pauta_item", pauta_id))
        .join(Evento, Evento.id == PautaItem.evento_id)
        .where(Evento.data_hora_inicio >= comeco, Evento.data_hora_inicio < final),
    }
    return db.union_all(*(por_tipo[tipo] for tipo in tipos or por_tipo))


def _juntar_por_rrf(listas):
    """Reciprocal Rank Fusion: cada lista soma 1 / (constante + posicao) ao trecho."""
    constante = current_app.config["RAG_RRF_K"]
    notas = Counter()
    for lista in listas:
        for posicao, trecho_id in enumerate(lista, start=1):
            notas[trecho_id] += 1 / (constante + posicao)
    return notas


def buscar(modelo, consulta, top_k=None, tipos=None, inicio=None, fim=None, modo="hibrida"):
    """
    Decisao 16.1: os melhores de cada indice, juntos pelo RRF; os filtros valem para os dois.
    Em similaridade vai a nota do RRF; no modo vetorial, que so serve para comparar, vai o cosseno.
    """
    if modo not in MODOS_BUSCA:
        raise ValueError(f"Modo de busca desconhecido: {modo}")
    k = top_k or current_app.config["RAG_TOP_K"]
    if inicio or fim:
        candidatos = _ids_no_periodo(inicio, fim, tipos)
    elif tipos:
        candidatos = db.select(TrechoRAG.id).where(TrechoRAG.tipo.in_(tipos))
    else:
        candidatos = None
    # O SQLite grava a criacao da tabela na hora, mas o conteudo do rebuild so com commit
    vetores.criar_indice()
    palavras.criar_indice()
    db.session.commit()

    limite = max(k, current_app.config["RAG_CANDIDATOS"])
    if modo == "vetorial":
        embedding = centralizacao.transformador()(modelo.embutir([consulta])[0])
        notas = {trecho_id: 1 - distancia for trecho_id, distancia in vetores.buscar(embedding, k, candidatos)}
    else:
        listas = [palavras.buscar(consulta, limite, candidatos)]
        if modo == "hibrida":
            embedding = centralizacao.transformador()(modelo.embutir([consulta])[0])
            listas.append([trecho_id for trecho_id, _ in vetores.buscar(embedding, limite, candidatos)])
        notas = _juntar_por_rrf(listas)

    melhores = sorted(notas.items(), key=lambda item: item[1], reverse=True)[:k]
    return [
        ResultadoBusca(posicao=posicao, similaridade=nota, trecho=db.session.get(TrechoRAG, trecho_id))
        for posicao, (trecho_id, nota) in enumerate(melhores, start=1)
    ]


def _proposicao_do_trecho(trecho):
    """Tramitacao tambem conta como achar a proposicao; o ref_id dela e "proposicao/sequencia"."""
    if trecho.tipo == "proposicao":
        return int(trecho.ref_id)
    if trecho.tipo == "tramitacao":
        return int(trecho.ref_id.split("/")[0])
    return None


def medir_busca(modelo, consultas, modos=MODOS_BUSCA, k=8):
    """Decisao 16.2: quantas das proposicoes esperadas aparecem nos k primeiros, em cada modo."""
    resultado = {}
    for modo in modos:
        acertos = 0
        total = 0
        por_consulta = []
        for item in consultas:
            esperadas = set(item["esperadas"])
            achadas = {
                _proposicao_do_trecho(achado.trecho) for achado in buscar(modelo, item["consulta"], k, modo=modo)
            }
            certas = len(esperadas & achadas)
            acertos += certas
            total += len(esperadas)
            por_consulta.append((item["consulta"], certas, len(esperadas)))
        resultado[modo] = {"acertos": acertos, "total": total, "consultas": por_consulta}
    return resultado
