import json
import re
from datetime import date, datetime

import pytest

import fabricas
from desperta.ia.gerador import (
    CASO_NOVA,
    CASO_SITUACAO,
    CASO_VOTACAO,
    DadosNoticia,
    DadosProposicao,
    DadosTramitacao,
    DadosVotacao,
    GeradorFalso,
    GeradorFrases,
    criar_gerador,
    simplificar_ementa,
)
from desperta.ia.models import GeracaoIA, GeracaoTrecho, TrechoRAG
from desperta.noticias.models import Noticia, NoticiaFonte
from desperta.noticias.services import criar_rascunho, gerar_slug
from desperta.proposicoes.models import ProposicaoAutor, ProposicaoTema
from desperta.sistema.models import LogSistema
from desperta.votacoes.models import VotacaoProposicao


def _proposicao(**campos):
    return DadosProposicao(
        **{
            "sigla": "PL",
            "numero": 1234,
            "ano": 2024,
            "descricao_tipo": "Projeto de Lei",
            "ementa": "Institui o Dia Nacional da Merenda, e dá outras providências.",
            "apresentada_em": date(2024, 5, 14),
            "autor": "Fulana de Tal",
            "situacao": "Aguardando Parecer",
            **campos,
        }
    )


def _votacao(**campos):
    return DadosVotacao(
        **{
            "descricao": "Aprovado o Projeto de Lei nº 1.234, de 2024. Sim: 300; Não: 100; Total: 400.",
            "data": date(2024, 5, 14),
            "sigla_orgao": "PLEN",
            "orgao": "PLEN",
            "aprovacao": True,
            "sim": 300,
            "nao": 100,
            **campos,
        }
    )


def _passo(**campos):
    return DadosTramitacao(
        **{"data": date(2024, 6, 3), "orgao": "CCJC", "descricao": "Parecer", "despacho": "Publique-se", **campos}
    )


def _escrever(caso, **campos):
    campos.setdefault("proposicao", _proposicao())
    return GeradorFrases().escrever("consulta", ["trecho um"], DadosNoticia(caso=caso, **campos))


# ======================================================
# EMENTA SIMPLIFICADA
# ======================================================
@pytest.mark.parametrize(
    "ementa,esperado",
    [
        ("Institui o Dia Nacional, e dá outras providências.", ("verbo", "institui o Dia Nacional")),
        ("Altera a Lei nº 9.491, de 1997, para incluir as estatais.", ("finalidade", "incluir as estatais")),
        (
            "Altera o Sistema Tributário Nacional e dá outras providências.",
            ("verbo", "altera o Sistema Tributário Nacional"),
        ),
        (
            "Altera a Lei nº 11.648, para os fins que especifica.",
            ("verbo", "altera a Lei nº 11.648, para os fins que especifica"),
        ),
        ('"Dispõe sobre o tema."', ("verbo", "dispõe sobre o tema")),
        ("Susta, nos termos do art. 49, a Portaria 1.", ("verbo", "susta, nos termos do art. 49, a Portaria 1")),
        (
            "Fica assegurada ao portador a realização do trabalho.",
            ("livre", "Fica assegurada ao portador a realização do trabalho"),
        ),
        ("Cria o programa.   NOVA EMENTA: outro texto", ("verbo", "cria o programa")),
    ],
)
def test_simplificar_ementa(ementa, esperado):
    assert simplificar_ementa(ementa) == esperado


# ======================================================
# OS TRES MODELOS DE FRASE
# ======================================================
def test_proposicao_nova():
    texto = _escrever(CASO_NOVA)
    assert texto.titulo == "Projeto institui o Dia Nacional da Merenda"
    assert texto.resumo.startswith("O PL 1234/2024, de autoria de Fulana de Tal, foi apresentado em 14/05/2024.")
    assert "Ementa oficial: Institui o Dia Nacional da Merenda." in texto.corpo


