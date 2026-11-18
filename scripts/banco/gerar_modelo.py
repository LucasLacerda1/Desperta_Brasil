"""
Gera a documentacao do modelo do banco a partir do codigo (os modelos do SQLAlchemy), para ela
nunca ficar desatualizada:

- docs/banco/MODELO_DO_BANCO.md: dicionario de dados, tabela por tabela (colunas, tipos, chaves,
  restricoes), agrupado por dominio, com a descricao do cabecalho "# === Classe (descricao) ===";
- docs/banco/diagrama-er.dot: o diagrama entidade-relacionamento completo para o Graphviz (todas as
  tabelas, colunas, tipos, chaves e relacionamentos, com a classificacao de cada entidade).

Uso, na pasta do projeto:  python scripts/banco/gerar_modelo.py
"""

import inspect
import re
from collections import defaultdict
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

from desperta import create_app
from desperta.config import TestConfig
from desperta.ext.db import db

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / "docs" / "banco"

# Ordem e nome de cada dominio (pacote de desperta/)
DOMINIOS = {
    "proposicoes": "Proposições (API da Câmara)",
    "votacoes": "Votações (API da Câmara)",
    "parlamentares": "Parlamentares (API da Câmara)",
    "orgaos": "Órgãos e eventos (API da Câmara)",
    "auth": "Equipe (portal)",
    "noticias": "Notícias (portal)",
    "ia": "IA e busca (portal)",
    "sistema": "Sistema (portal)",
    "visitantes": "Visitantes (portal)",
}


def _descricoes(modulo):
    """'# === Classe (descricao) ===' de cada classe do models.py."""
    texto = inspect.getsource(modulo)
    return {m.group(1): m.group(2) for m in re.finditer(r"#\s*===\s*(\w+)\s*\((.+?)\)\s*===", texto)}


def _tabelas():
    mapa = {}
    for mapper in db.Model.registry.mappers:
        classe = mapper.class_
        dominio = classe.__module__.split(".")[1]
        modulo = inspect.getmodule(classe)
        mapa[mapper.local_table.name] = (dominio, classe.__name__, _descricoes(modulo).get(classe.__name__, ""))
    return mapa


def _tipo(coluna):
    return str(coluna.type).upper()


def _restricoes(tabela):
    linhas = []
    for r in sorted(tabela.constraints, key=lambda r: str(r.name)):
        if isinstance(r, UniqueConstraint):
            linhas.append(f"`{r.name}`: única ({', '.join(c.name for c in r.columns)})")
        elif isinstance(r, CheckConstraint):
            linhas.append(f"`{r.name}`: {r.sqltext}")
    return linhas


def gerar_markdown(tabelas, mapa):
    por_dominio = defaultdict(list)
    for nome, tabela in tabelas.items():
        por_dominio[mapa[nome][0]].append(tabela)
    total_colunas = sum(len(t.columns) for t in tabelas.values())
    total_fks = sum(len(t.foreign_keys) for t in tabelas.values())

    md = [
        "# Modelo do banco de dados",
        "",
        "Gerado a partir do código (`python scripts/banco/gerar_modelo.py`), então vale sempre o que está nos",
        "`models.py`. Banco SQLite com Flask-SQLAlchemy; mudanças no esquema só por migração (Flask-Migrate).",
        "",
        f"**{len(tabelas)} tabelas, {total_colunas} colunas e {total_fks} chaves estrangeiras.** "
        "As 21 tabelas da API da Câmara usam os mesmos ids da API "
        "(reprocessar uma coleta atualiza em vez de duplicar).",
        "",
        "Legenda: **PK** chave primária · **FK** chave estrangeira · **Nulo** = a coluna aceita valor vazio.",
        "",
        "Diagrama entidade-relacionamento completo: `diagrama-er.svg`, desenhado pelo Graphviz a partir de",
        "`diagrama-er.dot` (`dot -Tsvg diagrama-er.dot -o diagrama-er.svg`).",
        "",
        "Classificação das entidades: **forte** (chave primária própria, existe sozinha), **associativa**",
        "(resolve um relacionamento N:N) e **fraca** (só existe ligada à tabela pai; a chave primária inclui a",
        "FK do pai). Nenhuma é abstrata: o modelo não tem generalização/especialização (herança).",
        "",
        "`noticia_fonte` e `trecho_rag` não têm FK para as tabelas da Câmara: guardam `tipo` + `ref_id`,",
        "e o back-end confere se o registro existe.",
        "",
    ]
    for dominio, titulo in DOMINIOS.items():
        md += [f"## {titulo}", ""]
        for tabela in sorted(por_dominio[dominio], key=lambda t: t.name):
            _, classe, descricao = mapa[tabela.name]
            md += [f"### `{tabela.name}` ({classe})", ""]
            if descricao:
                md += [descricao[0].upper() + descricao[1:] + ".", ""]
            md += [f"Classificação: {FAIXA[classificacao(tabela.name)][1]}.", ""]
            md += ["| Coluna | Tipo | Nulo | Chave |", "|---|---|---|---|"]
            for c in tabela.columns:
                chave = []
                if c.primary_key:
                    chave.append("PK")
                for fk in c.foreign_keys:
                    chave.append(f"FK → `{fk.column.table.name}.{fk.column.name}`")
                if c.index:
                    chave.append("índice")
                md.append(f"| `{c.name}` | {_tipo(c)} | {'sim' if c.nullable else 'não'} | {', '.join(chave)} |")
            restricoes = _restricoes(tabela)
            if restricoes:
                md += ["", "Restrições: " + "; ".join(restricoes) + "."]
            md.append("")
    return "\n".join(md)


