import json
from dataclasses import dataclass, field
from typing import List

from flask import current_app

from desperta.ext.db import db

# ----------------------------------------------------------
# Fila por prioridade (decisao 25.13, item 2; registro em 25.15)
# INTERNO: so a equipe ve. Ordena a revisao sem esconder nada: toda noticia continua na fila.
# Calculada na hora, a partir do caso da geracao (geracao_ia.entrada), das fontes e das
# lacunas da Camara; sem coluna nova no banco.
# ----------------------------------------------------------
ALTA = "alta"
MEDIA = "media"
BAIXA = "baixa"
PRIORIDADES = (ALTA, MEDIA, BAIXA)
ORDEM = {ALTA: 0, MEDIA: 1, BAIXA: 2}

# Tipos que pesam mais quando sao apresentados
TIPOS_DE_PESO = {"PEC": "proposta de emenda à Constituição nova", "MPV": "medida provisória nova"}
TIPOS_COMUNS = {"PL": "projeto de lei novo", "PLP": "projeto de lei complementar novo"}


@dataclass
class Prioridade:
    nivel: str
    motivos: List[str] = field(default_factory=list)

    def como_dict(self):
        return {"nivel": self.nivel, "motivos": self.motivos}


def _casos(ids):
    """{noticia_id: [entradas das geracoes ok, da mais antiga para a mais nova]} (25.16: a noticia viva tem varias)."""
    from desperta.ia.models import GeracaoIA

    entradas = {}
    for noticia_id, entrada in db.session.execute(
        db.select(GeracaoIA.noticia_id, GeracaoIA.entrada)
        .where(GeracaoIA.noticia_id.in_(ids), GeracaoIA.status == "ok")
        .order_by(GeracaoIA.id)
    ):
        try:
            entradas.setdefault(noticia_id, []).append(json.loads(entrada))
        except ValueError:
            entradas.setdefault(noticia_id, []).append({})
    return entradas


def _fontes(ids):
    from .models import NoticiaFonte

    fontes = {}
    for fonte in db.session.scalars(
        db.select(NoticiaFonte).where(NoticiaFonte.noticia_id.in_(ids)).order_by(NoticiaFonte.ordem)
    ):
        fontes.setdefault(fonte.noticia_id, []).append((fonte.tipo, fonte.ref_id))
    return fontes


def _da_votacao(votacao, proposicao):
    from desperta.votacoes.services import e_votacao_de_merito

    merito = e_votacao_de_merito(votacao.descricao)
    acompanhado = proposicao is not None and proposicao.sigla_tipo in current_app.config["TIPOS_ACOMPANHADOS"]
    if votacao.sigla_orgao == "PLEN":
        if merito and acompanhado:
            return ALTA, "votação do próprio projeto no Plenário"
        return MEDIA, "votação de procedimento no Plenário (requerimento, destaque, urgência)"
    if merito and acompanhado:
        return MEDIA, "votação do projeto em comissão"
    return BAIXA, "votação de procedimento em comissão"


def _da_situacao(proposicao, entrada):
    from desperta.proposicoes.situacoes import MARCOS, situacao_informada

    if proposicao is None:
        return MEDIA, "proposição não encontrada no banco"
    if not situacao_informada(proposicao.cod_situacao, proposicao.situacao):
        return BAIXA, "passo do andamento sem situação informada pela Câmara"
    if proposicao.cod_situacao in MARCOS:
        return ALTA, f'marco: "{proposicao.situacao.strip()}"'
    return MEDIA, f'mudança de situação: "{proposicao.situacao.strip()}"'


def _da_nova(proposicao):
    if proposicao is None:
        return MEDIA, "proposição não encontrada no banco"
    if proposicao.sigla_tipo in TIPOS_DE_PESO:
        return ALTA, TIPOS_DE_PESO[proposicao.sigla_tipo]
    if proposicao.sigla_tipo in TIPOS_COMUNS:
        return MEDIA, TIPOS_COMUNS[proposicao.sigla_tipo]
    return BAIXA, f"{proposicao.sigla_tipo} novo"


