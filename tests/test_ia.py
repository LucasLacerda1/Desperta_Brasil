import hashlib
import math
import struct
import json
import os
import sys
from datetime import date, datetime, timedelta

import pytest

import fabricas
from desperta import create_app
from desperta.config import TestConfig
from desperta.ia import centralizacao, embeddings, palavras, services, trechos, vetores
from desperta.ia.embeddings import ModeloEmbedding, preparar_ambiente
from desperta.ia.gerador import Gerador, GeradorFalso
from desperta.ia.models import GeracaoIA, GeracaoTrecho, TrechoRAG
from desperta.sistema.models import LogSistema

pytest.importorskip("sqlite_vec")

MODELO = "modelo-de-teste"


class ModeloFalso:
    """Palavras viram posicoes do vetor: textos com as mesmas palavras ficam parecidos."""

    nome = MODELO

    def __init__(self):
        self.embutidos = []

    def dividir(self, texto, max_tokens, sobreposicao):
        palavras = texto.split()
        if len(palavras) <= max_tokens:
            return [(texto, len(palavras))]
        passo = max_tokens - sobreposicao
        inicios = range(0, len(palavras) - sobreposicao, passo)
        pedacos = [palavras[inicio:][:max_tokens] for inicio in inicios]
        return [(" ".join(pedaco), len(pedaco)) for pedaco in pedacos]

    def embutir(self, textos):
        self.embutidos.extend(textos)
        return [self._vetor(texto) for texto in textos]

    def _vetor(self, texto):
        vetor = [0.0] * 768
        for palavra in texto.lower().split():
            vetor[int(hashlib.sha256(palavra.encode()).hexdigest(), 16) % 768] += 1.0
        norma = math.sqrt(sum(valor * valor for valor in vetor)) or 1.0
        return struct.pack("768f", *(valor / norma for valor in vetor))


@pytest.fixture
def modelo():
    return ModeloFalso()


@pytest.fixture
def origem(app, db):
    # As datas dos exemplos sao antigas: aqui, todas as tramitacoes contam como recentes
    app.config["RAG_TRAMITACAO_DIAS"] = 100_000
    db.session.add_all(
        [
            fabricas.orgao(),
            fabricas.proposicao(ementa="Reforma tributaria dos municipios", ementa_detalhada="Imposto municipal"),
            fabricas.proposicao(
                id=2, numero=2, ementa="Merenda escolar nas escolas", data_apresentacao=datetime(2020, 1, 1)
            ),
            fabricas.tramitacao(despacho="Encaminhe-se a comissao de saude", situacao="Aguardando parecer"),
            fabricas.tramitacao(sequencia=2, despacho="", situacao=None),
            fabricas.evento(descricao="Sessao sobre orcamento"),
            fabricas.votacao(descricao="Aprovado o projeto de merenda", aprovacao=True),
        ]
    )
    db.session.commit()
    return db


def _trecho(db, tipo, ref_id, parte=1):
    return db.session.scalar(db.select(TrechoRAG).filter_by(tipo=tipo, ref_id=ref_id, parte=parte))


def _referencias(resultados):
    return [(achado.trecho.tipo, achado.trecho.ref_id) for achado in resultados]


# ======================================================
# O QUE VIRA TRECHO
# ======================================================
def test_textos_de_origem_tem_os_campos_da_secao_6_1(origem):
    textos = {(tipo, ref): texto for tipo, ref, texto in trechos.textos_de_origem()}
    assert textos[("proposicao", "2310837")] == "PL 1234/2024. Reforma tributaria dos municipios Imposto municipal"
    assert textos[("tramitacao", "2310837/1")] == (
        "PL 1234/2024 — Reforma tributaria dos municipios 14/05/2024 PLEN. "
        "Aguardando parecer Encaminhe-se a comissao de saude"
    )
    assert textos[("votacao", "2310837-8")] == "Aprovado o projeto de merenda PLEN, 14/05/2024. Resultado: aprovada."
    assert textos[("evento", "70001")] == "Sessao Deliberativa. Sessao sobre orcamento"


def test_tramitacao_sem_situacao_e_sem_despacho_nao_vira_trecho(origem):
    assert ("tramitacao", "2310837/2") not in {(tipo, ref) for tipo, ref, _ in trechos.textos_de_origem()}


def test_tramitacao_antiga_nao_vira_trecho(app, origem):
    app.config["RAG_TRAMITACAO_DIAS"] = 90
    assert list(trechos.textos_de_origem(["tramitacao"])) == []
    recente = datetime.now() - timedelta(days=10)
    origem.session.add(fabricas.tramitacao(sequencia=3, data_hora=recente))
    origem.session.commit()
    assert [ref for _, ref, _ in trechos.textos_de_origem(["tramitacao"])] == ["2310837/3"]


