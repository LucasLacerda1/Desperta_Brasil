"""
Planta da noticia e publicacao automatica (decisao 25.18; texto em docs/PLANTA_DA_NOTICIA.md).

O conferidor mede cada rascunho contra a planta. Escolha do Lucas (17/11/2026): a noticia que
passa em tudo e publicada sozinha; so vai para a revisao da equipe quando o sistema nao confia
nela. A confianca e medida por regras que da para explicar: as da planta (falhas) e as dos dados
(falha grave da Camara, situacao fora do dicionario, rascunho antigo, equipe ja mexendo).
PUBLICACAO_AUTOMATICA: ensaio (padrao, so marca), ligada ou desligada.
"""

import re
import secrets
from dataclasses import dataclass, field
from typing import List

from flask import current_app

from desperta.ext.db import db
from desperta.sistema.models import LogSistema

from .models import Noticia, NoticiaRevisao

# ----------------------------------------------------------
# Regras da planta (o grupo pode ajustar)
# ----------------------------------------------------------
TITULO_MINIMO = 10
TITULO_MAXIMO = 120
RESUMO_FRASES = 2
RESUMO_PALAVRAS = 60
RESUMO_CARACTERES_AVISO = 400
FRASE_PALAVRAS_AVISO = 25

# Palavras de opiniao ou de emocao que nao entram no titulo nem no paragrafo principal
PALAVRAS_DE_OPINIAO = (
    "polêmic",
    "absurd",
    "históric",
    "important",
    "vergonh",
    "escândal",
    "escandal",
    "brilhante",
    "péssim",
    "ótim",
    "excelente",
    "lamentável",
    "lamentavelmente",
    "infelizmente",
    "felizmente",
    "finalmente",
    "surpreendente",
    "chocante",
    "inacreditável",
    "conseguiu",
    "derrubou",
    "barrou",
    "emplacou",
)
# O que nao entra no paragrafo principal (vai para os blocos abaixo, 25.13)
FORA_DO_PARAGRAFO = (
    (re.compile(r"\bvotos? a favor\b|\b\d+ contra\b|\babsten", re.IGNORECASE), "placar no parágrafo principal"),
    (
        re.compile(r"não (foi |foram )?informad|não informou", re.IGNORECASE),
        "o que a Câmara não informou no parágrafo principal",
    ),
)
SECOES_POR_CASO = {
    "nova": ("O que propõe", "Onde está na Câmara"),
    "situacao": ("O que propõe", "Onde está na Câmara"),
    "votacao": ("O que propõe", "Resultado da votação", "Onde está na Câmara"),
}
# So o que foi escrito ja na planta pode sair sozinho; o resto (de antes de 17/11) vai para a equipe
VERSOES_NA_PLANTA = ("frases-v3", "boletim-v1")
SIGLA = re.compile(r"\b(PL|PLP|PEC|MPV|PDL) \d+/\d{4}")
FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ\"“])")

NOME_DO_SISTEMA = "Publicação automática"
EMAIL_DO_SISTEMA = "publicacao-automatica@desperta.local"
MODOS = ("desligada", "ensaio", "ligada")


@dataclass
class Conferencia:
    falhas: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    @property
    def passou(self):
        return not self.falhas

    def como_dict(self):
        return {"passou": self.passou, "falhas": self.falhas, "avisos": self.avisos}


def frases(texto):
    return [frase for frase in FIM_DE_FRASE.split((texto or "").strip()) if frase.strip()]


def _palavras(texto):
    return re.findall(r"\w+", texto)


