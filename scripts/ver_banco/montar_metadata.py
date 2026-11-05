"""
Monta scripts/ver_banco/metadata.json, a configuracao do Datasette usada por `invoke ver-banco`.
So para ver o banco durante o desenvolvimento: nao faz parte do portal.
Rodar de novo depois de mudar este arquivo: python scripts/ver_banco/montar_metadata.py
"""

import json
import os

PASTA = os.path.dirname(os.path.abspath(__file__))
BANCOS = ("desperta", "desperta-amostra")

# ----------------------------------------------------------
# Tabelas, agrupadas como no modelo (secao 5 do CLAUDE.md)
# ----------------------------------------------------------
GRUPOS = {
    "Proposições": {
        "proposicao": "Projetos de lei, PECs e outras propostas, com os mesmos ids da API da Câmara",
        "tramitacao": "Cada passo do andamento de uma proposição",
        "proposicao_autor": "Quem assina cada proposição, na ordem de assinatura",
        "proposicao_tema": "Temas oficiais de cada proposição",
        "tema": "Os 32 temas oficiais da Câmara, usados como categorias do portal",
    },
    "Votações": {
        "votacao": "Deliberações em Plenário ou comissão (id em texto, como 2645346-18)",
        "voto": "Voto de cada deputado; vazio na votação secreta",
        "orientacao": "Orientação de partidos e blocos nas votações do Plenário",
        "votacao_proposicao": "Proposições afetadas por cada votação",
    },
    "Parlamentares": {
        "deputado": "Deputados, com o partido e a legislatura mais recentes",
        "partido": "Partidos (a sigla não é única; as ligações são pelo id)",
        "legislatura": "Legislaturas e datas",
        "lideranca": "Líderes e vice-líderes das bancadas",
        "bloco": "Blocos parlamentares",
        "bloco_partido": "Partidos de cada bloco (composição atual)",
        "frente": "Frentes parlamentares",
        "frente_membro": "Membros de cada frente",
    },
    "Órgãos e eventos": {
        "orgao": "Plenário, comissões e Mesa Diretora",
        "deputado_orgao": "Cargos dos deputados nos órgãos (composição atual)",
        "evento": "Sessões e reuniões",
        "pauta_item": "Itens da pauta de cada evento",
    },
    "Portal": {
        "noticia": "Notícias e relatórios; os rascunhos entram aqui",
        "noticia_fonte": "Registros da API usados em cada notícia",
        "noticia_revisao": "Histórico de revisão das notícias",
        "administrador": "Equipe do portal (vazia até a Fase 4)",
        "visitante": "Visitantes anônimos (vazia até a Fase 5)",
        "visitante_tema": "Temas mais lidos por visitante",
    },
    "IA e busca": {
        "trecho_rag": "O que a Roberta lê: trechos de texto com o vetor da RoBERTaLexPT (tem busca por palavras)",
        "geracao_ia": "Cada execução da geração de rascunhos, mesmo com erro",
        "geracao_trecho": "Trechos usados em cada geração",
    },
    "Sistema": {
        "coleta": "Cada coleta da API: período, itens, requisições e status",
        "log_sistema": "Log do coletor, da IA e da equipe",
        "alembic_version": "Versão do esquema (última migração aplicada)",
    },
}

# Coluna mostrada no lugar do id quando outra tabela aponta para esta
ROTULOS = {
    "deputado": "nome",
    "partido": "sigla",
    "orgao": "sigla",
    "tema": "nome",
    "proposicao": "ementa",
    "evento": "descricao",
    "votacao": "descricao",
    "frente": "titulo",
    "bloco": "nome",
    "administrador": "nome",
    "noticia": "titulo",
    "coleta": "recurso",
}