def test_proposicao_nova_com_finalidade_e_tipo_feminino():
    proposicao = _proposicao(sigla="PEC", ementa="Altera o art. 5º da Constituição para garantir o acesso.")
    texto = _escrever(CASO_NOVA, proposicao=proposicao)
    assert texto.titulo == "Proposta propõe garantir o acesso"
    assert "A PEC 1234/2024" in texto.resumo and "foi apresentada" in texto.resumo


def test_proposicao_nova_sem_autor_e_com_varios():
    assert "de autoria" not in _escrever(CASO_NOVA, proposicao=_proposicao(autor=None)).resumo
    assert "Fulana de Tal e outros" in _escrever(CASO_NOVA, proposicao=_proposicao(mais_autores=True)).resumo


def test_proposicao_nova_com_ementa_sem_verbo():
    texto = _escrever(CASO_NOVA, proposicao=_proposicao(ementa="Fica assegurada a realização."))
    assert texto.titulo == "Projeto propõe: Fica assegurada a realização"


def test_votacao_de_merito_aprovada():
    texto = _escrever(CASO_VOTACAO, votacao=_votacao())
    assert texto.titulo == "Câmara aprova projeto de lei que institui o Dia Nacional da Merenda"
    assert (
        texto.resumo
        == "O Plenário aprovou, na terça-feira (14/05/2024), o PL 1234/2024. Foram 300 votos a favor e 100 contra."
    )


def test_votacao_de_merito_rejeitada_e_em_comissao():
    votacao = _votacao(
        descricao="Rejeitado o Projeto de Lei nº 1.234.", aprovacao=False, sigla_orgao="CCJC", orgao="CCJC"
    )
    texto = _escrever(CASO_VOTACAO, votacao=votacao)
    assert texto.titulo.startswith("CCJC rejeita projeto de lei")
    assert texto.resumo.startswith("O órgão CCJC rejeitou")


def test_votacao_simbolica_nao_tem_placar():
    texto = _escrever(CASO_VOTACAO, votacao=_votacao(sim=0, nao=0))
    assert "votos" not in texto.resumo
    assert texto.resumo.endswith("o PL 1234/2024.")


def test_placar_com_abstencao_e_fim_de_semana():
    texto = _escrever(CASO_VOTACAO, votacao=_votacao(abstencao=2, data=date(2024, 5, 18)))
    assert "no sábado (18/05/2024)" in texto.resumo
    assert "com 2 de abstenção" in texto.resumo


@pytest.mark.parametrize(
    "descricao",
    [
        "Aprovado o Requerimento de Urgência (Art. 155 do RICD). Sim: 299; Não: 134; Total: 436.",
        "Aprovada a Redação Final assinada pelo relator, Dep. Fulano.",
        "Aprovada a preferência. Sim: 294; Não: 172; Total: 466.",
        "Aprovado, em apreciação preliminar, o Parecer da Comissão Mista.",
        "Aprovadas as Emendas do Senado Federal ao Projeto de Lei nº 327, de 2021.",
        "Realizar o encaminhamento do PLP-68/2024 à CEURG.",
    ],
)
def test_votacao_que_nao_e_do_projeto_nao_diz_que_a_camara_aprovou(descricao):
    # Casos reais do banco: dizer "Camara aprova projeto" aqui seria um fato falso
    texto = _escrever(CASO_VOTACAO, votacao=_votacao(descricao=descricao))
    assert "aprova projeto" not in texto.titulo
    assert "aprovou" not in texto.resumo
    assert texto.titulo.startswith("PL 1234/2024: ")
    assert "Sim:" not in texto.titulo


def test_requerimento_nunca_e_votacao_de_merito():
    proposicao = _proposicao(sigla="REQ", descricao_tipo="Requerimento")
    assert _escrever(CASO_VOTACAO, proposicao=proposicao, votacao=_votacao()).titulo.startswith("REQ 1234/2024: ")


