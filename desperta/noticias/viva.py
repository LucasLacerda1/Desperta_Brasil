from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from desperta.ext.db import db
from desperta.sistema.models import LogSistema

from .models import Noticia, NoticiaFonte

# ----------------------------------------------------------
# Noticia viva (decisao 25.13, item 3; registro em 25.16)
# Uma noticia por proposicao. O fato que abriu a noticia continua no topo (titulo e paragrafo
# principal nao mudam, escolha do Lucas); cada fato novo entra na secao "## Atualizacoes",
# da mais recente para a mais antiga, sem mexer no resto do texto (a equipe pode ter editado).
# - Noticia da proposicao ainda em rascunho ou em revisao: o fato entra direto nela.
# - Noticia ja publicada: o fato vira um RASCUNHO DE ATUALIZACAO, que a equipe revisa; ao
#   publicar, o texto entra nas atualizacoes da noticia original (mesmo slug) e o rascunho
#   fica arquivado como historico.
# Sem tabela nem coluna nova: a ligacao sai das fontes (a proposicao) e das datas.
# ----------------------------------------------------------
SECAO_ATUALIZACOES = "Atualizações"
MARCA_SECAO = "## "
MARCA_ATUALIZACAO = "### "
TITULO_DA_ATUALIZACAO = "Atualização: "
STATUS_ABERTOS = ("rascunho", "em_revisao")
TAMANHO_TITULO = 200


@dataclass
class Fato:
    """O fato novo ja escrito pelo gerador, pronto para virar uma atualizacao."""

    data: date
    titulo: str
    resumo: str
    # Partes do corpo que acompanham a atualizacao (ex.: o placar)
    detalhes: List[str] = field(default_factory=list)
    fontes: List[Tuple[str, str]] = field(default_factory=list)


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def proposicao_da_noticia(noticia):
    """A proposicao da noticia viva e a primeira fonte do tipo proposicao."""
    fonte = db.session.scalar(
        db.select(NoticiaFonte)
        .filter_by(noticia_id=noticia.id, tipo="proposicao")
        .order_by(NoticiaFonte.ordem)
        .limit(1)
    )
    return int(fonte.ref_id) if fonte else None


def _da_proposicao(proposicao_id):
    return (
        db.select(Noticia)
        .join(NoticiaFonte, NoticiaFonte.noticia_id == Noticia.id)
        .where(
            NoticiaFonte.tipo == "proposicao",
            NoticiaFonte.ref_id == str(proposicao_id),
            Noticia.tipo == "noticia",
            Noticia.origem == "ia",
        )
    )


def aberta_da_proposicao(proposicao_id):
    """A noticia da proposicao ainda em rascunho ou em revisao (a mais antiga, se houver mais de uma)."""
    return db.session.scalar(
        _da_proposicao(proposicao_id)
        .where(Noticia.status.in_(STATUS_ABERTOS))
        .order_by(Noticia.criado_em, Noticia.id)
        .limit(1)
    )


def publicada_da_proposicao(proposicao_id, antes_de=None):
    """A noticia publicada mais recente da proposicao (publicada antes de `antes_de`, se informado)."""
    consulta = _da_proposicao(proposicao_id).where(Noticia.status == "publicada")
    if antes_de is not None:
        consulta = consulta.where(Noticia.publicado_em < antes_de)
    return db.session.scalar(consulta.order_by(Noticia.publicado_em.desc(), Noticia.id.desc()).limit(1))


def original_da_atualizacao(noticia):
    """
    Se a noticia e um rascunho de atualizacao, a noticia publicada que ela atualiza; senao None.
    E atualizacao quando, ao ser criada, a proposicao ja tinha noticia publicada. Uma noticia comum
    so e criada quando a proposicao nao tem nenhuma aberta nem publicada, entao a regra nao a confunde.
    """
    if noticia.tipo != "noticia" or noticia.origem != "ia" or noticia.criado_em is None:
        return None
    proposicao_id = proposicao_da_noticia(noticia)
    if proposicao_id is None:
        return None
    original = publicada_da_proposicao(proposicao_id, antes_de=noticia.criado_em)
    return original if original is not None and original.id != noticia.id else None


def texto_da_atualizacao(fato):
    partes = [f"{MARCA_ATUALIZACAO}{fato.data:%d/%m/%Y}: {fato.titulo}", fato.resumo, *fato.detalhes]
    return "\n\n".join(parte.strip() for parte in partes if parte and parte.strip())


def _inserir_na_secao(corpo, texto):
    """Poe o texto logo abaixo do titulo "## Atualizacoes" (a mais recente primeiro); cria a secao se nao houver."""
    titulo = f"{MARCA_SECAO}{SECAO_ATUALIZACOES}"
    linhas = (corpo or "").split("\n")
    if titulo in linhas:
        posicao = linhas.index(titulo) + 1
        resto = "\n".join(linhas[posicao:]).strip()
        return "\n".join(linhas[:posicao]) + f"\n\n{texto}" + (f"\n\n{resto}" if resto else "")
    return f"{(corpo or '').rstrip()}\n\n{titulo}\n\n{texto}"