# Filtros rapidos mostrados no topo de cada tabela
FILTROS = {
    "proposicao": ["sigla_tipo", "ano", "situacao", "regime"],
    "tramitacao": ["sigla_orgao", "situacao"],
    "proposicao_tema": ["cod_tema"],
    "votacao": ["sigla_orgao", "aprovacao", "data"],
    "voto": ["tipo_voto", "sigla_partido"],
    "orientacao": ["orientacao", "tipo_lideranca"],
    "deputado": ["sigla_partido", "sigla_uf", "sexo", "id_legislatura"],
    "lideranca": ["bancada_tipo", "titulo"],
    "deputado_orgao": ["titulo"],
    "frente_membro": ["titulo"],
    "orgao": ["tipo_orgao"],
    "evento": ["situacao", "descricao_tipo"],
    "pauta_item": ["situacao_item", "regime"],
    "noticia": ["status", "tipo", "origem"],
    "trecho_rag": ["tipo"],
    "geracao_ia": ["status", "modelo_geracao"],
    "coleta": ["recurso", "status", "tipo"],
    "log_sistema": ["nivel", "modulo", "acao"],
}

# Ordem padrao: o mais recente primeiro
ORDEM_DECRESCENTE = {
    "proposicao": "data_apresentacao",
    "tramitacao": "data_hora",
    "votacao": "data",
    "evento": "data_hora_inicio",
    "coleta": "id",
    "log_sistema": "id",
    "noticia": "criado_em",
    "geracao_ia": "id",
}

COLUNAS = {
    "proposicao": {
        "regime": "Regime de tramitação. Vazio ou '.' quer dizer que a Câmara não informou",
        "data_status": "Data da situação atual. Vazio quer dizer que a Câmara não informou",
        "url_inteiro_teor": "Link do texto completo. Vazio quer dizer que a Câmara não informou",
        "filhos_sincronizados_em": "Quando autores, temas e tramitações foram buscados. Vazio = pendente",
        "hash_origem": "SHA-256 do conteúdo, para saber se mudou na API",
    },
    "votacao": {
        "aprovacao": "1 = aprovada, 0 = rejeitada, vazio = a Câmara não informou",
        "filhos_sincronizados_em": "Quando votos e orientações foram buscados. Vazio = pendente",
        "proposicao_id": "Proposição objeto da votação, quando a API informa",
    },
    "voto": {
        "tipo_voto": "Sim, Não, Abstenção, Obstrução ou Artigo 17 (presidente). Vazio = votação secreta",
        "sigla_partido": "Partido do deputado no dia do voto",
    },
    "tramitacao": {"despacho": "Texto vazio quer dizer que a Câmara não mandou despacho"},
    "trecho_rag": {
        "texto": "O texto que a RoBERTaLexPT lê (até 400 tokens)",
        "embedding": "Vetor de 768 números (3.072 bytes)",
    },
    "coleta": {"status": "ok, parcial (algum registro falhou) ou erro"},
}

OCULTAS = (
    [f"{base}_{sufixo}" for base in ("noticia_fts", "trecho_fts") for sufixo in ("config", "data", "docsize", "idx")]
    + ["noticia_fts", "trecho_fts", "sqlite_sequence"]
    + [f"vec_trecho_{sufixo}" for sufixo in ("chunks", "info", "rowids", "vector_chunks00", "auxiliary")]
    + ["vec_trecho"]
)

CONTAGEM = " UNION ALL ".join(
    f"SELECT '{tabela}' AS tabela, COUNT(*) AS linhas FROM {tabela}"
    for grupo in GRUPOS.values()
    for tabela in grupo
    if tabela != "alembic_version"
)

