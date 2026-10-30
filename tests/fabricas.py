"""Monta objetos validos para os testes; cada funcao aceita campos alterados."""

from datetime import date, datetime
from types import SimpleNamespace

from desperta.auth.models import Administrador
from desperta.ia.models import GeracaoIA, GeracaoTrecho, TrechoRAG
from desperta.noticias.models import Noticia, NoticiaFonte, NoticiaRevisao
from desperta.orgaos.models import DeputadoOrgao, Evento, Orgao, PautaItem
from desperta.parlamentares.models import (
    Bloco,
    BlocoPartido,
    Deputado,
    Frente,
    FrenteMembro,
    Legislatura,
    Lideranca,
    Partido,
)
from desperta.proposicoes.models import Proposicao, ProposicaoAutor, ProposicaoTema, Tema, Tramitacao
from desperta.sistema.models import Coleta, LogSistema
from desperta.visitantes.models import Visitante, VisitanteTema
from desperta.votacoes.models import Orientacao, Votacao, VotacaoProposicao, Voto

MOMENTO = datetime(2024, 5, 14, 15, 30)
UUID_VISITANTE = "5f0d3a52-7a8e-4d7b-9a55-0b1c2d3e4f60"


def legislatura(**campos):
    return Legislatura(**{"id": 57, "data_inicio": date(2023, 2, 1), "data_fim": date(2027, 1, 31), **campos})


def partido(**campos):
    return Partido(**{"id": 37906, "sigla": "PL", "nome": "Partido Liberal", **campos})


def deputado(**campos):
    return Deputado(
        **{
            "id": 204554,
            "nome": "Fulana de Tal",
            "sigla_uf": "ES",
            "sexo": "F",
            "url_foto": "https://www.camara.leg.br/foto.jpg",
            "id_legislatura": 57,
            "sigla_partido": "PL",
            **campos,
        }
    )


def orgao(**campos):
    return Orgao(
        **{
            "id": 180,
            "sigla": "PLEN",
            "nome": "Plenario",
            "apelido": "Plenario",
            "cod_tipo_orgao": 26,
            "tipo_orgao": "Plenario Virtual",
            **campos,
        }
    )


def tema(**campos):
    return Tema(**{"cod_tema": 46, "nome": "Educacao", "icone": "school", **campos})


def proposicao(**campos):
    return Proposicao(
        **{
            "id": 2310837,
            "sigla_tipo": "PL",
            "cod_tipo": 139,
            "descricao_tipo": "Projeto de Lei",
            "numero": 1234,
            "ano": 2024,
            "ementa": "Dispoe sobre o tema.",
            "data_apresentacao": MOMENTO,
            "url_inteiro_teor": "https://www.camara.leg.br/inteiro-teor.pdf",
            "data_status": MOMENTO,
            "regime": "Ordinario",
            "apreciacao": "Plenario",
            **campos,
        }
    )


def tramitacao(**campos):
    return Tramitacao(
        **{
            "proposicao_id": 2310837,
            "sequencia": 1,
            "data_hora": MOMENTO,
            "orgao_id": 180,
            "sigla_orgao": "PLEN",
            "cod_tipo_tramitacao": "100",
            "descricao": "Apresentacao",
            "despacho": "Publique-se.",
            "regime": "Ordinario",
            "ambito": "Regimental",
            "apreciacao": "Plenario",
            **campos,
        }
    )


def evento(**campos):
    return Evento(
        **{
            "id": 70001,
            "data_hora_inicio": MOMENTO,
            "situacao": "Encerrada",
            "descricao_tipo": "Sessao Deliberativa",
            "descricao": "Sessao do Plenario",
            "orgao_id": 180,
            **campos,
        }
    )


def votacao(**campos):
    return Votacao(
        **{
            "id": "2310837-8",
            "data": date(2024, 5, 14),
            "data_hora_registro": MOMENTO,
            "orgao_id": 180,
            "sigla_orgao": "PLEN",
            "descricao": "Aprovado o projeto.",
            **campos,
        }
    )


def voto(**campos):
    return Voto(
        **{
            "votacao_id": "2310837-8",
            "deputado_id": 204554,
            "tipo_voto": "Sim",
            "data_registro": MOMENTO,
            "sigla_partido": "PL",
            **campos,
        }
    )