def _juntar_fontes(noticia, fontes):
    existentes = {(fonte.tipo, fonte.ref_id) for fonte in noticia.fontes}
    ordem = max((fonte.ordem for fonte in noticia.fontes), default=0)
    for tipo, ref_id in fontes:
        if (tipo, str(ref_id)) in existentes:
            continue
        ordem += 1
        noticia.fontes.append(NoticiaFonte(tipo=tipo, ref_id=str(ref_id), ordem=ordem))
        existentes.add((tipo, str(ref_id)))


def acrescentar(noticia, fato):
    """O fato entra na noticia aberta. Se ela e um rascunho de atualizacao, o corpo e a propria lista."""
    texto = texto_da_atualizacao(fato)
    if original_da_atualizacao(noticia) is not None:
        noticia.corpo = f"{texto}\n\n{noticia.corpo.strip()}"
    else:
        noticia.corpo = _inserir_na_secao(noticia.corpo, texto)
    _juntar_fontes(noticia, fato.fontes)
    noticia.alterado_em = _agora()
    db.session.add(
        LogSistema(
            nivel="info",
            modulo="IA",
            acao="atualizar_noticia_viva",
            descricao=f"Fato de {fato.data:%d/%m/%Y} acrescentado: {fato.titulo}"[:1000],
            entidade="noticia",
            entidade_id=str(noticia.id),
        )
    )
    return noticia


def criar_atualizacao(original, fato, cod_tema):
    """Rascunho de atualizacao de uma noticia ja publicada; a equipe revisa antes de entrar."""
    from .services import criar_rascunho

    titulo = f"{TITULO_DA_ATUALIZACAO}{fato.titulo}"
    if len(titulo) > TAMANHO_TITULO:
        titulo = titulo[: TAMANHO_TITULO - 1].rsplit(" ", 1)[0] + "…"
    rascunho = criar_rascunho(titulo, fato.resumo, texto_da_atualizacao(fato), cod_tema, fato.fontes)
    # O banco grava criado_em arredondado ao segundo; com a hora exata, "criado depois da publicacao
    # da original" (original_da_atualizacao) vale mesmo no mesmo segundo
    rascunho.criado_em = _agora()
    db.session.add(
        LogSistema(
            nivel="info",
            modulo="IA",
            acao="rascunho_de_atualizacao",
            descricao=f"Rascunho de atualizacao da noticia {original.id} ({original.slug}).",
            entidade="noticia",
            entidade_id=str(rascunho.id),
        )
    )
    return rascunho


def destino_do_fato(proposicao_id, fato, cod_tema, fontes, criar_nova):
    """
    Para onde vai o fato: a noticia aberta da proposicao, um rascunho de atualizacao da publicada,
    ou uma noticia nova (criar_nova()). Devolve a noticia.
    """
    aberta = aberta_da_proposicao(proposicao_id)
    if aberta is not None:
        return acrescentar(aberta, fato)
    publicada = publicada_da_proposicao(proposicao_id)
    if publicada is not None:
        return criar_atualizacao(publicada, fato, cod_tema)
    return criar_nova()


def publicar_atualizacao(rascunho, original, admin):
    """
    Ao publicar o rascunho de atualizacao: o texto (talvez editado pela equipe) entra nas atualizacoes
    da original, que ganha as fontes e o alterado_em; o rascunho fica arquivado como historico.
    """
    from .services import _revisao

    original.corpo = _inserir_na_secao(original.corpo, rascunho.corpo.strip())
    _juntar_fontes(original, [(fonte.tipo, fonte.ref_id) for fonte in rascunho.fontes])
    original.alterado_em = _agora()
    _revisao(original, admin, "editou", f"Atualização publicada (rascunho {rascunho.id}).")
    rascunho.status = "arquivada"
    _revisao(rascunho, admin, "publicou", f"Entrou como atualização da notícia {original.id}.")
    db.session.add(
        LogSistema(
            nivel="info",
            modulo="admin",
            acao="publicar_atualizacao",
            descricao=f"Rascunho {rascunho.id} entrou como atualizacao da noticia {original.id}.",
            admin_id=admin.id,
            entidade="noticia",
            entidade_id=str(original.id),
        )
    )
    return original


def como_dict_da_original(noticia) -> Optional[dict]:
    """Para a equipe: qual noticia publicada o rascunho atualiza."""
    original = original_da_atualizacao(noticia)
    if original is None:
        return None
    return {"id": original.id, "titulo": original.titulo, "slug": original.slug}


# ======================================================
# JUNTAR OS RASCUNHOS QUE JA ESTAVAM NA FILA (25.16, ponto 3)
# ======================================================
def _data_do_fato_da_noticia(noticia):
    """A data do fato que a noticia conta, pela entrada da geracao; sem ela, o dia em que foi criada."""
    import json

    from desperta.ia.models import GeracaoIA
    from desperta.proposicoes.models import Proposicao
    from desperta.votacoes.models import Votacao

    entrada = db.session.scalar(
        db.select(GeracaoIA.entrada).filter_by(noticia_id=noticia.id, status="ok").order_by(GeracaoIA.id).limit(1)
    )
    try:
        entrada = json.loads(entrada) if entrada else {}
    except ValueError:
        entrada = {}
    if entrada.get("votacao_id"):
        votacao = db.session.get(Votacao, entrada["votacao_id"])
        if votacao is not None:
            return votacao.data
    if entrada.get("caso") == "situacao" and entrada.get("data_status"):
        return datetime.fromisoformat(entrada["data_status"]).date()
    if entrada.get("caso") == "nova" and entrada.get("proposicao_id"):
        proposicao = db.session.get(Proposicao, entrada["proposicao_id"])
        if proposicao is not None:
            return proposicao.data_apresentacao.date()
    return noticia.criado_em.date()