def test_tramitacao_comeca_com_a_ementa_cortada(origem):
    origem.session.get(fabricas.Proposicao, 2310837).ementa = "x" * 300
    origem.session.commit()
    texto = dict((ref, texto) for _, ref, texto in trechos.textos_de_origem(["tramitacao"]))["2310837/1"]
    assert texto.startswith("PL 1234/2024 — " + "x" * 200 + " 14/05/2024")


def test_filtro_por_tipo_e_item_de_pauta(origem):
    origem.session.add(fabricas.PautaItem(evento_id=70001, ordem=1, topico="Tema", texto_parecer="Parecer"))
    origem.session.add(fabricas.PautaItem(evento_id=70001, ordem=2))
    origem.session.commit()
    assert list(trechos.textos_de_origem(["pauta_item"])) == [("pauta_item", "70001/1", "Tema Parecer")]


# ======================================================
# INDEXACAO
# ======================================================
def test_indexar_grava_trecho_embedding_e_indice(origem, modelo):
    resumo = services.indexar(modelo)
    assert resumo["indexados"] == 5
    trecho = _trecho(origem, "votacao", "2310837-8")
    assert len(trecho.embedding) == 3072
    assert trecho.modelo_embedding == MODELO
    assert trecho.hash_texto == hashlib.sha256(trecho.texto.encode()).hexdigest()
    assert trecho.tokens == len(trecho.texto.split())
    assert vetores.buscar(trecho.embedding, 1)[0][0] == trecho.id


def test_indexar_de_novo_nao_gera_embedding(origem, modelo):
    services.indexar(modelo)
    modelo.embutidos.clear()
    resumo = services.indexar(modelo)
    assert modelo.embutidos == []
    assert resumo["indexados"] == 0
    assert resumo["iguais"] == 5


def test_texto_alterado_atualiza_o_mesmo_trecho_e_o_indice(origem, modelo):
    services.indexar(modelo)
    antes = _trecho(origem, "evento", "70001")
    id_antes, embedding_antes = antes.id, antes.embedding
    origem.session.get(fabricas.Evento, 70001).descricao = "Audiencia sobre previdencia"
    origem.session.commit()

    resumo = services.indexar(modelo)

    depois = _trecho(origem, "evento", "70001")
    assert resumo["indexados"] == 1
    assert (depois.id, "previdencia" in depois.texto) == (id_antes, True)
    assert depois.embedding != embedding_antes
    assert vetores.buscar(depois.embedding, 1) == [(id_antes, pytest.approx(0, abs=1e-5))]


def test_texto_longo_vira_varias_partes_com_sobreposicao(app, origem, modelo):
    app.config.update(RAG_TRECHO_TOKENS=4, RAG_TRECHO_SOBREPOSICAO=1)
    origem.session.get(fabricas.Evento, 70001).descricao = "a b c d e f g"
    origem.session.commit()
    services.indexar(modelo, ["evento"])
    assert [_trecho(origem, "evento", "70001", parte).texto for parte in (1, 2, 3)] == [
        "Sessao Deliberativa. a b",
        "b c d e",
        "e f g",
    ]
    # Na segunda vez, tambem nao gera embedding das partes
    modelo.embutidos.clear()
    services.indexar(modelo, ["evento"])
    assert modelo.embutidos == []


def test_parte_e_registro_que_sumiram_saem_do_indice(app, origem, modelo):
    services.indexar(modelo)
    trecho = _trecho(origem, "evento", "70001")
    id_trecho, embedding = trecho.id, trecho.embedding
    origem.session.delete(origem.session.get(fabricas.Evento, 70001))
    origem.session.commit()

    resumo = services.indexar(modelo)

    assert resumo["removidos"] == 1
    assert _trecho(origem, "evento", "70001") is None
    assert id_trecho not in [achado[0] for achado in vetores.buscar(embedding, 5)]


def test_trecho_usado_por_geracao_fica_para_o_historico(origem, modelo):
    services.indexar(modelo)
    trecho = _trecho(origem, "evento", "70001")
    geracao = GeracaoIA(
        modelo_geracao="x", modelo_embedding=MODELO, consulta="c", versao_prompt="v", entrada="{}", status="ok"
    )
    origem.session.add(geracao)
    origem.session.flush()
    origem.session.add(GeracaoTrecho(geracao_id=geracao.id, trecho_id=trecho.id, posicao=1, similaridade=0.9))
    origem.session.delete(origem.session.get(fabricas.Evento, 70001))
    origem.session.commit()

    resumo = services.indexar(modelo)

    assert (resumo["removidos"], resumo["mantidos"]) == (0, 1)
    assert _trecho(origem, "evento", "70001") is not None


def test_limite_para_e_a_proxima_execucao_continua_sem_apagar_nada(origem, modelo):
    primeira = services.indexar(modelo, limite=2)
    assert primeira["indexados"] == 2
    assert primeira["interrompido"] == 1
    assert primeira["removidos"] == 0
    segunda = services.indexar(modelo)
    assert segunda["indexados"] == 3
    assert segunda["iguais"] == 2