# Classificacao das entidades (a mesma do modelo do grupo de 28/10, com as tabelas novas da IA).
# Nenhuma e abstrata: o modelo nao tem generalizacao/especializacao (heranca).
ASSOCIATIVAS = (
    "proposicao_autor",
    "proposicao_tema",
    "voto",
    "votacao_proposicao",
    "deputado_orgao",
    "bloco_partido",
    "frente_membro",
    "noticia_revisao",
    "visitante_tema",
    "geracao_trecho",
)
FRACAS = ("tramitacao", "orientacao", "pauta_item", "noticia_fonte")
DA_CAMARA = ("proposicoes", "votacoes", "parlamentares", "orgaos")

# Cabecalho azul (espelha a API da Camara) ou verde (proprio do portal); faixa de cada classificacao
COR_CAMARA = "#1f4f99"
COR_PORTAL = "#2b7148"
FAIXA = {
    "forte": ("#e8edf5", "entidade forte"),
    "associativa": ("#fbe7b5", "entidade associativa"),
    "fraca": ("#e4def4", "entidade fraca"),
}


def classificacao(nome):
    if nome in ASSOCIATIVAS:
        return "associativa"
    if nome in FRACAS:
        return "fraca"
    return "forte"


def _unicas(tabela):
    """Colunas que sozinhas sao unicas (chave alternativa)."""
    unicas = {c.name for c in tabela.columns if c.unique}
    for r in tabela.constraints:
        if isinstance(r, UniqueConstraint) and len(r.columns) == 1:
            unicas |= {c.name for c in r.columns}
    return unicas


def _tabela_html(tabela, dominio):
    """Todas as colunas: chave (PK, FK, UQ), nome (? = aceita nulo) e tipo."""
    tipo_entidade = classificacao(tabela.name)
    cor = COR_CAMARA if dominio in DA_CAMARA else COR_PORTAL
    fundo, texto_faixa = FAIXA[tipo_entidade]
    borda = "0" if tipo_entidade == "associativa" else "1"  # a associativa ganha a moldura tracejada no no
    html = (
        f'<TABLE BORDER="{borda}" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" COLOR="#3d4650"'
        ' BGCOLOR="#ffffff">'
        f'<TR><TD COLSPAN="4" BGCOLOR="{cor}" CELLPADDING="5"><FONT COLOR="#ffffff" POINT-SIZE="15">'
        f"<B>{tabela.name}</B></FONT></TD></TR>"
        f'<TR><TD COLSPAN="4" BGCOLOR="{fundo}"><FONT POINT-SIZE="11">«{texto_faixa}»</FONT></TD></TR>'
    )
    unicas = _unicas(tabela)
    for c in tabela.columns:
        marcas = [m for m, ok in (("PK", c.primary_key), ("FK", bool(c.foreign_keys)), ("UQ", c.name in unicas)) if ok]
        nome = f"<B>{c.name}</B>" if c.primary_key else c.name
        if c.nullable and not c.primary_key:
            nome += '<FONT COLOR="#b0491c"><B> ?</B></FONT>'
        chave = f'<FONT COLOR="#8a4f12" POINT-SIZE="11"><B>{" ".join(marcas)}</B></FONT>' if marcas else " "
        html += (
            f'<TR><TD ALIGN="LEFT">{chave}</TD>'
            f'<TD ALIGN="LEFT">{nome}</TD><TD WIDTH="14"> </TD>'
            f'<TD ALIGN="LEFT"><FONT COLOR="#56626c" POINT-SIZE="11">{_tipo(c)}</FONT></TD></TR>'
        )
    html += "</TABLE>"
    if tipo_entidade == "fraca":  # moldura dupla, como no DER
        moldura = '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" COLOR="#3d4650">'
        html = f"{moldura}<TR><TD>{html}</TD></TR></TABLE>"
    return f"<{html}>"