CONSULTAS = {
    "contagem_das_tabelas": ("Quantas linhas tem cada tabela", CONTAGEM + " ORDER BY linhas DESC"),
    "votacoes_secretas": (
        "Votações secretas (todos os votos sem tipo)",
        "SELECT v.id, v.data, v.sigla_orgao, v.descricao, COUNT(*) AS presentes FROM votacao v "
        "JOIN voto x ON x.votacao_id = v.id GROUP BY v.id HAVING COUNT(x.tipo_voto) = 0",
    ),
    "situacao_das_votacoes": (
        "Votações nominais, secretas, simbólicas e pendentes",
        "SELECT CASE WHEN v.filhos_sincronizados_em IS NULL THEN 'pendente' "
        "WHEN (SELECT COUNT(*) FROM voto x WHERE x.votacao_id = v.id) = 0 THEN 'simbolica' "
        "WHEN (SELECT COUNT(tipo_voto) FROM voto x WHERE x.votacao_id = v.id) = 0 THEN 'secreta' "
        "ELSE 'nominal' END AS situacao, COUNT(*) AS votacoes FROM votacao v GROUP BY situacao ORDER BY votacoes DESC",
    ),
    "placar_por_partido": (
        "Placar de uma votação por partido",
        "SELECT sigla_partido, SUM(tipo_voto = 'Sim') AS sim, SUM(tipo_voto = 'Não') AS nao, "
        "SUM(tipo_voto = 'Abstenção') AS abstencao, SUM(tipo_voto IS NULL) AS sem_tipo FROM voto "
        "WHERE votacao_id = :votacao GROUP BY sigla_partido ORDER BY sim DESC",
    ),
    "proposicao_completa": (
        "Uma proposição: autores, temas e tramitações",
        "SELECT 'autor' AS parte, ordem AS n, nome AS texto FROM proposicao_autor WHERE proposicao_id = :id "
        "UNION ALL SELECT 'tema', relevancia, (SELECT nome FROM tema t WHERE t.cod_tema = pt.cod_tema) "
        "FROM proposicao_tema pt WHERE proposicao_id = :id "
        "UNION ALL SELECT 'tramitacao', sequencia, data_hora || ' ' || sigla_orgao || ': ' || "
        "COALESCE(NULLIF(despacho, ''), descricao) FROM tramitacao WHERE proposicao_id = :id ORDER BY parte, n",
    ),
    "votacoes_de_uma_proposicao": (
        "Votações de uma proposição",
        "SELECT v.id, v.data, v.sigla_orgao, v.aprovacao, v.descricao FROM votacao v "
        "JOIN votacao_proposicao vp ON vp.votacao_id = v.id WHERE vp.proposicao_id = :id ORDER BY v.data DESC",
    ),
    "votos_de_um_deputado": (
        "Votos de um deputado (procure pelo nome)",
        "SELECT d.nome, x.tipo_voto, v.data, v.descricao FROM voto x JOIN deputado d ON d.id = x.deputado_id "
        "JOIN votacao v ON v.id = x.votacao_id WHERE d.nome LIKE '%' || :nome || '%' ORDER BY v.data DESC",
    ),
    "proposicoes_por_tema": (
        "Proposições por tema",
        "SELECT t.nome AS tema, COUNT(*) AS proposicoes FROM proposicao_tema pt "
        "JOIN tema t ON t.cod_tema = pt.cod_tema GROUP BY t.nome ORDER BY proposicoes DESC",
    ),
    "nao_informado_pela_camara": (
        "Campos que a Câmara não informou",
        "SELECT 'proposicao.regime' AS campo, SUM(regime IS NULL OR TRIM(regime) IN ('', '.', '-')) AS linhas "
        "FROM proposicao UNION ALL SELECT 'proposicao.data_status', SUM(data_status IS NULL) FROM proposicao "
        "UNION ALL SELECT 'proposicao.url_inteiro_teor', SUM(url_inteiro_teor IS NULL) FROM proposicao "
        "UNION ALL SELECT 'tramitacao.regime', SUM(regime IS NULL OR TRIM(regime) IN ('', '.', '-')) FROM tramitacao "
        "UNION ALL SELECT 'tramitacao.despacho vazio', SUM(despacho = '') FROM tramitacao "
        "UNION ALL SELECT 'voto.tipo_voto', SUM(tipo_voto IS NULL) FROM voto",
    ),
    "pendentes": (
        "Proposições e votações pendentes",
        "SELECT 'proposicao' AS tipo, sigla_tipo AS sigla, COUNT(*) AS pendentes FROM proposicao "
        "WHERE filhos_sincronizados_em IS NULL GROUP BY sigla_tipo UNION ALL SELECT 'votacao', '', COUNT(*) "
        "FROM votacao WHERE filhos_sincronizados_em IS NULL ORDER BY pendentes DESC",
    ),
    "ultimas_coletas": (
        "Últimas coletas",
        "SELECT id, recurso, tipo, status, iniciado_em, finalizado_em, total_itens, itens_novos, "
        "itens_atualizados, requisicoes, erros_http, mensagem_erro FROM coleta ORDER BY id DESC LIMIT 50",
    ),
    "erros_no_log": (
        "Erros e avisos do log, agrupados",
        "SELECT nivel, acao, entidade, COUNT(*) AS vezes, MAX(data_hora) AS ultima, MIN(descricao) AS exemplo "
        "FROM log_sistema WHERE nivel IN ('erro', 'aviso') GROUP BY nivel, acao, entidade ORDER BY vezes DESC",
    ),
    "trechos_de_uma_proposicao": (
        "O que a Roberta lê sobre uma proposição",
        "SELECT tipo, ref_id, parte, tokens, texto FROM trecho_rag WHERE (tipo = 'proposicao' AND ref_id = :id) "
        "OR (tipo = 'tramitacao' AND ref_id LIKE :id || '/%') ORDER BY tipo, ref_id, parte",
    ),
    "vetores_amostra": (
        "Índice vetorial: amostra (precisa da extensão sqlite-vec)",
        "SELECT v.trecho_id, vec_length(v.embedding) AS dimensoes, t.tipo, t.ref_id, substr(t.texto, 1, 80) "
        "AS inicio FROM vec_trecho v JOIN trecho_rag t ON t.id = v.trecho_id LIMIT 50",
    ),
}