@pytest.mark.parametrize(
    "situacao,explicacao",
    [
        ("secreta", "Votação secreta: a Câmara divulgou só o placar total (404 a favor, 61 contra e 1 abstenção)."),
        ("simbolica", "Votação simbólica: a Câmara não registra o voto de cada deputado."),
        ("pendente", "Os votos desta votação ainda estão sendo coletados."),
    ],
)
def test_votacao_explica_quando_nao_ha_o_voto_de_cada_deputado(situacao, explicacao):
    """Transparencia (05/11/2026): o texto diz por que nao ha placar por deputado."""
    votacao = _votacao(sim=0, nao=0, situacao=situacao, explicacao=explicacao)
    texto = _escrever(CASO_VOTACAO, votacao=votacao)
    assert texto.resumo.endswith(explicacao)
    assert explicacao in texto.corpo


def test_corpo_mostra_o_que_a_camara_nao_informou():
    proposicao = _proposicao(situacao=None, regime=".", apreciacao=None)
    corpo = _escrever(CASO_NOVA, proposicao=proposicao).corpo
    assert "Situação atual: não informada pela Câmara." in corpo
    assert "Regime de tramitação: não informado pela Câmara. Apreciação: não informada pela Câmara." in corpo


def test_corpo_mostra_regime_e_apreciacao_informados():
    proposicao = _proposicao(
        regime="Urgência (Art. 155, RICD)", apreciacao="Proposição Sujeita à Apreciação do Plenário"
    )
    corpo = _escrever(CASO_NOVA, proposicao=proposicao).corpo
    assert "Regime de tramitação: Urgência (Art. 155, RICD). Apreciação: Proposição Sujeita" in corpo


def test_votacao_sem_resultado_informado_e_neutra():
    assert "aprova" not in _escrever(CASO_VOTACAO, votacao=_votacao(aprovacao=None)).titulo.split(":")[0]


@pytest.mark.parametrize(
    "situacao,avanca",
    [
        ("Pronta para Pauta", True),
        ("Transformado em Norma Jurídica", True),
        ("Arquivada", False),
        ("Retirado pelo(a) Autor(a)", False),
        ("Aguardando Parecer", False),
        ("Vetado totalmente", False),
    ],
)
def test_so_avanca_quando_a_situacao_e_de_avanco(situacao, avanca):
    texto = _escrever(CASO_SITUACAO, proposicao=_proposicao(situacao=situacao), tramitacoes=[_passo()])
    assert ("avança" in texto.titulo) is avanca
    assert f'"{situacao}"' in texto.resumo
    assert "Em 03/06/2024, em CCJC: Publique-se." in texto.resumo


def test_titulo_de_situacao_mostra_a_situacao_como_a_camara_escreve():
    texto = _escrever(CASO_SITUACAO, proposicao=_proposicao(situacao="Aguardando Designação de Relator(a)"))
    assert texto.titulo == 'PL 1234/2024: situação agora é "Aguardando Designação de Relator(a)"'


def test_situacao_nula_usa_a_ultima_tramitacao():
    texto = _escrever(
        CASO_SITUACAO,
        proposicao=_proposicao(situacao=None),
        tramitacoes=[_passo(descricao="Designado relator", despacho="")],
    )
    assert "Designado relator" in texto.resumo
    assert "Em 03/06/2024, em CCJC: Designado relator." in texto.corpo


def test_sem_situacao_e_sem_tramitacao_nao_escreve():
    with pytest.raises(ValueError):
        _escrever(CASO_SITUACAO, proposicao=_proposicao(situacao=None))


def test_corpo_traz_so_as_tres_ultimas_tramitacoes():
    passos = [_passo(despacho=f"Despacho {numero}") for numero in range(1, 6)]
    corpo = _escrever(CASO_NOVA, tramitacoes=passos).corpo
    assert "Despacho 2" not in corpo and all(f"Despacho {numero}" in corpo for numero in (3, 4, 5))


def test_precisa_dos_registros():
    with pytest.raises(ValueError):
        GeradorFrases().escrever("c", [])


# ======================================================
# NUNCA INVENTA
# ======================================================
def _numeros(texto):
    return set(re.findall(r"\d+", texto))


