"""
Gera a documentacao do modelo do banco a partir do codigo (os modelos do SQLAlchemy), para ela
nunca ficar desatualizada:

- docs/banco/MODELO_DO_BANCO.md: dicionario de dados, tabela por tabela (colunas, tipos, chaves,
  restricoes), agrupado por dominio, com a descricao do cabecalho "# === Classe (descricao) ===";
- docs/banco/diagrama-er*.dot: diagramas ER para o Graphviz (completo, dados da Camara e portal), so com
  as chaves (PK e FK), para ficar legivel.

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
        "Diagramas ER: `diagrama-er-camara.svg` (dados da Câmara), `diagrama-er-portal.svg` (portal)",
        "e `diagrama-er.svg` (completo), desenhados pelo Graphviz a partir dos `.dot` desta pasta",
        "(`dot -Tsvg diagrama-er.dot -o diagrama-er.svg`).",
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


def _rotulo_html(tabela):
    """Tabela do diagrama: nome em cima (lapis), so as colunas de chave e quantas outras ha."""
    linhas = [
        '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4" COLOR="#9c836f" BGCOLOR="#ffffff">',
        f'<TR><TD COLSPAN="2" BGCOLOR="#263b5c"><FONT COLOR="#ffffff"><B>{tabela.name}</B></FONT></TD></TR>',
    ]
    outras = 0
    for c in tabela.columns:
        if not (c.primary_key or c.foreign_keys):
            outras += 1
            continue
        marcas = " ".join(m for m, ok in (("PK", c.primary_key), ("FK", bool(c.foreign_keys))) if ok)
        linhas.append(
            f'<TR><TD PORT="{c.name}" ALIGN="LEFT">{c.name}</TD>'
            f'<TD ALIGN="LEFT"><FONT COLOR="#6d4727"><B>{marcas}</B></FONT></TD></TR>'
        )
    if outras:
        texto = f"+ {outras} {'coluna' if outras == 1 else 'colunas'}"
        linhas.append(f'<TR><TD COLSPAN="2" ALIGN="LEFT"><FONT COLOR="#5f6d73">{texto}</FONT></TD></TR>')
    linhas.append("</TABLE>>")
    return "".join(linhas)


# Fundo de cada dominio no diagrama (tons claros da paleta)
FUNDOS = {
    "proposicoes": "#f6efe6",
    "votacoes": "#eef2f7",
    "parlamentares": "#f3f0ea",
    "orgaos": "#edf3f4",
    "auth": "#f4f1ec",
    "noticias": "#f8efe6",
    "ia": "#eef1f6",
    "sistema": "#f1efec",
    "visitantes": "#f2efe9",
}


DA_CAMARA = ("proposicoes", "votacoes", "parlamentares", "orgaos")
DO_PORTAL = ("auth", "noticias", "ia", "sistema", "visitantes")


def gerar_dot(tabelas, mapa, dominios=tuple(DOMINIOS), titulo="modelo do banco de dados", direcao="TB"):
    """Diagrama ER para o Graphviz: um grupo por dominio; a ligacao sai do pai e chega no filho.

    Lado do pai: um traco (obrigatorio) ou um circulo e um traco (FK que aceita nulo).
    Lado do filho: pe de galinha com circulo (zero ou muitos).
    Tabela de fora dos dominios pedidos que e pai de alguma aparece tracejada, so com o nome.
    """
    linhas = [
        "digraph modelo_do_banco {",
        f'  graph [rankdir={direcao}, splines=true, nodesep=0.25, ranksep=0.7, pad=0.4, bgcolor="#fefdfb",'
        f' fontname="Helvetica", fontsize=22, labelloc=t, label="Desperta Brasil: {titulo}"];',
        '  node [shape=plain, fontname="Helvetica", fontsize=12];',
        '  edge [color="#956036", penwidth=1.1, arrowsize=0.8, dir=both];',
    ]
    dentro = {nome for nome in tabelas if mapa[nome][0] in dominios}
    por_dominio = defaultdict(list)
    for nome in dentro:
        por_dominio[mapa[nome][0]].append(nome)
    for dominio in dominios:
        linhas.append(
            f'  subgraph cluster_{dominio} {{ label="{DOMINIOS[dominio]}"; style="rounded,filled"; color="#d8ccbf";'
            f' fillcolor="{FUNDOS[dominio]}"; fontsize=16; fontcolor="#263b5c";'
        )
        for nome in sorted(por_dominio[dominio]):
            linhas.append(f'    "{nome}" [label={_rotulo_html(tabelas[nome])}];')
        linhas.append("  }")
    de_fora = sorted({fk.column.table.name for n in dentro for fk in tabelas[n].foreign_keys} - dentro)
    for nome in de_fora:
        linhas.append(
            f'  "{nome}" [shape=box, style="rounded,dashed", color="#9c836f", fontcolor="#5f6d73",'
            f' label="{nome}\\n({DOMINIOS[mapa[nome][0]]})"];'
        )
    for nome in sorted(dentro):
        for fk in sorted(tabelas[nome].foreign_keys, key=lambda f: f.parent.name):
            pai = fk.column.table.name
            lado_pai = "teeodot" if fk.parent.nullable else "teetee"
            origem = f'"{pai}":"{fk.column.name}"' if pai in dentro else f'"{pai}"'
            linhas.append(f'  {origem} -> "{nome}":"{fk.parent.name}" [arrowtail={lado_pai}, arrowhead=crowodot];')
    linhas.append("}")
    return "\n".join(linhas) + "\n"


def main():
    app = create_app(TestConfig)
    with app.app_context():
        tabelas = dict(db.metadata.tables)
        mapa = _tabelas()
        SAIDA.mkdir(parents=True, exist_ok=True)
        (SAIDA / "MODELO_DO_BANCO.md").write_text(gerar_markdown(tabelas, mapa), encoding="utf-8")
        diagramas = {
            "diagrama-er.dot": gerar_dot(tabelas, mapa),
            "diagrama-er-camara.dot": gerar_dot(tabelas, mapa, DA_CAMARA, "dados da Câmara (21 tabelas)", "TB"),
            "diagrama-er-portal.dot": gerar_dot(tabelas, mapa, DO_PORTAL, "tabelas do portal (11 tabelas)", "LR"),
        }
        for arquivo, conteudo in diagramas.items():
            (SAIDA / arquivo).write_text(conteudo, encoding="utf-8")
        print(f"{len(tabelas)} tabelas -> {SAIDA}")


if __name__ == "__main__":
    main()
