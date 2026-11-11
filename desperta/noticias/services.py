import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from desperta.auth.models import Administrador
from desperta.ext.api import iso, url_camara
from desperta.ext.db import db
from desperta.ext.erros import AcessoNegado, Conflito, DadosInvalidos, ErroDoPortal, NaoEncontrado
from desperta.orgaos.models import Evento, Orgao
from desperta.parlamentares.models import Deputado, Partido
from desperta.proposicoes.models import Proposicao, Tema
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import Votacao

# desperta.ia importa este modulo (criar_rascunho): os modelos da IA entram dentro das funcoes, em _ia()

from .models import (
    NOTICIA_FONTE_TIPOS,
    NOTICIA_ORIGENS,
    NOTICIA_STATUS,
    NOTICIA_TIPOS,
    Noticia,
    NoticiaFonte,
    NoticiaRevisao,
)

noticia_fts = db.table("noticia_fts", db.column("rowid"))

TAMANHO_SLUG = 220
# Caminhos fixos das rotas de /api/noticias: uma noticia nao pode ter um destes como slug
SLUGS_RESERVADOS = ("admin", "busca", "principal")
# Decisao 10.4: o fluxo normal e arquivar; apagar de verdade so estes, e so o admin
STATUS_QUE_PODEM_SER_APAGADOS = ("rascunho", "rejeitada")


def gerar_slug(titulo):
    """Sem acento, minusculo e unico; depois de publicada, a noticia nao muda de slug."""
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")[:TAMANHO_SLUG].rstrip("-") or "noticia"
    if base in SLUGS_RESERVADOS:
        base = f"{base}-noticia"
    slug = base
    numero = 2
    while db.session.scalar(db.select(Noticia.id).filter_by(slug=slug).limit(1)) is not None:
        sufixo = f"-{numero}"
        slug = base[: TAMANHO_SLUG - len(sufixo)].rstrip("-") + sufixo
        numero += 1
    return slug


def criar_rascunho(titulo, resumo, corpo, cod_tema, fontes, origem="ia"):
    """RF06: toda noticia gerada entra como rascunho; fontes sao (tipo, ref_id), a primeira e a principal."""
    noticia = Noticia(
        titulo=titulo,
        slug=gerar_slug(titulo),
        resumo=resumo,
        corpo=corpo,
        origem=origem,
        cod_tema=cod_tema,
        status="rascunho",
    )
    db.session.add(noticia)
    db.session.flush()
    db.session.add_all(
        NoticiaFonte(noticia_id=noticia.id, tipo=tipo, ref_id=ref_id, ordem=ordem)
        for ordem, (tipo, ref_id) in enumerate(fontes, start=1)
    )
    return noticia


def excluir_noticia(noticia, admin):
    """
    Apaga um rascunho ou uma noticia rejeitada (decisao 10.4). Fontes e revisoes vao junto
    (cascade do ORM); as geracoes da IA ficam, com noticia_id nulo, para o registro da IA
    continuar completo (RF15). Qualquer outro caso vira 409, nunca erro 500.
    """
    if admin.papel != "admin" or not admin.ativo:
        raise AcessoNegado("So um admin ativo pode apagar noticias.")
    if noticia.status not in STATUS_QUE_PODEM_SER_APAGADOS:
        raise Conflito(
            f"Noticia com status '{noticia.status}' nao e apagada. "
            "Use arquivar; apagar so vale para rascunho ou rejeitada."
        )
    noticia_id, titulo = noticia.id, noticia.titulo
    try:
        for geracao in list(noticia.geracoes):
            geracao.noticia_id = None
        db.session.delete(noticia)
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="admin",
                acao="excluir_noticia",
                descricao=f"Noticia apagada: {titulo}",
                admin_id=admin.id,
                entidade="noticia",
                entidade_id=str(noticia_id),
            )
        )
        db.session.commit()
    except (IntegrityError, AssertionError) as erro:
        db.session.rollback()
        raise Conflito(f"A noticia {noticia_id} esta em uso e nao foi apagada.") from erro


def _termo_para_match(termo):
    """Cada palavra vira uma frase entre aspas, para nao quebrar a sintaxe do MATCH."""
    palavras = (termo or "").split()
    return " ".join('"' + palavra.replace('"', '""') + '"' for palavra in palavras)