@pytest.mark.parametrize(
    "caso,campos",
    [
        (CASO_NOVA, {}),
        (CASO_SITUACAO, {"tramitacoes": [_passo()]}),
        (CASO_VOTACAO, {"votacao": _votacao(abstencao=7), "tramitacoes": [_passo()]}),
        (CASO_VOTACAO, {"votacao": _votacao(descricao="Aprovado o Requerimento nº 55. Sim: 300; Não: 100.")}),
    ],
)
def test_todo_numero_do_texto_existe_nos_dados(caso, campos):
    dados = DadosNoticia(caso=caso, proposicao=_proposicao(), **campos)
    texto = GeradorFrases().escrever("consulta", [], dados)
    entrada = f"{dados.proposicao} {dados.votacao} {dados.tramitacoes}"
    permitidos = _numeros(entrada)
    for data in (
        [dados.proposicao.apresentada_em]
        + [v.data for v in (dados.votacao,) if v]
        + [p.data for p in dados.tramitacoes]
    ):
        permitidos |= {f"{data:%d}", f"{data:%m}", f"{data:%Y}"}
    if dados.votacao:
        permitidos |= {str(dados.votacao.sim), str(dados.votacao.nao), str(dados.votacao.abstencao)}
    assert _numeros(f"{texto.titulo} {texto.resumo} {texto.corpo}") <= permitidos


def test_trechos_do_rag_nao_entram_no_texto():
    texto = GeradorFrases().escrever("c", ["PL 9999/1999 de outro projeto"], DadosNoticia(CASO_NOVA, _proposicao()))
    assert "9999" not in f"{texto.titulo} {texto.resumo} {texto.corpo}"


def test_cabe_nos_tamanhos_de_noticia_sem_partir_palavra():
    ementa = "Institui " + "palavra " * 200
    texto = _escrever(CASO_NOVA, proposicao=_proposicao(ementa=ementa))
    assert len(texto.titulo) <= 200 and len(texto.resumo) <= 500
    assert texto.titulo.endswith("palavra…")


# ======================================================
# CONFIGURACAO
# ======================================================
def test_padrao_e_o_gerador_de_frases(app):
    assert app.config["GERADOR"] == "frases"
    assert criar_gerador("frases").nome == "frases-v1"
    assert isinstance(criar_gerador("falso"), GeradorFalso)


@pytest.mark.parametrize("nome", ["roberta", "outro"])
def test_gerador_que_ainda_nao_existe(nome):
    with pytest.raises(ValueError):
        criar_gerador(nome)


# ======================================================
# SLUG E RASCUNHO
# ======================================================
def test_slug_sem_acento_unico_e_no_tamanho(db):
    db.session.add(fabricas.tema())
    assert gerar_slug("Câmara aprova: reforma, já!") == "camara-aprova-reforma-ja"
    assert gerar_slug("???") == "noticia"
    assert len(gerar_slug("a" * 300)) == 220
    criar_rascunho("Título igual", "r", "c", 46, [])
    criar_rascunho("Titulo igual", "r", "c", 46, [])
    db.session.flush()
    assert gerar_slug("titulo igual") == "titulo-igual-3"


# ======================================================
# GERAR A NOTICIA
# ======================================================
@pytest.fixture
def banco(app, db):
    pytest.importorskip("sqlite_vec")
    db.session.add_all(
        [
            fabricas.orgao(),
            fabricas.tema(),
            fabricas.tema(cod_tema=47, nome="Saude", icone="health"),
            fabricas.proposicao(ementa="Institui o Dia Nacional da Merenda.", situacao="Pronta para Pauta"),
            fabricas.tramitacao(),
            fabricas.votacao(descricao="Aprovado o Projeto de Lei nº 1.234.", aprovacao=True),
        ]
    )
    db.session.flush()
    db.session.add_all(
        [
            ProposicaoTema(proposicao_id=2310837, cod_tema=46, relevancia=1),
            ProposicaoTema(proposicao_id=2310837, cod_tema=47, relevancia=5),
            ProposicaoAutor(
                proposicao_id=2310837, ordem=1, nome="Fulana", cod_tipo=1, tipo="Deputado(a)", proponente=True
            ),
            VotacaoProposicao(votacao_id="2310837-8", proposicao_id=2310837),
            TrechoRAG(
                tipo="proposicao",
                ref_id="2310837",
                parte=1,
                texto="PL 1234/2024. Institui o Dia Nacional da Merenda.",
                tokens=8,
                embedding=bytes(3072),
                modelo_embedding="m",
                hash_texto="a" * 64,
            ),
        ]
    )
    db.session.commit()
    return db