# ======================================================
# REGRAS DO TEXTO (planta, secoes 2 e 3)
# ======================================================
def conferir_texto(titulo, resumo, corpo, caso=None, tipo="noticia", atualizacao=False):
    """As regras da planta que dependem so do texto. Devolve Conferencia."""
    from desperta.ia.gerador import TIPOS

    from .services import secoes_do_corpo

    conferencia = Conferencia()
    falhas, avisos = conferencia.falhas, conferencia.avisos

    # Titulo (o rascunho de atualizacao nao tem titulo proprio no portal: entra na noticia original)
    if not atualizacao:
        if not TITULO_MINIMO <= len(titulo) <= TITULO_MAXIMO:
            falhas.append(f"título com {len(titulo)} caracteres (a planta pede de {TITULO_MINIMO} a {TITULO_MAXIMO})")
        if "…" in titulo:
            falhas.append("título cortado no meio (…)")
        if tipo == "noticia" and not SIGLA.search(titulo):
            falhas.append("título sem a sigla da proposição (ex.: PL 1234/2024)")

    # Paragrafo principal
    lista = frases(resumo)
    if len(lista) > RESUMO_FRASES:
        falhas.append(f"parágrafo principal com {len(lista)} frases (a planta pede até {RESUMO_FRASES})")
    if len(_palavras(resumo)) > RESUMO_PALAVRAS:
        falhas.append(f"parágrafo principal com {len(_palavras(resumo))} palavras (até {RESUMO_PALAVRAS})")
    for padrao, motivo in FORA_DO_PARAGRAFO:
        if padrao.search(resumo):
            falhas.append(motivo)
    sigla = SIGLA.search(resumo)
    if sigla and sigla.group(1) in TIPOS:
        extenso = TIPOS[sigla.group(1)][0]
        if extenso.lower() not in resumo[: sigla.start()].lower():
            falhas.append(f"sigla {sigla.group(1)} sem explicação na primeira vez ({extenso})")
    if len(resumo) > RESUMO_CARACTERES_AVISO:
        avisos.append(f"parágrafo principal com {len(resumo)} caracteres")
    longas = [frase for frase in lista if len(_palavras(frase)) > FRASE_PALAVRAS_AVISO]
    if longas:
        avisos.append(f"{len(longas)} frase(s) do parágrafo principal com mais de {FRASE_PALAVRAS_AVISO} palavras")

    # Imparcialidade: titulo e paragrafo principal
    texto = f"{titulo} {resumo}".lower()
    opiniao = sorted({palavra for palavra in PALAVRAS_DE_OPINIAO if re.search(rf"\b{palavra}", texto)})
    if opiniao:
        falhas.append(f"palavra de opinião: {', '.join(opiniao)}")

    # Blocos
    if tipo == "noticia" and not atualizacao:
        titulos = [secao["titulo"] for secao in secoes_do_corpo(corpo)]
        faltam = [secao for secao in SECOES_POR_CASO.get(caso, ()) if secao not in titulos]
        if caso not in SECOES_POR_CASO:
            falhas.append("caso sem planta (só a equipe publica)")
        elif faltam:
            falhas.append(f"faltam os blocos: {', '.join(faltam)}")
    return conferencia


# ======================================================
# CONFIANCA (planta, secao 4)
# ======================================================
def _geracoes(noticia):
    from desperta.ia.models import GeracaoIA

    return db.session.scalars(
        db.select(GeracaoIA).filter_by(noticia_id=noticia.id, status="ok").order_by(GeracaoIA.id)
    ).all()


def _caso(geracao):
    import json

    try:
        return json.loads(geracao.entrada).get("caso")
    except ValueError:
        return None


def conferir(noticia):
    """A planta e a confianca juntas: passou = pode sair sozinha."""
    from desperta.proposicoes.models import Proposicao
    from desperta.proposicoes.situacoes import situacao_conhecida
    from desperta.sistema.lacunas import CONTRADICAO, OCULTACAO, lacunas_das_fontes

    from . import viva

    geracoes = _geracoes(noticia)
    casos = [_caso(geracao) for geracao in geracoes]
    atualizacao = viva.original_da_atualizacao(noticia) is not None
    conferencia = conferir_texto(
        noticia.titulo,
        noticia.resumo,
        noticia.corpo,
        casos[0] if casos else None,
        noticia.tipo,
        atualizacao=atualizacao,
    )
    falhas = conferencia.falhas
    if noticia.origem != "ia":
        falhas.append("notícia escrita pela equipe")
    if not geracoes or any(geracao.versao_prompt not in VERSOES_NA_PLANTA for geracao in geracoes):
        falhas.append("escrita antes da planta (rascunho antigo)")
    revisoes = db.select(db.func.count()).select_from(NoticiaRevisao).where(NoticiaRevisao.noticia_id == noticia.id)
    sistema = _id_do_sistema()
    if sistema is not None:
        revisoes = revisoes.where(NoticiaRevisao.admin_id != sistema)
    humanas = db.session.scalar(revisoes)
    if humanas:
        falhas.append("a equipe já mexeu neste rascunho")
    graves = [
        lacuna.codigo
        for lacuna in lacunas_das_fontes([(fonte.tipo, fonte.ref_id) for fonte in noticia.fontes])
        if lacuna.nivel in (CONTRADICAO, OCULTACAO)
    ]
    if graves:
        falhas.append(f"falha grave nos dados da Câmara: {', '.join(sorted(set(graves)))}")
    principal = viva.proposicao_da_noticia(noticia)
    if principal is not None:
        proposicao = db.session.get(Proposicao, principal)
        if proposicao is not None and not situacao_conhecida(proposicao.cod_situacao, proposicao.situacao):
            falhas.append(f"situação fora do dicionário: {proposicao.situacao!r}")
    return conferencia