def test_indexar_registra_no_log(origem, modelo):
    services.indexar(modelo)
    log = origem.session.scalar(origem.select(LogSistema).where(LogSistema.acao == "indexar"))
    assert log.modulo == "IA"
    assert "indexados=5" in log.descricao


# ======================================================
# BUSCA
# ======================================================
def test_busca_ordena_por_similaridade(origem, modelo):
    services.indexar(modelo)
    resultados = services.buscar(modelo, "merenda escolar nas escolas", top_k=2, modo="vetorial")
    assert [achado.posicao for achado in resultados] == [1, 2]
    assert _referencias(resultados)[0] == ("proposicao", "2")
    assert resultados[0].similaridade > resultados[1].similaridade
    assert resultados[0].similaridade <= 1.0001


def test_busca_usa_o_top_k_da_configuracao(app, origem, modelo):
    app.config["RAG_TOP_K"] = 3
    services.indexar(modelo)
    assert len(services.buscar(modelo, "merenda")) == 3


def test_busca_filtra_por_tipo(origem, modelo):
    services.indexar(modelo)
    resultados = services.buscar(modelo, "merenda escolar", top_k=8, tipos=["votacao"])
    assert _referencias(resultados) == [("votacao", "2310837-8")]


def test_busca_filtra_por_data_de_origem(origem, modelo):
    services.indexar(modelo)
    resultados = services.buscar(modelo, "merenda", top_k=8, inicio=date(2020, 1, 1), fim=date(2020, 1, 1))
    assert _referencias(resultados) == [("proposicao", "2")]
    # 14/05/2024: proposicao, tramitacao, evento e votacao; a proposicao de 2020 fica de fora
    resultados = services.buscar(modelo, "merenda", top_k=8, inicio=date(2024, 5, 14))
    assert set(_referencias(resultados)) == {
        ("proposicao", "2310837"),
        ("tramitacao", "2310837/1"),
        ("evento", "70001"),
        ("votacao", "2310837-8"),
    }


def test_busca_filtra_por_tipo_e_data_juntos_e_item_de_pauta(origem, modelo):
    origem.session.add(fabricas.PautaItem(evento_id=70001, ordem=1, topico="Merenda"))
    origem.session.commit()
    services.indexar(modelo)
    assert _referencias(
        services.buscar(modelo, "merenda", tipos=["pauta_item"], inicio=date(2024, 5, 1), fim=date(2024, 5, 31))
    ) == [("pauta_item", "70001/1")]
    assert services.buscar(modelo, "merenda", tipos=["pauta_item"], fim=date(2024, 1, 1)) == []


def test_busca_sem_nada_indexado_devolve_vazio(db, modelo):
    assert services.buscar(modelo, "qualquer coisa") == []


def test_modo_de_busca_desconhecido(db, modelo):
    with pytest.raises(ValueError):
        services.buscar(modelo, "x", modo="outro")


# ======================================================
# DECISAO 16.1: BUSCA HIBRIDA
# ======================================================
class ModeloCego(ModeloFalso):
    """Todo texto vira o mesmo vetor: so a busca por palavras consegue separar."""

    def _vetor(self, texto):
        return struct.pack("768f", *([1.0] + [0.0] * 767))


def test_busca_por_palavras_ignora_acento_e_maiuscula(origem, modelo):
    origem.session.get(fabricas.Evento, 70001).descricao = "Audiência sobre PREVIDÊNCIA"
    origem.session.commit()
    services.indexar(modelo)
    resultados = services.buscar(modelo, "previdencia", modo="palavras")
    assert _referencias(resultados) == [("evento", "70001")]


def test_busca_por_palavras_nao_quebra_com_pontuacao(origem, modelo):
    services.indexar(modelo)
    assert services.buscar(modelo, 'PL "1234/2024" AND (', modo="palavras")
    assert services.buscar(modelo, "!!! ---", modo="palavras") == []


def test_hibrida_acha_palavra_que_o_vetor_nao_acha(origem):
    modelo = ModeloCego()
    services.indexar(modelo)
    resultados = services.buscar(modelo, "orcamento", top_k=1)
    assert _referencias(resultados) == [("evento", "70001")]


def test_hibrida_acha_pelo_vetor_o_que_nao_tem_a_palavra(origem, modelo):
    services.indexar(modelo)
    vetor_igual = "Merenda escolar nas escolas"
    resultados = services.buscar(modelo, f"{vetor_igual} inexistentepalavra", top_k=1)
    assert _referencias(resultados) == [("proposicao", "2")]


def test_nota_e_a_soma_do_rrf(app, origem, modelo):
    services.indexar(modelo)
    constante = app.config["RAG_RRF_K"]
    primeiro = services.buscar(modelo, "Merenda escolar nas escolas", top_k=1)[0]
    # Em primeiro lugar nas duas listas
    assert primeiro.similaridade == pytest.approx(2 / (constante + 1))


