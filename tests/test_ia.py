import hashlib
import math
import struct
import sys
from datetime import date, datetime

import pytest

import fabricas
from desperta import create_app
from desperta.config import TestConfig
from desperta.ia import services, trechos, vetores
from desperta.ia.embeddings import ModeloEmbedding
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
def origem(db):
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
        "14/05/2024 PLEN. Aguardando parecer Encaminhe-se a comissao de saude"
    )
    assert textos[("votacao", "2310837-8")] == "Aprovado o projeto de merenda PLEN, 14/05/2024. Resultado: aprovada."
    assert textos[("evento", "70001")] == "Sessao Deliberativa. Sessao sobre orcamento"


def test_tramitacao_sem_situacao_e_sem_despacho_nao_vira_trecho(origem):
    assert ("tramitacao", "2310837/2") not in {(tipo, ref) for tipo, ref, _ in trechos.textos_de_origem()}


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
    resultados = services.buscar(modelo, "merenda escolar nas escolas", top_k=2)
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


def test_drop_db_tira_o_indice(app, db):
    vetores.criar_indice()
    db.session.commit()
    resultado = app.test_cli_runner().invoke(args=["drop-db"])
    assert resultado.exit_code == 0, resultado.output
    assert db.session.execute(db.text("SELECT 1 FROM sqlite_master WHERE name = 'vec_trecho'")).first() is None
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
def embeddings():
    return ModeloEmbedding("modelo", tokenizador=TokenizadorFalso(), modelo=RedeFalsa())


def test_mean_pooling_ignora_preenchimento_e_normaliza(embeddings):
    primeiro, segundo = embeddings.embutir(["a", "bb"])
    assert len(primeiro) == len(segundo) == 3072
    assert struct.unpack("768f", primeiro)[0] == pytest.approx(1.0)
    valores = struct.unpack("768f", segundo)
    assert valores[0] == 0.0
    assert valores[1] == pytest.approx(1.0)


def test_embutir_mantem_a_ordem_de_entrada(embeddings):
    longo, curto = embeddings.embutir(["texto bem mais longo", "a"])
    # O mais curto vai primeiro no lote, mas cada resultado volta para a posicao do seu texto
    assert struct.unpack("768f", curto)[0] == pytest.approx(1.0)
    assert struct.unpack("768f", longo)[1] == pytest.approx(1.0)


def test_dividir_texto_curto_fica_num_trecho_so(embeddings):
    assert embeddings.dividir("1 2 3", 400, 50) == [("1 2 3", 3)]


def test_dividir_texto_longo_com_sobreposicao(embeddings):
    texto = " ".join(str(numero) for numero in range(1, 8))
    assert embeddings.dividir(texto, 4, 1) == [("1 2 3 4", 4), ("4 5 6 7", 4)]