# Consultas que pedem um valor, com o campo e um exemplo para o menu
COM_CAMPO = {
    "placar_por_partido": ("votacao", "Id da votação", "2480642-7"),
    "proposicao_completa": ("id", "Id da proposição", "265999"),
    "votacoes_de_uma_proposicao": ("id", "Id da proposição", "2459654"),
    "votos_de_um_deputado": ("nome", "Nome do deputado", "Aécio"),
    "trechos_de_uma_proposicao": ("id", "Id da proposição", "265999"),
}

ESTILO = """
<style>
.menu-desperta{font-size:1rem;line-height:1.5;max-width:70em}
.menu-desperta h2{margin:1.2em 0 .4em;font-size:1.3rem}
.menu-desperta h3{margin:.8em 0 .2em;font-size:1.05rem}
.menu-desperta .grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(18em,1fr));gap:.8em 1.6em}
.menu-desperta form{margin:.3em 0}
.menu-desperta label{display:block;font-weight:bold}
.menu-desperta input[type=text]{font-size:1rem;padding:.25em .4em;width:14em}
.menu-desperta ul{margin:.2em 0 .6em 1.2em;padding:0}
.menu-desperta li{margin:.15em 0}
.menu-desperta .nota{color:#444;font-size:.95rem}
</style>
"""


def _busca(banco, acao, campo, rotulo, exemplo, botao):
    identificador = f"{acao.replace('/', '-')}-{campo}"
    return (
        f'<form action="/{banco}/{acao}" method="get">'
        f'<label for="{identificador}">{rotulo}</label>'
        f'<input type="text" id="{identificador}" name="{campo}" placeholder="ex.: {exemplo}"> '
        f'<input type="submit" value="{botao}"></form>'
    )