def test_filtros_valem_para_as_duas_buscas(origem, modelo):
    services.indexar(modelo)
    assert _referencias(services.buscar(modelo, "merenda", tipos=["votacao"], modo="palavras")) == [
        ("votacao", "2310837-8")
    ]
    assert _referencias(services.buscar(modelo, "merenda", fim=date(2020, 12, 31), modo="palavras")) == [
        ("proposicao", "2")
    ]
    assert {tipo for tipo, _ in _referencias(services.buscar(modelo, "merenda", tipos=["votacao"]))} == {"votacao"}


def test_indice_de_palavras_acompanha_alteracao_e_remocao(origem, modelo):
    services.indexar(modelo)
    assert services.buscar(modelo, "orcamento", modo="palavras")
    origem.session.get(fabricas.Evento, 70001).descricao = "Sessao sobre previdencia"
    origem.session.commit()
    services.indexar(modelo)
    assert services.buscar(modelo, "orcamento", modo="palavras") == []
    assert _referencias(services.buscar(modelo, "previdencia", modo="palavras")) == [("evento", "70001")]
    origem.session.delete(origem.session.get(fabricas.Evento, 70001))
    origem.session.commit()
    services.indexar(modelo)
    assert services.buscar(modelo, "previdencia", modo="palavras") == []


def test_indice_de_palavras_recebe_os_trechos_que_ja_existiam(origem, modelo):
    services.indexar(modelo)
    palavras.remover_indice()
    origem.session.commit()
    resultados = services.buscar(modelo, "orcamento", modo="palavras")
    assert _referencias(resultados) == [("evento", "70001")]


def test_indice_de_palavras_criado_na_busca_continua_cheio_depois_dela(origem, modelo):
    services.indexar(modelo)
    palavras.remover_indice()
    origem.session.commit()
    services.buscar(modelo, "orcamento", modo="palavras")
    # Como quando o comando termina: o que nao teve commit e desfeito
    origem.session.rollback()
    assert _referencias(services.buscar(modelo, "orcamento", modo="palavras")) == [("evento", "70001")]


def test_reconstruir_refaz_o_indice_de_palavras(origem, modelo):
    services.indexar(modelo)
    origem.session.execute(origem.text("INSERT INTO trecho_fts(trecho_fts) VALUES ('delete-all')"))
    origem.session.commit()
    assert services.buscar(modelo, "orcamento", modo="palavras") == []
    services.reconstruir_indice(MODELO)
    assert services.buscar(modelo, "orcamento", modo="palavras")


# ======================================================
# DECISAO 16.1: CENTRALIZACAO
# ======================================================
def _vetor(embedding):
    return struct.unpack("768f", embedding)


def test_centralizar_grava_o_vetor_medio_e_nao_muda_trecho_rag(app, origem, modelo, tmp_path):
    app.instance_path = str(tmp_path)
    services.indexar(modelo)
    trecho = _trecho(origem, "votacao", "2310837-8")
    original = trecho.embedding
    assert centralizacao.calcular(MODELO) == 5
    assert (tmp_path / centralizacao.ARQUIVO).exists()

    app.config["RAG_CENTRALIZAR"] = True
    services.reconstruir_indice(MODELO)

    assert _trecho(origem, "votacao", "2310837-8").embedding == original
    centralizado = centralizacao.transformador()(original)
    assert centralizado != original
    assert math.sqrt(sum(valor * valor for valor in _vetor(centralizado))) == pytest.approx(1.0, abs=1e-5)
    assert vetores.buscar(centralizado, 1)[0][0] == trecho.id


def test_consulta_e_trechos_novos_tambem_sao_centralizados(app, origem, modelo, tmp_path):
    app.instance_path = str(tmp_path)
    services.indexar(modelo)
    centralizacao.calcular(MODELO)
    app.config["RAG_CENTRALIZAR"] = True
    services.reconstruir_indice(MODELO)
    origem.session.add(fabricas.evento(id=70002, descricao="Audiencia sobre previdencia"))
    origem.session.commit()
    services.indexar(modelo)
    resultados = services.buscar(modelo, "Sessao Deliberativa. Audiencia sobre previdencia", top_k=1, modo="vetorial")
    assert _referencias(resultados) == [("evento", "70002")]
    assert resultados[0].similaridade == pytest.approx(1.0, abs=1e-4)


def test_centralizar_sem_trechos_nao_grava_arquivo(app, db, tmp_path):
    app.instance_path = str(tmp_path)
    assert centralizacao.calcular(MODELO) == 0
    assert not (tmp_path / centralizacao.ARQUIVO).exists()