def _gerar(caso="nova", ref=2310837, gerador=None):
    from desperta.ia.geracao import gerar_noticia

    return gerar_noticia(None, caso, ref, gerador)


def test_gerar_grava_rascunho_geracao_trechos_e_fontes(banco):
    geracao, nova = _gerar()
    assert nova is True
    noticia = geracao.noticia
    assert (noticia.status, noticia.origem, noticia.tipo) == ("rascunho", "ia", "noticia")
    assert noticia.cod_tema == 47
    assert noticia.titulo == "Projeto institui o Dia Nacional da Merenda."[:-1]
    assert noticia.slug == "projeto-institui-o-dia-nacional-da-merenda"
    assert (geracao.status, geracao.modelo_geracao, geracao.versao_prompt) == ("ok", "frases-v1", "frases-v1")
    assert geracao.duracao_ms >= 0 and geracao.tokens_saida > 0
    assert json.loads(geracao.entrada)["proposicao_id"] == 2310837
    ligado = banco.session.scalar(banco.select(GeracaoTrecho).filter_by(geracao_id=geracao.id))
    assert ligado.posicao == 1 and ligado.similaridade > 0
    assert [(f.tipo, f.ref_id, f.ordem) for f in noticia.fontes] == [("proposicao", "2310837", 1)]


def test_gerar_votacao_tem_a_votacao_como_fonte_principal(banco):
    banco.session.add_all([fabricas.legislatura(), fabricas.deputado(), fabricas.voto()])
    banco.session.get(fabricas.Votacao, "2310837-8").filhos_sincronizados_em = datetime(2024, 5, 15)
    banco.session.commit()
    geracao, _ = _gerar("votacao", "2310837-8")
    assert geracao.noticia.titulo.startswith("Câmara aprova projeto de lei que institui")
    assert "Foi 1 voto a favor e 0 contra." in geracao.noticia.resumo
    assert [(f.tipo, f.ref_id) for f in geracao.noticia.fontes] == [
        ("votacao", "2310837-8"),
        ("proposicao", "2310837"),
        ("orgao", "180"),
    ]


def test_votacao_prefere_a_proposicao_de_tipo_acompanhado(banco):
    banco.session.add(
        fabricas.proposicao(id=9, sigla_tipo="REQ", descricao_tipo="Requerimento", numero=9, ementa="Urgencia")
    )
    banco.session.flush()
    banco.session.add(VotacaoProposicao(votacao_id="2310837-8", proposicao_id=9))
    banco.session.get(fabricas.Votacao, "2310837-8").proposicao_id = 9
    banco.session.commit()
    geracao, _ = _gerar("votacao", "2310837-8")
    assert json.loads(geracao.entrada)["proposicao_id"] == 2310837


def test_gerar_de_novo_nao_duplica_e_mudanca_de_status_gera(banco):
    primeira, _ = _gerar("situacao")
    segunda, nova = _gerar("situacao")
    assert nova is False and segunda.id == primeira.id
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(Noticia)) == 1
    banco.session.get(fabricas.Proposicao, 2310837).data_status = datetime(2025, 1, 1)
    banco.session.commit()
    assert _gerar("situacao")[1] is True


def test_proposicao_sem_data_da_situacao_tambem_gera(banco):
    """Fase 2b: data_status pode vir vazio da Camara."""
    banco.session.get(fabricas.Proposicao, 2310837).data_status = None
    banco.session.commit()
    geracao, nova = _gerar()
    assert (geracao.status, nova) == ("ok", True)
    assert json.loads(geracao.entrada)["data_status"] is None