# ======================================================
# PUBLICACAO AUTOMATICA
# ======================================================
def _id_do_sistema():
    from desperta.auth.models import Administrador

    return db.session.scalar(db.select(Administrador.id).filter_by(email=EMAIL_DO_SISTEMA))


def usuario_do_sistema():
    """
    Quem assina a publicacao automatica no historico (noticia_revisao pede alguem da equipe):
    um cadastro tecnico, desativado e sem senha conhecida, entao ninguem entra com ele.
    """
    from desperta.auth.models import Administrador

    usuario = db.session.scalar(db.select(Administrador).filter_by(email=EMAIL_DO_SISTEMA))
    if usuario is None:
        usuario = Administrador(nome=NOME_DO_SISTEMA, email=EMAIL_DO_SISTEMA, papel="editor", ativo=False)
        usuario.set_senha(secrets.token_urlsafe(32))
        db.session.add(usuario)
        db.session.flush()
    return usuario


def publicada_pelo_sistema(noticia):
    """A ultima publicacao foi automatica? (transparencia em "como foi feita")."""
    from desperta.auth.models import Administrador

    quem = db.session.scalar(
        db.select(Administrador.email)
        .join(NoticiaRevisao, NoticiaRevisao.admin_id == Administrador.id)
        .where(NoticiaRevisao.noticia_id == noticia.id, NoticiaRevisao.acao == "publicou")
        .order_by(NoticiaRevisao.data_hora.desc(), NoticiaRevisao.id.desc())
        .limit(1)
    )
    return quem == EMAIL_DO_SISTEMA


@dataclass
class ResultadoDaPublicacao:
    modo: str
    conferidas: int = 0
    publicaveis: int = 0
    publicadas: int = 0
    para_a_equipe: int = 0

    def em_texto(self):
        if self.modo == "desligada":
            return "publicacao automatica desligada"
        verbo = "publicadas" if self.modo == "ligada" else "publicaria (ensaio)"
        numero = self.publicadas if self.modo == "ligada" else self.publicaveis
        return f"modo={self.modo} conferidas={self.conferidas} {verbo}={numero} " f"para_a_equipe={self.para_a_equipe}"


def candidatas():
    """Rascunhos da IA escritos na planta (frases-v3 ou boletim), sem revisao da equipe."""
    from desperta.ia.models import GeracaoIA

    na_planta = db.select(GeracaoIA.noticia_id).where(GeracaoIA.versao_prompt.in_(VERSOES_NA_PLANTA))
    return db.session.scalars(
        db.select(Noticia)
        .where(Noticia.status == "rascunho", Noticia.origem == "ia", Noticia.id.in_(na_planta))
        .order_by(Noticia.criado_em, Noticia.id)
    ).all()


def publicar_automaticas(modo=None):
    """Confere os rascunhos na planta e, no modo ligada, publica os que passam (pelo service, com historico)."""
    from .services import mudar_status

    modo = modo or current_app.config["PUBLICACAO_AUTOMATICA"]
    if modo not in MODOS:
        raise ValueError(f"PUBLICACAO_AUTOMATICA invalida: use {', '.join(MODOS)}.")
    resultado = ResultadoDaPublicacao(modo=modo)
    if modo == "desligada":
        return resultado
    for noticia in candidatas():
        resultado.conferidas += 1
        conferencia = conferir(noticia)
        if not conferencia.passou:
            resultado.para_a_equipe += 1
            continue
        resultado.publicaveis += 1
        if modo == "ligada":
            mudar_status(
                noticia,
                usuario_do_sistema(),
                "publicar",
                "Publicação automática: passou na planta da notícia e nas regras de confiança (25.18).",
            )
            resultado.publicadas += 1
    db.session.add(LogSistema(nivel="info", modulo="IA", acao="publicacao_automatica", descricao=resultado.em_texto()))
    db.session.commit()
    return resultado
