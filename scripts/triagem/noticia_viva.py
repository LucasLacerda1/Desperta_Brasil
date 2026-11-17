"""
Junta os rascunhos da mesma proposicao numa noticia viva (decisao 25.16, ponto 3; escolha do Lucas em 17/11/2026).

Para cada proposicao com mais de uma noticia aberta (rascunho ou em revisao) da IA:
- a mais antiga vira a noticia viva: o fato dela continua no topo (titulo e paragrafo principal);
- as outras entram na secao "## Atualizacoes", da mais recente para a mais antiga, com as fontes;
- as geracoes da IA passam para a noticia viva (o mesmo fato nao e escrito de novo) e as outras
  noticias sao apagadas; cada uma deixa uma linha em log_sistema (juntar_noticia_viva).
Proposicao que ja tem noticia publicada fica de fora. Tudo assinado pelo admin informado.

Uso (da raiz do projeto, com backup antes):
    python scripts/triagem/noticia_viva.py --admin email@exemplo --simular
    python scripts/triagem/noticia_viva.py --admin email@exemplo
"""

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.getcwd())

from app import app  # noqa: E402
from desperta.auth.models import Administrador  # noqa: E402
from desperta.ext.db import db  # noqa: E402
from desperta.noticias import viva  # noqa: E402
from desperta.noticias.models import Noticia  # noqa: E402
from desperta.sistema.models import LogSistema  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin", required=True, help="E-mail do admin que assina.")
    parser.add_argument("--simular", action="store_true", help="So mostra o que seria feito.")
    argumentos = parser.parse_args()

    with app.app_context():
        print(db.engine.url)
        admin = db.session.scalar(db.select(Administrador).filter_by(email=argumentos.admin.strip().lower()))
        if admin is None or admin.papel != "admin" or not admin.ativo:
            raise SystemExit(f"Nao ha admin ativo com o e-mail {argumentos.admin}.")
        abertas = db.session.scalar(
            db.select(db.func.count())
            .select_from(Noticia)
            .where(Noticia.status.in_(viva.STATUS_ABERTOS), Noticia.origem == "ia", Noticia.tipo == "noticia")
        )
        grupos, com_publicada = viva.grupos_para_juntar()
        apagadas = sum(len(lista) - 1 for lista in grupos.values())
        tamanhos = Counter(len(lista) for lista in grupos.values())
        print(f"noticias abertas da IA: {abertas}")
        print(f"proposicoes com mais de uma: {len(grupos)} (tamanhos: {dict(sorted(tamanhos.items()))})")
        print(f"proposicoes de fora por ja terem noticia publicada: {len(com_publicada)}")
        print(f"ficam {abertas - apagadas} noticias ({apagadas} rascunhos viram atualizacoes)")
        if argumentos.simular:
            maior = max(grupos.values(), key=len, default=None)
            if maior:
                print(f"\nExemplo (proposicao com {len(maior)} rascunhos), antes:")
                for noticia in maior:
                    print(f"  {noticia.id} {noticia.criado_em:%d/%m %H:%M} {noticia.titulo[:110]}")
                juntada, repetidos = viva.juntar(maior, admin)
                print(f"\n{repetidos} dos {len(maior) - 1} rascunhos juntados repetiam um fato ja contado")
                print(f"\nDepois: noticia {juntada.id}\nTITULO: {juntada.titulo}\nRESUMO: {juntada.resumo}\n")
                print(juntada.corpo[:4000])
                db.session.rollback()
            print("\nSimulacao: nada foi gravado.")
            return

        repetidos = 0
        for lista in grupos.values():
            repetidos += viva.juntar(lista, admin)[1]
            db.session.commit()
        db.session.add(
            LogSistema(
                nivel="info",
                modulo="admin",
                acao="triagem_noticia_viva",
                descricao=(
                    f"Noticia viva (25.16): {len(grupos)} proposicoes, {apagadas} rascunhos juntados "
                    f"({repetidos} repetiam um fato ja contado); "
                    f"ficaram {abertas - apagadas} noticias abertas"
                ),
                admin_id=admin.id,
            )
        )
        db.session.commit()
        print(f"Feito: {len(grupos)} noticias vivas; {apagadas} rascunhos juntados ({repetidos} repetidos).")


if __name__ == "__main__":
    main()
