"""
Triagem dos rascunhos de "mudanca de situacao" escritos antes da decisao 25.1 (14/11/2026).

Esses rascunhos diziam que a situacao tinha mudado quando a Camara so tinha registrado mais um
passo do andamento (ou nem informava a situacao). A triagem, decidida pelo Lucas em 15/11/2026:
- o passo do dia e noticia (parecer do relator, prejudicialidade, urgencia...) e nao ha rascunho
  de votacao da mesma proposicao no mesmo dia: o rascunho fica, com titulo e resumo reescritos
  a partir do passo e com o tema principal da 25.2 (um por proposicao, o mais recente);
- o resto (publicacao, prazo, apensacao, recebimento, distribuicao...) e apagado pelo service
  de exclusao (10.4): as geracoes da IA ficam registradas, sem a noticia.
Tudo passa pelos services, com o admin que assina: o historico e o log mostram quem fez.

Uso (da raiz do projeto):
    python scripts/triagem/situacao_errada.py --admin email@exemplo --simular
    python scripts/triagem/situacao_errada.py --admin email@exemplo
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.getcwd())

from app import app  # noqa: E402
from desperta.auth.models import Administrador  # noqa: E402
from desperta.ext.db import db  # noqa: E402
from desperta.ia.gerador import _cortar, _frase, _identificacao  # noqa: E402
from desperta.ia.models import GeracaoIA  # noqa: E402
from desperta.noticias import services as noticias  # noqa: E402
from desperta.noticias.models import Noticia  # noqa: E402
from desperta.orgaos.models import Orgao  # noqa: E402
from desperta.proposicoes.models import Proposicao, Tramitacao  # noqa: E402
from desperta.proposicoes.services import tema_principal  # noqa: E402
from desperta.sistema.models import LogSistema  # noqa: E402
from desperta.votacoes.models import Votacao  # noqa: E402

# Passos do andamento que sao noticia, do mais forte ao mais fraco, com o titulo de cada um
PASSOS_UTEIS = {
    "Aprovação de Proposição (Plenário)": "{id}: aprovado no Plenário",
    "Votação (Plenário)": "{id}: votado no Plenário",
    "Aprovação da Redação Final": "{id}: aprovada a redação final",
    "Declaração de Prejudicialidade": "{id}: declarada a prejudicialidade",
    "Aprovação de Urgência (154, 155 ou 64 CF)": "{id}: aprovada a urgência",
    "Aprovação do Parecer": "{id}: aprovado o parecer na {orgao}",
    "Parecer do(a) Relator(a)": "{id}: relator apresenta parecer na {orgao}",
}
COMENTARIO = (
    "Triagem de 15/11/2026 (decisao 25.1): o rascunho dizia que a situacao tinha mudado; "
    "o texto foi reescrito a partir do passo do andamento do dia."
)


def _dados(geracao):
    entrada = json.loads(geracao.entrada)
    return entrada["proposicao_id"], (entrada.get("data_status") or "")[:10]


def _situacao_mudou_naquele_dia(passos, dia):
    """Como a 25.1, mas com a situacao daquele dia (a proposicao pode ter mudado depois)."""
    ate = [p for p in passos if p.data_hora.date().isoformat() <= dia]
    antes = [p.cod_situacao for p in passos if p.data_hora.date().isoformat() < dia and p.cod_situacao is not None]
    if not ate or ate[-1].cod_situacao is None:
        return False
    return not antes or antes[-1] != ate[-1].cod_situacao


def _votacoes_com_rascunho():
    """(proposicao, dia) que ja tem rascunho de votacao: o passo do mesmo dia nao precisa de outro."""
    pares = set()
    entradas = db.session.scalars(
        db.select(GeracaoIA.entrada)
        .join(Noticia, Noticia.id == GeracaoIA.noticia_id)
        .where(Noticia.status == "rascunho", GeracaoIA.entrada.like('%"caso": "votacao"%'))
    )
    for entrada in entradas:
        dados = json.loads(entrada)
        votacao = db.session.get(Votacao, dados["votacao_id"])
        if votacao is not None:
            pares.add((dados["proposicao_id"], votacao.data.isoformat()))
    return pares


def _nome_do_orgao(passo):
    orgao = db.session.get(Orgao, passo.orgao_id)
    if orgao is not None and orgao.nome:
        return orgao.nome
    return passo.sigla_orgao or "Câmara"


def _texto(proposicao, passo, modelo):
    identificacao = _identificacao(
        type("P", (), {"sigla": proposicao.sigla_tipo, "numero": proposicao.numero, "ano": proposicao.ano})
    )
    orgao = _nome_do_orgao(passo)
    titulo = modelo.format(id=identificacao, orgao=orgao)
    detalhe = (passo.despacho or "").strip() or passo.descricao.strip()
    artigo = "no" if orgao.startswith(("Plenário", "Plenario")) else "na"
    resumo = f"Em {passo.data_hora:%d/%m/%Y}, {artigo} {orgao}: {_frase(detalhe)}"
    return _cortar(titulo, noticias.TAMANHO_TITULO), _cortar(resumo, noticias.TAMANHO_RESUMO)


def classificar():
    """Devolve (manter: {noticia_id: (proposicao, passo, modelo)}, apagar: [(noticia_id, motivo)])."""
    votacoes = _votacoes_com_rascunho()
    linhas = db.session.execute(
        db.select(Noticia.id, GeracaoIA)
        .join(GeracaoIA, GeracaoIA.noticia_id == Noticia.id)
        .where(Noticia.status == "rascunho", GeracaoIA.entrada.like('%"caso": "situacao"%'))
        .order_by(Noticia.id)
    ).all()
    candidatos, apagar = [], []
    for noticia_id, geracao in linhas:
        proposicao_id, dia = _dados(geracao)
        passos = db.session.scalars(
            db.select(Tramitacao).filter_by(proposicao_id=proposicao_id).order_by(Tramitacao.sequencia)
        ).all()
        if _situacao_mudou_naquele_dia(passos, dia):
            continue  # o rascunho estava certo: fica como esta
        do_dia = [p for p in passos if p.data_hora.date().isoformat() == dia]
        util = next(((p, PASSOS_UTEIS[d]) for d in PASSOS_UTEIS for p in reversed(do_dia) if p.descricao == d), None)
        if util is None:
            apagar.append((noticia_id, "passo burocratico"))
        elif (proposicao_id, dia) in votacoes:
            apagar.append((noticia_id, "a votacao do dia ja tem rascunho"))
        else:
            candidatos.append((dia, noticia_id, proposicao_id, util))
    manter = {}
    por_proposicao = {}
    for dia, noticia_id, proposicao_id, util in sorted(candidatos):
        if proposicao_id in por_proposicao:
            apagar.append((por_proposicao[proposicao_id], "mesma proposicao, passo mais antigo"))
            del manter[por_proposicao[proposicao_id]]
        por_proposicao[proposicao_id] = noticia_id
        manter[noticia_id] = (proposicao_id, *util)
    return manter, apagar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin", required=True, help="E-mail do admin que assina a triagem.")
    parser.add_argument("--simular", action="store_true", help="So mostra o que seria feito.")
    argumentos = parser.parse_args()

    with app.app_context():
        print(db.engine.url)
        admin = db.session.scalar(db.select(Administrador).filter_by(email=argumentos.admin.strip().lower()))
        if admin is None or admin.papel != "admin" or not admin.ativo:
            raise SystemExit(f"Nao ha admin ativo com o e-mail {argumentos.admin}.")
        manter, apagar = classificar()
        motivos = Counter(motivo for _, motivo in apagar)
        passos = Counter(passo.descricao for _, passo, _ in manter.values())
        print(f"manter e reescrever: {len(manter)} {dict(passos)}")
        print(f"apagar: {len(apagar)} {dict(motivos)}")
        exemplos = list(manter.items())[:5]
        for noticia_id, (proposicao_id, passo, modelo) in exemplos:
            titulo, resumo = _texto(db.session.get(Proposicao, proposicao_id), passo, modelo)
            print(f"  {noticia_id}: {titulo}\n      {resumo}")
        if argumentos.simular:
            print("Simulacao: nada foi gravado.")
            return

        for noticia_id, (proposicao_id, passo, modelo) in manter.items():
            noticia = db.session.get(Noticia, noticia_id)
            titulo, resumo = _texto(db.session.get(Proposicao, proposicao_id), passo, modelo)
            cod_tema = tema_principal(proposicao_id) or noticia.cod_tema
            # Rodar de novo nao reescreve nem duplica o historico: so registra quando o texto mudou
            if noticias.editar_noticia(noticia, admin, titulo=titulo, resumo=resumo, cod_tema=cod_tema):
                noticias._revisao(noticia, admin, "editou", COMENTARIO)
                db.session.commit()
        for noticia_id, _ in apagar:
            noticias.excluir_noticia(db.session.get(Noticia, noticia_id), admin)
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="admin",
                acao="triagem_situacao",
                descricao=(
                    f"Triagem dos rascunhos de situacao (25.1): {len(manter)} reescritos, "
                    f"{len(apagar)} apagados ({', '.join(f'{m}: {n}' for m, n in motivos.items())})"
                ),
                admin_id=admin.id,
            )
        )
        db.session.commit()
        print(f"Feito: {len(manter)} reescritos e {len(apagar)} apagados.")


if __name__ == "__main__":
    main()