def buscar_noticias(termo, inicio=None, fim=None, cod_tema=None):
    """
    Busca nas noticias publicadas, por relevancia e depois pela mais recente.
    inicio e fim comparam com publicado_em (UTC); fim sem hora inclui o dia inteiro.
    """
    match = _termo_para_match(termo)
    if not match:
        return []

    consulta = (
        db.select(Noticia)
        .join(noticia_fts, noticia_fts.c.rowid == Noticia.id)
        .where(db.text("noticia_fts MATCH :termo").bindparams(termo=match))
        .where(Noticia.status == "publicada")
    )
    if inicio is not None:
        consulta = consulta.where(Noticia.publicado_em >= inicio)
    if fim is not None:
        if isinstance(fim, datetime):
            consulta = consulta.where(Noticia.publicado_em <= fim)
        else:
            consulta = consulta.where(Noticia.publicado_em < fim + timedelta(days=1))
    if cod_tema is not None:
        consulta = consulta.where(Noticia.cod_tema == cod_tema)

    consulta = consulta.order_by(db.func.bm25(db.literal_column("noticia_fts")), Noticia.publicado_em.desc())
    return list(db.session.scalars(consulta))


# ======================================================
# PORTAL: NOTICIAS PUBLICADAS (RF10, RF11, RF12, RF18)
# ======================================================
LIMITE_DA_BUSCA = 500
URL_PAGINA = {
    "proposicao": "https://www.camara.leg.br/propostas-legislativas/{}",
    "deputado": "https://www.camara.leg.br/deputados/{}",
    "evento": "https://www.camara.leg.br/evento-legislativo/{}",
}
URL_API = {
    "proposicao": "proposicoes/{}",
    "votacao": "votacoes/{}",
    "deputado": "deputados/{}",
    "evento": "eventos/{}",
    "orgao": "orgaos/{}",
    "partido": "partidos/{}",
}


def _ia():
    from desperta.ia import models

    return models


def _tema_dict(tema):
    return {"cod_tema": tema.cod_tema, "nome": tema.nome, "icone": tema.icone} if tema else None


def como_cartao(noticia):
    """O que aparece na lista e na pagina principal."""
    return {
        "id": noticia.id,
        "titulo": noticia.titulo,
        "slug": noticia.slug,
        "resumo": noticia.resumo,
        "tipo": noticia.tipo,
        "tema": _tema_dict(noticia.tema),
        "publicado_em": iso(noticia.publicado_em),
        "alterado_em": iso(noticia.alterado_em),
        "visualizacoes": noticia.visualizacoes,
    }


def fontes_com_links(noticia):
    """Fontes na ordem; a primeira e a fonte oficial principal (RF18)."""
    saida = []
    for fonte in noticia.fontes:
        pagina = URL_PAGINA.get(fonte.tipo)
        api = URL_API.get(fonte.tipo)
        saida.append(
            {
                "tipo": fonte.tipo,
                "ref_id": fonte.ref_id,
                "ordem": fonte.ordem,
                "url_pagina": pagina.format(fonte.ref_id) if pagina else None,
                "url_dados_abertos": url_camara(api.format(fonte.ref_id)) if api else None,
            }
        )
    return saida


def como_foi_feita(noticia):
    """Transparencia (22.5): quem escreveu, quem revisou e publicou."""
    ia = _ia()
    geracao = db.session.scalar(
        db.select(ia.GeracaoIA)
        .filter_by(noticia_id=noticia.id, status="ok")
        .order_by(ia.GeracaoIA.id.desc())
        .limit(1)
    )
    publicou = db.session.execute(
        db.select(Administrador.nome, NoticiaRevisao.data_hora)
        .join(Administrador, Administrador.id == NoticiaRevisao.admin_id)
        .where(NoticiaRevisao.noticia_id == noticia.id, NoticiaRevisao.acao == "publicou")
        .order_by(NoticiaRevisao.data_hora.desc())
        .limit(1)
    ).first()
    revisoes = db.session.scalar(
        db.select(db.func.count()).select_from(NoticiaRevisao).filter_by(noticia_id=noticia.id)
    )
    return {
        "origem": noticia.origem,
        "gerador": geracao.modelo_geracao if geracao else None,
        "revisoes": revisoes,
        "publicada_por": publicou.nome if publicou else None,
        "publicada_em": iso(publicou.data_hora) if publicou else iso(noticia.publicado_em),
    }


def como_completa(noticia):
    dados = como_cartao(noticia)
    dados.update(
        {"corpo": noticia.corpo, "fontes": fontes_com_links(noticia), "como_foi_feita": como_foi_feita(noticia)}
    )
    return dados


def _publicadas():
    return db.select(Noticia).where(Noticia.status == "publicada")