def administrador(**campos):
    admin = Administrador(**{"nome": "Lucas", "email": "lucas@desperta.org", **campos})
    admin.set_senha("senha-de-teste")
    return admin


def noticia(**campos):
    return Noticia(
        **{
            "titulo": "Camara aprova projeto",
            "slug": "camara-aprova-projeto",
            "resumo": "Resumo da noticia.",
            "corpo": "Texto da noticia.",
            "origem": "ia",
            "cod_tema": 46,
            **campos,
        }
    )


def trecho(**campos):
    return TrechoRAG(
        **{
            "tipo": "proposicao",
            "ref_id": "2310837",
            "parte": 1,
            "texto": "PL 1234/2024",
            "tokens": 8,
            "embedding": bytes(3072),
            "modelo_embedding": "eduagarcia/RoBERTaLexPT-base",
            "hash_texto": "a" * 64,
            **campos,
        }
    )


def coleta(**campos):
    return Coleta(**{"endpoint": "/proposicoes", "status": "ok", **campos})


def visitante(**campos):
    return Visitante(**{"id": UUID_VISITANTE, **campos})


def popular(db):
    """Grava uma linha em cada uma das 32 tabelas, na ordem das FKs."""
    d = SimpleNamespace(
        legislatura=legislatura(),
        partido=partido(),
        deputado=deputado(partido_id=37906),
        orgao=orgao(),
        tema=tema(),
        proposicao=proposicao(),
        evento=evento(),
        votacao=votacao(evento_id=70001, proposicao_id=2310837, aprovacao=True),
        admin=administrador(),
        noticia=noticia(),
        coleta=coleta(),
        trecho=trecho(),
        visitante=visitante(consentimento=True),
    )
    db.session.add_all(vars(d).values())
    db.session.flush()

    d.geracao = GeracaoIA(
        noticia_id=d.noticia.id,
        modelo_geracao="gerador-falso",
        modelo_embedding="eduagarcia/RoBERTaLexPT-base",
        consulta="educacao",
        versao_prompt="v1",
        entrada="{}",
        status="ok",
    )
    db.session.add(d.geracao)
    db.session.flush()

    db.session.add_all(
        [
            tramitacao(),
            ProposicaoAutor(
                proposicao_id=2310837,
                ordem=1,
                deputado_id=204554,
                nome="Fulana",
                cod_tipo=10000,
                tipo="Deputado",
                proponente=True,
            ),
            ProposicaoTema(proposicao_id=2310837, cod_tema=46, relevancia=1),
            voto(),
            Orientacao(
                votacao_id="2310837-8", partido_bloco="PL", tipo_lideranca="P", partido_id=37906, orientacao="Sim"
            ),
            VotacaoProposicao(votacao_id="2310837-8", proposicao_id=2310837),
            Lideranca(
                deputado_id=204554,
                bancada_nome="PL",
                bancada_tipo="partido",
                titulo="Lider",
                data_inicio=date(2024, 1, 1),
            ),
            Bloco(id=590, nome="Bloco A", federacao=False, id_legislatura=57),
            Frente(id=54000, titulo="Frente da Educacao", id_legislatura=57),
            DeputadoOrgao(
                deputado_id=204554,
                orgao_id=180,
                data_inicio=date(2023, 2, 1),
                cod_titulo="1",
                titulo="Titular",
            ),
            PautaItem(evento_id=70001, ordem=1, proposicao_id=2310837, relator_id=204554, votacao_id="2310837-8"),
            NoticiaFonte(noticia_id=d.noticia.id, tipo="votacao", ref_id="2310837-8", ordem=1),
            NoticiaRevisao(noticia_id=d.noticia.id, admin_id=d.admin.id, acao="aprovou"),
            GeracaoTrecho(geracao_id=d.geracao.id, trecho_id=d.trecho.id, posicao=1, similaridade=0.91),
            LogSistema(nivel="info", modulo="coletor", acao="coletar", descricao="ok", coleta_id=d.coleta.id),
            VisitanteTema(visitante_id=UUID_VISITANTE, cod_tema=46, acessos=3),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            BlocoPartido(bloco_id=590, partido_id=37906),
            FrenteMembro(frente_id=54000, deputado_id=204554, cod_titulo="1", titulo="Presidente"),
        ]
    )
    db.session.commit()
    return d