def _legenda(tabelas):
    contagem = defaultdict(int)
    for nome in tabelas:
        contagem[classificacao(nome)] += 1
    total_fks = sum(len(t.foreign_keys) for t in tabelas.values())
    linhas = [
        ("<B>Legenda</B>", ""),
        (f'<FONT COLOR="{COR_CAMARA}"><B>azul</B></FONT>', "tabela que espelha a API da Câmara (21)"),
        (f'<FONT COLOR="{COR_PORTAL}"><B>verde</B></FONT>', "tabela própria do portal (11)"),
        ("«entidade forte»", f"chave primária própria, existe sozinha ({contagem['forte']})"),
        ("«entidade associativa»", f"borda tracejada: resolve um N:N ({contagem['associativa']})"),
        ("«entidade fraca»", f"borda dupla: só existe ligada à tabela pai ({contagem['fraca']})"),
        ("entidade abstrata", "nenhuma: o modelo não tem herança"),
        ("<B>PK</B> · <B>FK</B> · <B>UQ</B>", "chave primária · chave estrangeira · valor único"),
        ("<B>negrito</B> · <B>?</B>", "faz parte da PK · aceita nulo"),
        ("||-------o&lt;", "exatamente um para zero ou muitos (FK obrigatória)"),
        ("o|-------o&lt;", "zero ou um para zero ou muitos (FK que aceita nulo)"),
        ("tipo + ref_id", "noticia_fonte e trecho_rag apontam para a Câmara sem FK"),
        ("<B>Total</B>", f"{len(tabelas)} tabelas · {total_fks} relacionamentos 1:N · 10 N:N"),
    ]
    html = '<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#3d4650" BGCOLOR="#ffffff">'
    for a, b in linhas:
        b = f'<FONT COLOR="#3d4650">{b}</FONT>' if b else " "
        html += f'<TR><TD ALIGN="LEFT">{a}</TD><TD ALIGN="LEFT">{b}</TD></TR>'
    return f"<{html}</TABLE>>"


def gerar_dot(tabelas, mapa):
    """DER completo para o Graphviz: todas as tabelas, colunas e relacionamentos, linhas em angulo reto.

    A ligacao sai do pai e chega no filho. Lado do pai: um traco (FK obrigatoria) ou circulo e traco
    (FK que aceita nulo). Lado do filho: pe de galinha com circulo (zero ou muitos).
    """
    linhas = [
        "digraph modelo_do_banco {",
        '  graph [rankdir=TB, splines=ortho, nodesep=0.7, ranksep=1.1, pad=0.5, bgcolor="#ffffff",'
        ' fontname="Helvetica", fontsize=30, labelloc=t,'
        ' label="Desperta Brasil: diagrama entidade-relacionamento do banco de dados\\n "];',
        '  node [shape=plain, fontname="Helvetica", fontsize=13];',
        '  edge [color="#4a5560", penwidth=1.3, arrowsize=0.9, dir=both];',
        f"  legenda [label={_legenda(tabelas)}];",
    ]
    for nome in sorted(tabelas):
        moldura = (
            ' shape=box, style="dashed", penwidth=1.6, margin=0.04, color="#3d4650",' if nome in ASSOCIATIVAS else ""
        )
        linhas.append(f'  "{nome}" [{moldura} label={_tabela_html(tabelas[nome], mapa[nome][0])}];')
    for nome in sorted(tabelas):
        for fk in sorted(tabelas[nome].foreign_keys, key=lambda f: f.parent.name):
            lado_pai = "teeodot" if fk.parent.nullable else "teetee"
            pai = fk.column.table.name
            linhas.append(f'  "{pai}" -> "{nome}" [arrowtail={lado_pai}, arrowhead=crowodot];')
    linhas.append("}")
    return "\n".join(linhas) + "\n"


def main():
    app = create_app(TestConfig)
    with app.app_context():
        tabelas = dict(db.metadata.tables)
        mapa = _tabelas()
        SAIDA.mkdir(parents=True, exist_ok=True)
        (SAIDA / "MODELO_DO_BANCO.md").write_text(gerar_markdown(tabelas, mapa), encoding="utf-8")
        (SAIDA / "diagrama-er.dot").write_text(gerar_dot(tabelas, mapa), encoding="utf-8")
        print(f"{len(tabelas)} tabelas -> {SAIDA}")


if __name__ == "__main__":
    main()