# ======================================================
# DECISAO 16.2: MEDIR A BUSCA
# ======================================================
def test_medir_busca_conta_as_esperadas_por_modo(origem, modelo):
    services.indexar(modelo)
    consultas = [
        {"consulta": "merenda escolar", "esperadas": [2]},
        {"consulta": "palavraquenaoexiste", "esperadas": [999]},
    ]
    resultado = services.medir_busca(modelo, consultas, modos=("palavras",))
    assert resultado["palavras"]["acertos"] == 1
    assert resultado["palavras"]["total"] == 2
    assert resultado["palavras"]["consultas"][0] == ("merenda escolar", 1, 1)


def test_tramitacao_conta_como_achar_a_proposicao(origem, modelo):
    services.indexar(modelo)
    consultas = [{"consulta": "comissao de saude", "esperadas": [2310837]}]
    assert services.medir_busca(modelo, consultas, modos=("palavras",))["palavras"]["acertos"] == 1


def test_comando_medir_busca(comandos, origem, tmp_path):
    comandos.invoke(args=["ia", "indexar"])
    arquivo = tmp_path / "consultas.json"
    arquivo.write_text(json.dumps({"consultas": [{"consulta": "merenda escolar", "esperadas": [2]}]}))
    saida = comandos.invoke(args=["ia", "medir-busca", str(arquivo)]).output
    assert "hibrida: 1 de 1" in saida
    assert "vetorial:" in saida and "palavras:" in saida


def test_arquivo_de_consultas_tem_20_consultas_com_esperadas():
    caminho = os.path.join(os.path.dirname(__file__), "dados", "consultas_busca.json")
    with open(caminho, encoding="utf-8") as entrada:
        consultas = json.load(entrada)["consultas"]
    assert len(consultas) == 20
    assert all(item["consulta"] and item["esperadas"] for item in consultas)