def test_noticia_rejeitada_pode_ser_refeita(banco):
    primeira, _ = _gerar()
    primeira.noticia.status = "rejeitada"
    banco.session.commit()
    segunda, nova = _gerar()
    assert nova is True and segunda.noticia_id != primeira.noticia_id


@pytest.mark.parametrize(
    "caso,ref,mensagem",
    [("nova", 999, "nao encontrada"), ("votacao", "1-1", "nao encontrada")],
)
def test_erro_grava_geracao_sem_noticia_e_log(banco, caso, ref, mensagem):
    geracao, _ = _gerar(caso, ref)
    assert geracao.status == "erro" and geracao.noticia_id is None
    assert mensagem in geracao.erro
    assert banco.session.scalar(banco.select(LogSistema).filter_by(acao="gerar_noticia", nivel="erro"))
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(Noticia)) == 0


def test_proposicao_sem_tema_vira_erro_e_nao_noticia(banco):
    banco.session.add(fabricas.proposicao(id=7, numero=7))
    banco.session.commit()
    geracao, _ = _gerar(ref=7)
    assert geracao.status == "erro"
    assert "nao tem tema" in geracao.erro


def test_falha_do_gerador_nao_deixa_noticia_pela_metade(banco):
    class Quebrado(GeradorFalso):
        def escrever(self, consulta, trechos, dados=None):
            raise RuntimeError("quebrou")

    geracao, _ = _gerar(gerador=Quebrado())
    assert (geracao.status, geracao.erro, geracao.modelo_geracao) == ("erro", "quebrou", "gerador-falso")
    assert banco.session.scalar(banco.select(banco.func.count()).select_from(NoticiaFonte)) == 0


def test_gerador_da_configuracao_invalido_tambem_grava_erro(app, banco):
    app.config["GERADOR"] = "roberta"
    geracao, _ = _gerar()
    assert geracao.status == "erro" and "Fase 3b" in geracao.erro
    assert banco.session.get(GeracaoIA, geracao.id).modelo_geracao == "roberta"


def test_sem_o_pendrive_o_comando_gera_so_com_palavras(app, banco, tmp_path):
    app.config["ROBERTA_DIR"] = str(tmp_path / "pendrive")
    resultado = app.test_cli_runner().invoke(args=["ia", "gerar", "nova", "2310837"])
    assert resultado.exit_code == 0, resultado.output
    assert "Usando só a busca por palavras" in resultado.output
    assert "Projeto institui" in resultado.output
    assert banco.session.scalar(banco.select(LogSistema).filter_by(acao="roberta_ausente"))
    assert banco.session.scalar(banco.select(GeracaoTrecho))


def test_comando_gerar_avisa_duplicata_e_erro(app, banco, tmp_path):
    app.config["ROBERTA_DIR"] = str(tmp_path / "pendrive")
    executor = app.test_cli_runner()
    executor.invoke(args=["ia", "gerar", "nova", "2310837"])
    assert "nada foi gerado" in executor.invoke(args=["ia", "gerar", "nova", "2310837"]).output
    erro = executor.invoke(args=["ia", "gerar", "nova", "999"])
    assert erro.exit_code != 0 and "nao encontrada" in erro.output


def test_gerar_votacao_secreta_usa_o_placar_da_camara(banco):
    banco.session.add_all([fabricas.legislatura(), fabricas.deputado()])
    votacao = banco.session.get(fabricas.Votacao, "2310837-8")
    votacao.descricao = "Aprovado o Projeto de Lei nº 1.234. Sim: 1; Não: 0; Total: 1."
    votacao.filhos_sincronizados_em = datetime(2024, 5, 15)
    banco.session.flush()
    banco.session.add(fabricas.voto(tipo_voto=None))
    banco.session.commit()
    geracao, _ = _gerar("votacao", "2310837-8")
    assert "Votação secreta: a Câmara divulgou só o placar total (1 a favor e 0 contra)." in geracao.noticia.resumo