def _fato_da_noticia(noticia):
    from .services import secoes_do_corpo

    detalhes = [secao["texto"] for secao in secoes_do_corpo(noticia.corpo) if secao["titulo"] == "Resultado da votação"]
    return Fato(
        data=_data_do_fato_da_noticia(noticia),
        titulo=noticia.titulo,
        resumo=noticia.resumo,
        detalhes=detalhes,
        fontes=[(fonte.tipo, fonte.ref_id) for fonte in noticia.fontes],
    )


def grupos_para_juntar():
    """
    {proposicao_id: [noticias abertas da IA, da mais antiga para a mais nova]}, so as proposicoes
    com mais de uma. Proposicao que ja tem noticia publicada fica de fora (devolvida a parte).
    """
    abertas = db.session.scalars(
        db.select(Noticia)
        .where(Noticia.status.in_(STATUS_ABERTOS), Noticia.origem == "ia", Noticia.tipo == "noticia")
        .order_by(Noticia.criado_em, Noticia.id)
    ).all()
    primeira_fonte = {}
    for noticia_id, ref_id, ordem in db.session.execute(
        db.select(NoticiaFonte.noticia_id, NoticiaFonte.ref_id, NoticiaFonte.ordem)
        .where(NoticiaFonte.tipo == "proposicao")
        .order_by(NoticiaFonte.ordem.desc())
    ):
        primeira_fonte[noticia_id] = int(ref_id)
    grupos = {}
    for noticia in abertas:
        proposicao_id = primeira_fonte.get(noticia.id)
        if proposicao_id is not None:
            grupos.setdefault(proposicao_id, []).append(noticia)
    grupos = {chave: lista for chave, lista in grupos.items() if len(lista) > 1}
    com_publicada = {chave for chave in grupos if publicada_da_proposicao(chave) is not None}
    return {chave: lista for chave, lista in grupos.items() if chave not in com_publicada}, com_publicada


def juntar(noticias, admin):
    """
    A mais antiga vira a noticia viva (o fato dela fica no topo); as outras entram como atualizacoes,
    na ordem das datas dos fatos, com as fontes; as geracoes passam para a viva e as outras sao apagadas.
    Devolve (noticia viva, quantos rascunhos repetiam um fato ja contado).
    """
    from desperta.ia.models import GeracaoIA

    from .services import _revisao

    from desperta.ia.geracao import chave_do_fato

    def chaves(noticia):
        return {
            chave_do_fato(entrada)
            for entrada in db.session.scalars(
                db.select(GeracaoIA.entrada).filter_by(noticia_id=noticia.id, status="ok")
            )
        }

    viva, outras = noticias[0], noticias[1:]
    ja_contados = chaves(viva)
    fatos = sorted(((_fato_da_noticia(outra), outra) for outra in outras), key=lambda par: (par[0].data, par[1].id))
    repetidos = 0
    for fato, outra in fatos:
        # O mesmo fato escrito mais de uma vez (antes da 25.16) entra uma vez so
        das_outras = chaves(outra)
        repetido = bool(das_outras) and das_outras <= ja_contados
        ja_contados |= das_outras
        if repetido:
            repetidos += 1
        else:
            viva.corpo = _inserir_na_secao(viva.corpo, texto_da_atualizacao(fato))
        _juntar_fontes(viva, fato.fontes)
        db.session.execute(db.update(GeracaoIA).where(GeracaoIA.noticia_id == outra.id).values(noticia_id=viva.id))
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="admin",
                acao="juntar_noticia_viva",
                descricao=(
                    f"Rascunho {outra.id} ({outra.titulo[:120]}) "
                    + ("repetia um fato ja contado" if repetido else "entrou como atualizacao")
                    + f" da noticia {viva.id}."
                ),
                admin_id=admin.id,
                entidade="noticia",
                entidade_id=str(viva.id),
            )
        )
        # As geracoes ja foram para a viva: a lista na memoria e relida, senao o ORM as desligaria ao apagar
        db.session.flush()
        db.session.expire(outra, ["geracoes"])
        db.session.delete(outra)
    viva.alterado_em = _agora()
    ids = ", ".join(str(outra.id) for _, outra in fatos)
    comentario = f"Notícia viva (25.16): juntou os rascunhos {ids}, da mesma proposição"
    if repetidos:
        comentario += f" ({repetidos} repetiam um fato já contado e entraram só como fonte)"
    _revisao(viva, admin, "editou", f"{comentario}.")
    return viva, repetidos