def listar_publicadas(cod_tema=None, pagina=1, por_pagina=20):
    """RF11: por tema, da mais recente para a mais antiga."""
    consulta = _publicadas()
    if cod_tema is not None:
        consulta = consulta.where(Noticia.cod_tema == cod_tema)
    total = db.session.scalar(db.select(db.func.count()).select_from(consulta.subquery()))
    itens = db.session.scalars(
        consulta.order_by(Noticia.publicado_em.desc(), Noticia.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    ).all()
    return itens, total


def pagina_principal(por_tema=3):
    """
    RF10: as principais de cada tema, com o tema da publicacao mais recente primeiro.
    A ordem pelos temas que o visitante mais le entra com o cookie (RF13, RF17).
    """
    temas = db.session.execute(
        db.select(Tema, db.func.max(Noticia.publicado_em).label("ultima"))
        .join(Noticia, Noticia.cod_tema == Tema.cod_tema)
        .where(Noticia.status == "publicada")
        .group_by(Tema.cod_tema)
        .order_by(db.text("ultima DESC"))
    ).all()
    secoes = []
    for tema, _ in temas:
        noticias = db.session.scalars(
            _publicadas().where(Noticia.cod_tema == tema.cod_tema).order_by(Noticia.publicado_em.desc()).limit(por_tema)
        ).all()
        secoes.append({"tema": _tema_dict(tema), "noticias": [como_cartao(n) for n in noticias]})
    return secoes


def buscar_publicadas(termo, inicio=None, fim=None, cod_tema=None, pagina=1, por_pagina=20):
    """RF12: busca por palavras com periodo (inicio incluso, fim exclusivo, em UTC)."""
    if not (termo or "").strip():
        raise DadosInvalidos("Informe o que buscar.")
    fim_incluso = fim - timedelta(microseconds=1) if fim is not None else None
    achadas = buscar_noticias(termo, inicio, fim_incluso, cod_tema)[:LIMITE_DA_BUSCA]
    inicio_da_pagina = (pagina - 1) * por_pagina
    return achadas[inicio_da_pagina:inicio_da_pagina + por_pagina], len(achadas)


def publicada_pelo_slug(slug):
    noticia = db.session.scalar(_publicadas().where(Noticia.slug == slug))
    if noticia is None:
        raise NaoEncontrado("Noticia nao encontrada.")
    return noticia


def contar_visualizacao(noticia):
    """RF18: +1 direto no banco, sem mexer em alterado_em."""
    db.session.execute(
        db.update(Noticia).where(Noticia.id == noticia.id).values(visualizacoes=Noticia.visualizacoes + 1)
    )
    db.session.commit()
    db.session.refresh(noticia)


# ======================================================
# AREA ADMINISTRATIVA: REVISAO (RF16)
# ======================================================
TAMANHO_TITULO = 200
TAMANHO_RESUMO = 500
TAMANHO_COMENTARIO = 2000
LOTE_MAXIMO = 200
CASOS_DA_IA = ("votacao", "situacao", "nova")
# acao da rota: (status de onde pode sair, status novo, acao gravada em noticia_revisao)
TRANSICOES = {
    "aprovar": (("rascunho",), "em_revisao", "aprovou"),
    "publicar": (("rascunho", "em_revisao"), "publicada", "publicou"),
    "rejeitar": (("rascunho", "em_revisao"), "rejeitada", "rejeitou"),
    "arquivar": (("rascunho", "em_revisao", "publicada"), "arquivada", "arquivou"),
}
STATUS_QUE_PODEM_SER_EDITADOS = ("rascunho", "em_revisao", "publicada")


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _texto(valor, nome, tamanho=None):
    if not isinstance(valor, str) or not valor.strip():
        raise DadosInvalidos(f"O campo {nome} e obrigatorio.")
    valor = valor.strip()
    if tamanho and len(valor) > tamanho:
        raise DadosInvalidos(f"O campo {nome} passa de {tamanho} caracteres.")
    return valor


def _comentario(valor, obrigatorio=False):
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if obrigatorio:
            raise DadosInvalidos("Escreva o motivo: ele volta para melhorar a IA.")
        return None
    if not isinstance(valor, str) or len(valor) > TAMANHO_COMENTARIO:
        raise DadosInvalidos(f"O comentario passa de {TAMANHO_COMENTARIO} caracteres.")
    return valor.strip()


def _tema_valido(cod_tema):
    if not isinstance(cod_tema, int) or isinstance(cod_tema, bool) or db.session.get(Tema, cod_tema) is None:
        raise DadosInvalidos("Tema invalido.")
    return cod_tema


def _revisao(noticia, admin, acao, comentario=None):
    db.session.add(NoticiaRevisao(noticia_id=noticia.id, admin_id=admin.id, acao=acao, comentario=comentario))


def buscar_para_revisao(noticia_id):
    noticia = db.session.get(Noticia, noticia_id)
    if noticia is None:
        raise NaoEncontrado("Noticia nao encontrada.")
    return noticia


def listar_para_revisao(status=None, cod_tema=None, caso=None, origem=None, pagina=1, por_pagina=20):
    """Fila da equipe: mais antigas primeiro, para nada ficar esquecido; caso = votacao, situacao ou nova."""
    ia = _ia()
    consulta = db.select(Noticia)
    if status is not None:
        if status not in NOTICIA_STATUS:
            raise DadosInvalidos(f"Status invalido: use {', '.join(NOTICIA_STATUS)}.")
        consulta = consulta.where(Noticia.status == status)
    if origem is not None:
        if origem not in NOTICIA_ORIGENS:
            raise DadosInvalidos(f"Origem invalida: use {', '.join(NOTICIA_ORIGENS)}.")
        consulta = consulta.where(Noticia.origem == origem)
    if cod_tema is not None:
        consulta = consulta.where(Noticia.cod_tema == cod_tema)
    if caso is not None:
        if caso not in CASOS_DA_IA:
            raise DadosInvalidos(f"Caso invalido: use {', '.join(CASOS_DA_IA)}.")
        # O caso fica no JSON de entrada da geracao; LIKE serve em qualquer banco (11.1)
        consulta = consulta.where(
            Noticia.id.in_(
                db.select(ia.GeracaoIA.noticia_id).where(ia.GeracaoIA.entrada.like(f'%"caso": "{caso}"%'))
            )
        )
    total = db.session.scalar(db.select(db.func.count()).select_from(consulta.subquery()))
    itens = db.session.scalars(
        consulta.order_by(Noticia.criado_em, Noticia.id).offset((pagina - 1) * por_pagina).limit(por_pagina)
    ).all()
    return itens, total


def como_item_de_revisao(noticia):
    dados = como_cartao(noticia)
    dados.update({"status": noticia.status, "origem": noticia.origem, "criado_em": iso(noticia.criado_em)})
    return dados


def como_detalhe_de_revisao(noticia):
    """Tudo o que a equipe precisa para revisar: texto, fontes, historico e o que a IA usou."""
    ia = _ia()
    dados = como_item_de_revisao(noticia)
    dados.update({"corpo": noticia.corpo, "fontes": fontes_com_links(noticia)})
    dados["revisoes"] = [
        {
            "acao": r.acao,
            "comentario": r.comentario,
            "data_hora": iso(r.data_hora),
            "administrador": r.administrador.nome if r.administrador else None,
        }
        for r in noticia.revisoes
    ]
    geracoes = []
    for geracao in sorted(noticia.geracoes, key=lambda g: g.id):
        trechos = db.session.execute(
            db.select(
                ia.GeracaoTrecho.posicao,
                ia.GeracaoTrecho.similaridade,
                ia.TrechoRAG.tipo,
                ia.TrechoRAG.ref_id,
                ia.TrechoRAG.texto,
            )
            .join(ia.TrechoRAG, ia.TrechoRAG.id == ia.GeracaoTrecho.trecho_id)
            .where(ia.GeracaoTrecho.geracao_id == geracao.id)
            .order_by(ia.GeracaoTrecho.posicao)
        ).all()
        try:
            entrada = json.loads(geracao.entrada)
        except ValueError:
            entrada = geracao.entrada
        geracoes.append(
            {
                "id": geracao.id,
                "status": geracao.status,
                "modelo_geracao": geracao.modelo_geracao,
                "modelo_embedding": geracao.modelo_embedding,
                "versao_prompt": geracao.versao_prompt,
                "consulta": geracao.consulta,
                "entrada": entrada,
                "duracao_ms": geracao.duracao_ms,
                "criado_em": iso(geracao.criado_em),
                "trechos": [
                    {"posicao": t.posicao, "nota": t.similaridade, "tipo": t.tipo, "ref_id": t.ref_id, "texto": t.texto}
                    for t in trechos
                ],
            }
        )
    dados["geracoes"] = geracoes
    return dados


def criar_pela_equipe(admin, titulo, resumo, corpo, cod_tema, fontes=None, tipo="noticia"):
    """Noticia escrita pela equipe: entra como rascunho, como as da IA."""
    if tipo not in NOTICIA_TIPOS:
        raise DadosInvalidos(f"Tipo invalido: use {', '.join(NOTICIA_TIPOS)}.")
    lista = []
    for fonte in fontes or []:
        if not isinstance(fonte, dict) or fonte.get("tipo") not in NOTICIA_FONTE_TIPOS:
            raise DadosInvalidos(f"Fonte invalida: o tipo precisa ser um de {', '.join(NOTICIA_FONTE_TIPOS)}.")
        ref = str(fonte.get("ref_id") or "").strip()
        if not ref or len(ref) > 20:
            raise DadosInvalidos("Fonte invalida: ref_id obrigatorio, com ate 20 caracteres.")
        if not _fonte_existe(fonte["tipo"], ref):
            raise DadosInvalidos(f"Fonte nao encontrada no banco: {fonte['tipo']} {ref}.")
        lista.append((fonte["tipo"], ref))
    noticia = criar_rascunho(
        _texto(titulo, "titulo", TAMANHO_TITULO),
        _texto(resumo, "resumo", TAMANHO_RESUMO),
        _texto(corpo, "corpo"),
        _tema_valido(cod_tema),
        lista,
        origem="equipe",
    )
    noticia.tipo = tipo
    _revisao(noticia, admin, "editou", "Escrita pela equipe.")
    db.session.commit()
    return noticia


def _fonte_existe(tipo, ref_id):
    """noticia_fonte nao tem FK (5.1): o back-end confere se o registro existe."""
    modelos = {
        "proposicao": Proposicao, "deputado": Deputado, "evento": Evento, "orgao": Orgao, "partido": Partido,
    }
    if tipo == "votacao":
        return db.session.get(Votacao, ref_id) is not None
    if not ref_id.isdigit():
        return False
    return db.session.get(modelos[tipo], int(ref_id)) is not None


def editar_noticia(noticia, admin, titulo=None, resumo=None, corpo=None, cod_tema=None):
    """Muda o texto; alterado_em so muda se algo mudou. O slug acompanha o titulo ate publicar."""
    if noticia.status not in STATUS_QUE_PODEM_SER_EDITADOS:
        raise Conflito(f"Noticia com status '{noticia.status}' nao e editada.")
    mudou = []
    if titulo is not None and _texto(titulo, "titulo", TAMANHO_TITULO) != noticia.titulo:
        noticia.titulo = titulo.strip()
        if noticia.status != "publicada":
            noticia.slug = gerar_slug(noticia.titulo)
        mudou.append("titulo")
    if resumo is not None and _texto(resumo, "resumo", TAMANHO_RESUMO) != noticia.resumo:
        noticia.resumo = resumo.strip()
        mudou.append("resumo")
    if corpo is not None and _texto(corpo, "corpo") != noticia.corpo:
        noticia.corpo = corpo.strip()
        mudou.append("corpo")
    if cod_tema is not None and _tema_valido(cod_tema) != noticia.cod_tema:
        noticia.cod_tema = cod_tema
        mudou.append("tema")
    if not mudou:
        return False
    noticia.alterado_em = _agora()
    _revisao(noticia, admin, "editou", f"Mudou: {', '.join(mudou)}.")
    db.session.commit()
    return True


def mudar_status(noticia, admin, acao, comentario=None):
    """Fluxo: rascunho -> em_revisao -> publicada, ou rejeitada / arquivada (RF16)."""
    if acao not in TRANSICOES:
        raise DadosInvalidos(f"Acao invalida: use {', '.join(TRANSICOES)}.")
    de_onde, status_novo, registro = TRANSICOES[acao]
    comentario = _comentario(comentario, obrigatorio=acao == "rejeitar")
    if noticia.status not in de_onde:
        raise Conflito(f"Nao da para {acao} uma noticia com status '{noticia.status}'.")
    noticia.status = status_novo
    if status_novo == "publicada" and noticia.publicado_em is None:
        noticia.publicado_em = _agora()
    _revisao(noticia, admin, registro, comentario)
    db.session.commit()
    return noticia


def mudar_status_em_lote(ids, admin, acao, comentario=None):
    """A mesma acao em varias noticias; cada uma e independente: as que nao podem ficam listadas com o motivo."""
    if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        raise DadosInvalidos("Envie 'ids' como uma lista de numeros.")
    if len(ids) > LOTE_MAXIMO:
        raise DadosInvalidos(f"No maximo {LOTE_MAXIMO} noticias por vez.")
    feitas, falhas = [], []
    for noticia_id in dict.fromkeys(ids):
        try:
            mudar_status(buscar_para_revisao(noticia_id), admin, acao, comentario)
            feitas.append(noticia_id)
        except ErroDoPortal as erro:
            db.session.rollback()
            falhas.append({"id": noticia_id, "erro": erro.mensagem})
    return feitas, falhas