# ======================================================
# DECISOES 16.7 E 21: ONDE O MODELO FICA
# ======================================================
def _pasta_de_modelo(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in ("config.json", "tokenizer_config.json", "tokenizer.json"):
        (pasta / nome).write_text("{}")
    (pasta / "model.safetensors").write_bytes(b"0" * 2_000_000)
    return pasta


class CarregadorFalso:
    """No lugar da ModeloEmbedding de verdade: guarda de onde o modelo seria lido."""

    pastas = []

    def __init__(self, nome, pasta=None, dispositivo="cpu"):
        CarregadorFalso.pastas.append(pasta)
        self.nome = nome
        self.dispositivo = dispositivo

    def embutir(self, textos):
        return [bytes(3072) for _ in textos]


@pytest.fixture
def carregador(monkeypatch):
    CarregadorFalso.pastas = []
    monkeypatch.setattr("desperta.ia.embeddings.ModeloEmbedding", CarregadorFalso)
    monkeypatch.setenv("HF_HUB_OFFLINE", "x")
    return CarregadorFalso


def test_padrao_da_roberta_fica_dentro_de_modelos_dir():
    assert TestConfig.ROBERTA_DIR_PADRAO == os.path.join(TestConfig.MODELOS_DIR, "roberta-lexpt-base")


def test_offline_pela_configuracao_e_baixar_sempre_online(app, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "x")
    app.config["HF_HUB_OFFLINE"] = "1"
    preparar_ambiente(app)
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    preparar_ambiente(app, offline=False)
    assert os.environ["HF_HUB_OFFLINE"] == "0"


def test_caminho_relativo_parte_da_raiz_e_absoluto_fica_como_esta(app):
    raiz = os.path.dirname(app.instance_path)
    assert embeddings.caminho_no_projeto(app, "instance/modelos") == os.path.join(raiz, "instance/modelos")
    assert embeddings.caminho_no_projeto(app, "/media/x/DESPERTA") == "/media/x/DESPERTA"


def test_pasta_completa_nao_falta_nada(tmp_path):
    assert embeddings.arquivos_faltando(_pasta_de_modelo(tmp_path)) == []


def test_tokenizador_pode_vir_em_vocab_e_merges(tmp_path):
    _pasta_de_modelo(tmp_path)
    (tmp_path / "tokenizer.json").unlink()
    assert embeddings.arquivos_faltando(tmp_path) == ["tokenizer.json"]
    (tmp_path / "vocab.json").write_text("{}")
    (tmp_path / "merges.txt").write_text("")
    assert embeddings.arquivos_faltando(tmp_path) == []


def test_pasta_que_nao_existe_falta_tudo(tmp_path):
    assert "model.safetensors" in embeddings.arquivos_faltando(tmp_path / "nada")


@pytest.mark.parametrize("criar", [False, True], ids=["nao-existe", "vazia"])
def test_sem_a_roberta_para_com_mensagem_e_aviso_no_log(app, db, tmp_path, criar):
    pasta = tmp_path / "pendrive"
    if criar:
        pasta.mkdir()
    app.config["ROBERTA_DIR"] = str(pasta)
    with pytest.raises(embeddings.RobertaAusente, match="O pendrive está conectado"):
        services.carregar_modelo()
    log = db.session.scalar(db.select(LogSistema).filter_by(acao="roberta_ausente"))
    assert (log.nivel, log.modulo) == ("aviso", "IA")
    assert str(pasta) in log.descricao


def test_comandos_que_usam_a_roberta_saem_com_erro_sem_ela(app, db, tmp_path):
    app.config["ROBERTA_DIR"] = str(tmp_path / "pendrive")
    for comando in (["ia", "indexar"], ["ia", "buscar", "x"], ["ia", "medir-busca"]):
        resultado = app.test_cli_runner().invoke(args=comando)
        assert resultado.exit_code != 0
        assert "O pendrive está conectado" in resultado.output


def test_com_a_pasta_carrega_dela_e_registra_o_dispositivo(app, db, carregador, tmp_path):
    app.config.update(ROBERTA_DIR=str(_pasta_de_modelo(tmp_path)), IA_DISPOSITIVO="cpu")
    services.carregar_modelo()
    assert carregador.pastas == [str(tmp_path)]
    log = db.session.scalar(db.select(LogSistema).filter_by(acao="carregar_modelo"))
    assert "dispositivo=cpu" in log.descricao


def test_baixar_modelo_salva_em_roberta_dir_online_e_sem_deixar_cache(app, carregador, monkeypatch, tmp_path):
    destino = tmp_path / "modelos" / "roberta"
    app.config.update(MODELOS_DIR=str(tmp_path / "modelos"), ROBERTA_DIR=str(destino), ROBERTA_DIR_PADRAO=str(destino))
    app.config["HF_HUB_OFFLINE"] = "1"
    chamadas = []

    def salvar(nome, pasta, cache):
        chamadas.append((nome, pasta, os.environ["HF_HUB_OFFLINE"]))
        _pasta_de_modelo(tmp_path / "modelos" / "roberta")

    monkeypatch.setattr("desperta.ia.embeddings.salvar_modelo", salvar)
    resultado = app.test_cli_runner().invoke(args=["ia", "baixar-modelo"])
    assert resultado.exit_code == 0, resultado.output
    assert chamadas == [(app.config["EMBEDDING_MODEL"], str(destino), "0")]
    assert "model.safetensors" in resultado.output and "(2 MB)" in resultado.output
    assert sorted(os.listdir(tmp_path / "modelos")) == ["roberta"]
    assert carregador.pastas == [str(destino)]


def test_baixar_modelo_nao_baixa_de_novo_se_a_pasta_esta_completa(app, carregador, monkeypatch, tmp_path):
    app.config["ROBERTA_DIR"] = str(_pasta_de_modelo(tmp_path))
    monkeypatch.setattr("desperta.ia.embeddings.salvar_modelo", lambda *a: pytest.fail("nao devia baixar"))
    assert app.test_cli_runner().invoke(args=["ia", "baixar-modelo"]).exit_code == 0


def test_baixar_modelo_nao_vai_para_o_pc_com_o_pendrive_desconectado(app, carregador, monkeypatch, tmp_path):
    app.config["ROBERTA_DIR"] = str(tmp_path / "DESPERTA" / "roberta")
    monkeypatch.setattr("desperta.ia.embeddings.salvar_modelo", lambda *a: pytest.fail("nao devia baixar"))
    resultado = app.test_cli_runner().invoke(args=["ia", "baixar-modelo"])
    assert resultado.exit_code != 0
    assert "O pendrive está conectado" in resultado.output


def test_mover_roberta_copia_confere_e_nao_apaga_a_antiga(app, carregador, tmp_path):
    origem = _pasta_de_modelo(tmp_path / "origem")
    destino = tmp_path / "pendrive" / "roberta"
    app.config["ROBERTA_DIR"] = str(origem)
    resultado = app.test_cli_runner().invoke(args=["ia", "mover-roberta", "--para", str(destino)])
    assert resultado.exit_code == 0, resultado.output
    assert sorted(os.listdir(destino)) == sorted(os.listdir(origem))
    assert (origem / "model.safetensors").exists()
    assert not any((destino / nome).is_symlink() for nome in os.listdir(destino))
    assert f"ROBERTA_DIR={destino}" in resultado.output
    assert carregador.pastas == [str(destino)]


def test_mover_roberta_recusa_pasta_com_arquivos_e_origem_incompleta(app, carregador, tmp_path):
    origem = _pasta_de_modelo(tmp_path / "origem")
    ocupada = tmp_path / "ocupada"
    ocupada.mkdir()
    (ocupada / "foto.jpg").write_text("x")
    app.config["ROBERTA_DIR"] = str(origem)
    resultado = app.test_cli_runner().invoke(args=["ia", "mover-roberta", "--para", str(ocupada)])
    assert resultado.exit_code != 0 and "nao esta vazia" in resultado.output
    assert (ocupada / "foto.jpg").read_text() == "x"
    app.config["ROBERTA_DIR"] = str(tmp_path / "nada")
    assert app.test_cli_runner().invoke(args=["ia", "mover-roberta", "--para", str(tmp_path / "d")]).exit_code != 0


def test_copia_diferente_do_original_e_erro(tmp_path, monkeypatch):
    origem = _pasta_de_modelo(tmp_path / "origem")
    hashes = iter(["a", "b"])
    monkeypatch.setattr("desperta.ia.embeddings._hash_do_arquivo", lambda caminho: next(hashes))
    with pytest.raises(ValueError, match="ficou diferente"):
        embeddings.copiar_modelo(origem, tmp_path / "destino")


# ======================================================
# DECISAO 19.2: RRF COM PESO E FORA DO ASSUNTO
# ======================================================
def test_rrf_com_peso_conta_menos_a_lista_vetorial(app, origem, modelo):
    services.indexar(modelo)
    app.config["RAG_PESO_VETOR"] = 0.5
    constante = app.config["RAG_RRF_K"]
    primeiro = services.buscar(modelo, "Merenda escolar nas escolas", top_k=1, modo="hibrida_peso")[0]
    assert primeiro.similaridade == pytest.approx(1.5 / (constante + 1))


def test_peso_baixo_deixa_a_busca_por_palavras_decidir(app, origem):
    modelo = ModeloCego()
    services.indexar(modelo)
    app.config["RAG_PESO_VETOR"] = 0.0
    resultados = services.buscar(modelo, "orcamento", top_k=1, modo="hibrida_peso")
    assert _referencias(resultados) == [("evento", "70001")]


def test_o_padrao_da_busca_continua_hibrida_sem_peso(app, origem, modelo):
    services.indexar(modelo)
    primeiro = services.buscar(modelo, "Merenda escolar nas escolas", top_k=1)[0]
    assert primeiro.similaridade == pytest.approx(2 / (app.config["RAG_RRF_K"] + 1))


def test_medir_conta_o_que_foi_marcado_como_fora_do_assunto(origem, modelo):
    services.indexar(modelo)
    consultas = [{"consulta": "merenda escolar", "esperadas": [2], "fora_do_assunto": [2, 999]}]
    assert services.medir_busca(modelo, consultas, modos=("palavras",))["palavras"]["fora_do_assunto"] == 1


# ======================================================
# DECISAO 20: DISPOSITIVO
# ======================================================
def test_cpu_nunca_olha_a_placa():
    assert embeddings.escolher_dispositivo("cpu") == "cpu"


def test_dispositivo_desconhecido():
    with pytest.raises(ValueError):
        embeddings.escolher_dispositivo("tpu")


# ======================================================
# INDICE
# ======================================================
def test_reconstruir_o_indice_a_partir_de_trecho_rag(origem, modelo):
    services.indexar(modelo)
    trecho = _trecho(origem, "votacao", "2310837-8")
    id_trecho, embedding = trecho.id, trecho.embedding
    vetores.remover(id_trecho)
    origem.session.commit()
    assert id_trecho not in [achado[0] for achado in vetores.buscar(embedding, 5)]

    assert services.reconstruir_indice(MODELO) == 5
    assert vetores.buscar(embedding, 1)[0][0] == id_trecho


def test_indice_nao_entra_nas_32_tabelas(db):
    vetores.criar_indice()
    db.session.commit()
    assert "vec_trecho" not in db.metadata.tables
    assert len(db.metadata.tables) == 32


def test_drop_db_tira_os_indices(app, db):
    vetores.criar_indice()
    palavras.criar_indice()
    db.session.commit()
    resultado = app.test_cli_runner().invoke(args=["drop-db"])
    assert resultado.exit_code == 0, resultado.output
    for nome in ("vec_trecho", "trecho_fts"):
        assert db.session.execute(db.text(f"SELECT 1 FROM sqlite_master WHERE name = '{nome}'")).first() is None
    db.create_all()


# ======================================================
# COMANDOS
# ======================================================
@pytest.fixture
def comandos(app, monkeypatch, modelo):
    monkeypatch.setattr("desperta.ia.cli._modelo", lambda: modelo)
    app.config["EMBEDDING_MODEL"] = MODELO
    return app.test_cli_runner()


def test_comandos_indexar_buscar_e_reconstruir(comandos, origem):
    assert "indexados=5" in comandos.invoke(args=["ia", "indexar"]).output
    saida = comandos.invoke(args=["ia", "buscar", "merenda escolar", "--tipo", "proposicao", "--k", "1"]).output
    assert "proposicao 2:" in saida
    assert "5 trechos" in comandos.invoke(args=["ia", "reconstruir"]).output


def test_comando_indexar_com_tipo_e_limite(comandos, origem):
    assert "indexados=1" in comandos.invoke(args=["ia", "indexar", "--tipo", "proposicao", "--limite", "1"]).output


def test_comando_buscar_com_periodo(comandos, origem):
    comandos.invoke(args=["ia", "indexar"])
    saida = comandos.invoke(args=["ia", "buscar", "merenda", "--inicio", "2020-01-01", "--fim", "2020-12-31"]).output
    assert "proposicao 2:" in saida
    assert "votacao" not in saida


# ======================================================
# A API NAO CARREGA O MODELO
# ======================================================
def test_criar_a_app_nao_carrega_torch_nem_transformers():
    codigo = (
        "import sys; from desperta import create_app; create_app(); "
        "assert not {'torch', 'transformers', 'sqlite_vec'} & set(sys.modules)"
    )
    import subprocess

    subprocess.run([sys.executable, "-c", codigo], check=True)
    assert create_app(TestConfig)


# ======================================================
# GERADOR FALSO
# ======================================================
def test_gerador_e_uma_interface():
    with pytest.raises(NotImplementedError):
        Gerador().escrever("c", [])


def test_gerador_falso_marca_o_texto_como_teste():
    texto = GeradorFalso().escrever("reforma", ["um", "dois"])
    assert texto.titulo == "[TESTE] reforma"
    assert "2 trechos" in texto.resumo
    assert texto.corpo == "um\n\ndois"
    assert (texto.tokens_entrada, texto.tokens_saida) == (3, 2)


def test_gerador_falso_respeita_os_tamanhos_de_noticia():
    texto = GeradorFalso().escrever("x" * 400, [])
    assert len(texto.titulo) <= 200


# ======================================================
# EMBEDDINGS (sem baixar o modelo)
# ======================================================
torch = pytest.importorskip("torch")


class TokenizadorFalso:
    def encode(self, texto, add_special_tokens=False):
        return [int(palavra) for palavra in texto.split()]

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(str(numero) for numero in ids)

    def __call__(self, textos, padding, truncation, max_length, return_tensors):
        assert (padding, truncation, max_length, return_tensors) == (True, True, 512, "pt")
        return {
            "input_ids": torch.tensor([[1, 2], [3, 0]]),
            "attention_mask": torch.tensor([[1, 1], [1, 0]]),
        }


class RedeFalsa:
    def __call__(self, input_ids, attention_mask):
        saida = torch.zeros(2, 2, 768)
        saida[0, 0, 0] = 2.0
        saida[0, 1, 0] = 4.0
        saida[1, 0, 1] = 5.0
        # O preenchimento (mascara 0) nao pode entrar na media
        saida[1, 1, 0] = 100.0

        class Saida:
            last_hidden_state = saida

        return Saida


@pytest.fixture
def rede():
    return ModeloEmbedding("modelo", tokenizador=TokenizadorFalso(), modelo=RedeFalsa())


def test_mean_pooling_ignora_preenchimento_e_normaliza(rede):
    primeiro, segundo = rede.embutir(["a", "bb"])
    assert len(primeiro) == len(segundo) == 3072
    assert struct.unpack("768f", primeiro)[0] == pytest.approx(1.0)
    valores = struct.unpack("768f", segundo)
    assert valores[0] == 0.0
    assert valores[1] == pytest.approx(1.0)


def test_embutir_mantem_a_ordem_de_entrada(rede):
    longo, curto = rede.embutir(["texto bem mais longo", "a"])
    # O mais curto vai primeiro no lote, mas cada resultado volta para a posicao do seu texto
    assert struct.unpack("768f", curto)[0] == pytest.approx(1.0)
    assert struct.unpack("768f", longo)[1] == pytest.approx(1.0)


def test_dividir_texto_curto_fica_num_trecho_so(rede):
    assert rede.dividir("1 2 3", 400, 50) == [("1 2 3", 3)]


def test_dividir_texto_longo_com_sobreposicao(rede):
    texto = " ".join(str(numero) for numero in range(1, 8))
    assert rede.dividir(texto, 4, 1) == [("1 2 3 4", 4), ("4 5 6 7", 4)]


@pytest.mark.parametrize(
    "preferencia,tem_placa,esperado",
    [("auto", True, "cuda:0"), ("auto", False, "cpu"), ("cuda", True, "cuda:0")],
)
def test_escolher_dispositivo(monkeypatch, preferencia, tem_placa, esperado):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: tem_placa)
    assert embeddings.escolher_dispositivo(preferencia) == esperado


def test_cuda_sem_placa_para_com_erro(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(embeddings.DispositivoIndisponivel):
        embeddings.escolher_dispositivo("cuda")


@pytest.mark.skipif(not torch.cuda.is_available(), reason="sem CUDA nesta maquina")
def test_nome_da_placa_real_vai_para_o_log():
    # Vale para qualquer placa NVIDIA; no PC do Lucas, o nome mostra a RTX 4050 (20.1)
    assert torch.cuda.get_device_name(0) in embeddings.nome_do_dispositivo("cuda:0")