def calcular(noticias):
    """
    {noticia_id: Prioridade} para varias noticias de uma vez (poucas consultas).
    noticias: objetos ou linhas com id, origem e tipo.
    Regras: o fato decide o nivel; uma falha grave nos dados da Camara (contradicao ou
    ocultacao, 25.13) sobe para alta; caso desconhecido fica no meio (seguro na duvida).
    """
    from desperta.proposicoes.models import Proposicao
    from desperta.sistema.lacunas import CONTRADICAO, OCULTACAO, lacunas_em_lote
    from desperta.votacoes.models import Votacao

    ids = [noticia.id for noticia in noticias]
    if not ids:
        return {}
    casos = _casos(ids)
    fontes = _fontes(ids)
    ids_proposicoes = {int(ref) for lista in fontes.values() for tipo, ref in lista if tipo == "proposicao"}
    ids_votacoes = {ref for lista in fontes.values() for tipo, ref in lista if tipo == "votacao"}
    proposicoes = {p.id: p for p in db.session.scalars(db.select(Proposicao).where(Proposicao.id.in_(ids_proposicoes)))}
    votacoes = {v.id: v for v in db.session.scalars(db.select(Votacao).where(Votacao.id.in_(ids_votacoes)))}
    lacunas_p, lacunas_v = lacunas_em_lote(list(proposicoes.values()), list(votacoes.values()))

    resultado = {}

    def do_fato(noticia, entrada, proposicao, votacao_padrao):
        caso = entrada.get("caso")
        votacao = votacoes.get(entrada.get("votacao_id")) or votacao_padrao
        if noticia.tipo == "relatorio" or caso == "relatorio_semanal":
            return ALTA, "relatório"
        if noticia.origem == "equipe":
            return MEDIA, "escrita pela equipe"
        if caso == "votacao" and votacao is not None:
            return _da_votacao(votacao, proposicao)
        if caso == "situacao":
            return _da_situacao(proposicao, entrada)
        if caso == "nova":
            return _da_nova(proposicao)
        return MEDIA, "sem regra para este caso"

    resultado = {}
    for noticia in noticias:
        entradas = casos.get(noticia.id) or [{}]
        lista = fontes.get(noticia.id, [])
        proposicao = next((proposicoes.get(int(ref)) for tipo, ref in lista if tipo == "proposicao"), None)
        votacao = next((votacoes.get(ref) for tipo, ref in lista if tipo == "votacao"), None)

        # 25.16: a noticia viva junta varios fatos; vale o nivel mais alto, com o motivo de cada fato
        por_fato = [do_fato(noticia, entrada, proposicao, votacao) for entrada in entradas]
        nivel = min((nivel for nivel, _ in por_fato), key=ORDEM.get)
        motivos = list(dict.fromkeys(motivo for _, motivo in sorted(por_fato, key=lambda item: ORDEM[item[0]])))

        # A Camara mudou de novo depois do ultimo fato de situacao: a equipe precisa saber antes de publicar
        situacoes = [entrada for entrada in entradas if entrada.get("caso") == "situacao"]
        if situacoes and proposicao is not None and proposicao.data_status is not None:
            ultima = situacoes[-1].get("data_status")
            if ultima and ultima != proposicao.data_status.isoformat():
                motivos.append("a situação mudou de novo depois deste rascunho")

        graves = [
            lacuna
            for tipo, ref in lista
            for lacuna in (
                lacunas_p.get(int(ref), [])
                if tipo == "proposicao"
                else lacunas_v.get(ref, []) if tipo == "votacao" else []
            )
            if lacuna.nivel in (CONTRADICAO, OCULTACAO)
        ]
        if graves:
            nivel = ALTA
            motivos.extend(f"falha grave nos dados da Câmara: {lacuna.codigo}" for lacuna in graves)
        resultado[noticia.id] = Prioridade(nivel, motivos)
    return resultado