def menu(banco):
    partes = [ESTILO, '<div class="menu-desperta">']
    partes.append(
        '<p class="nota">Só para olhar o banco durante o desenvolvimento, em <strong>modo somente leitura</strong>. '
        "Clique numa tabela para filtrar, ordenar e ver os registros; os ids ligados mostram o nome. "
        "Vazio, <code>''</code> ou <code>.</code> em campo da Câmara quer dizer que ela não informou.</p>"
    )
    partes.append(
        f'<p style="font-size:1.15rem"><strong><a href="/visao-geral?banco={banco}">Visão geral do banco</a></strong>: '
        "números, período dos dados, votações, o que a Câmara não informou, coletas e erros, numa página só.</p>"
    )
    partes.append('<h2>Busca rápida</h2><div class="grade">')
    partes.append(_busca(banco, "proposicao", "id__exact", "Proposição pelo id", "265999", "Abrir"))
    partes.append(_busca(banco, "proposicao", "ementa__contains", "Palavra na ementa", "indígenas", "Buscar"))
    partes.append(_busca(banco, "votacao", "id__exact", "Votação pelo id", "2645346-18", "Abrir"))
    partes.append(_busca(banco, "deputado", "nome__contains", "Deputado pelo nome", "Marinho", "Buscar"))
    partes.append(_busca(banco, "trecho_rag", "_search", "Palavras no que a Roberta lê", "demarcação", "Buscar"))
    partes.append(_busca(banco, "tramitacao", "despacho__contains", "Palavra no despacho", "arquive-se", "Buscar"))
    partes.append("</div>")

    partes.append('<h2>Tabelas</h2><div class="grade">')
    for grupo, tabelas in GRUPOS.items():
        itens = "".join(
            f'<li><a href="/{banco}/{tabela}">{tabela}</a>: {texto}</li>' for tabela, texto in tabelas.items()
        )
        partes.append(f"<div><h3>{grupo}</h3><ul>{itens}</ul></div>")
    partes.append("</div>")

    partes.append('<h2>Consultas prontas</h2><div class="grade">')
    simples = [
        nome for nome in CONSULTAS if nome not in COM_CAMPO and (banco == "desperta" or nome != "vetores_amostra")
    ]
    itens = "".join(f'<li><a href="/{banco}/{nome}">{CONSULTAS[nome][0]}</a></li>' for nome in simples)
    partes.append(f"<div><h3>Visão geral</h3><ul>{itens}</ul></div><div><h3>Com um valor</h3>")
    for nome, (campo, rotulo, exemplo) in COM_CAMPO.items():
        partes.append(_busca(banco, nome, campo, f"{CONSULTAS[nome][0]} ({rotulo.lower()})", exemplo, "Ver"))
    partes.append("</div></div>")
    partes.append(
        f'<p class="nota">Para escrever a sua própria consulta (só <code>SELECT</code>), use o campo de SQL '
        f'na <a href="/{banco}">página do banco</a>.</p></div>'
    )
    return "".join(partes)


def tabelas_do_banco(banco):
    tabelas = {}
    for grupo in GRUPOS.values():
        for tabela, texto in grupo.items():
            tabelas[tabela] = {"description": texto}
    for tabela, coluna in ROTULOS.items():
        tabelas[tabela]["label_column"] = coluna
    for tabela, colunas in FILTROS.items():
        tabelas[tabela]["facets"] = colunas
    for tabela, coluna in ORDEM_DECRESCENTE.items():
        tabelas[tabela]["sort_desc"] = coluna
    for tabela, colunas in COLUNAS.items():
        tabelas[tabela]["columns"] = colunas
    # Busca por palavras pelo indice que o modulo de IA ja mantem; a amostra nao tem esse indice
    if banco == "desperta":
        tabelas["trecho_rag"].update(fts_table="trecho_fts", fts_pk="id")
    tabelas["noticia"].update(fts_table="noticia_fts", fts_pk="id")
    for tabela in OCULTAS:
        tabelas[tabela] = {"hidden": True}
    return tabelas


def montar():
    metadata = {
        "title": "Desperta Brasil — banco de dados (desenvolvimento)",
        "description_html": ESTILO
        + '<div class="menu-desperta"><p style="font-size:1.15rem"><strong>Visão geral:</strong> '
        '<a href="/visao-geral?banco=desperta">banco completo</a> · '
        '<a href="/visao-geral?banco=desperta-amostra">amostra</a> (se estiver aberta)</p>'
        "<p>Ou escolha o banco abaixo: a página dele tem o menu com a busca rápida, as tabelas por assunto "
        "e as consultas prontas. Modo somente leitura; não faz parte do portal.</p></div>",
        "databases": {},
    }
    for banco in BANCOS:
        metadata["databases"][banco] = {
            "description_html": menu(banco),
            "tables": tabelas_do_banco(banco),
            # A amostra nao tem o indice vetorial: a consulta dele fica so no banco completo
            "queries": {
                nome: {"title": titulo, "sql": sql}
                for nome, (titulo, sql) in CONSULTAS.items()
                if banco == "desperta" or nome != "vetores_amostra"
            },
        }
    caminho = os.path.join(PASTA, "metadata.json")
    with open(caminho, "w", encoding="utf-8") as saida:
        json.dump(metadata, saida, ensure_ascii=False, indent=2)
    return caminho


if __name__ == "__main__":
    print(montar())
