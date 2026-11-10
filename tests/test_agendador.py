import os
import sys
from collections import Counter

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "agendador"))

import agendador  # noqa: E402

from desperta.ia import automatico, embeddings, services  # noqa: E402
from desperta.sistema.models import LogSistema  # noqa: E402


# ======================================================
# UNIDADES DO SYSTEMD
# ======================================================
def test_unidades_tem_o_servico_e_os_quatro_timers():
    arquivos = agendador.unidades(projeto="/srv/desperta", flask="/srv/desperta/.venv/bin/flask")
    assert set(arquivos) == {
        "desperta-coleta@.service",
        "desperta-horaria.timer",
        "desperta-diaria.timer",
        "desperta-semanal.timer",
        "desperta-mensal.timer",
    }
    servico = arquivos["desperta-coleta@.service"]
    assert "WorkingDirectory=/srv/desperta\n" in servico
    assert "ExecStart=/srv/desperta/.venv/bin/flask --app app.py coletar agendada %i\n" in servico
    assert "append:/srv/desperta/instance/agendador.log" in servico
    assert "Type=oneshot" in servico


@pytest.mark.parametrize(
    "rotina, calendario, persistente",
    [
        ("horaria", "*-*-* *:05:00", "false"),
        ("diaria", "*-*-* 03:30:00", "true"),
        ("semanal", "Sun *-*-* 04:30:00", "true"),
        ("mensal", "*-*-01 05:30:00", "true"),
    ],
)
def test_calendario_do_rf02(rotina, calendario, persistente):
    timer = agendador.unidades(projeto="/p", flask="/p/flask")[f"desperta-{rotina}.timer"]
    assert f"OnCalendar={calendario}\n" in timer
    assert f"Persistent={persistente}\n" in timer
    assert f"Unit=desperta-coleta@{rotina}.service\n" in timer
    assert "WantedBy=timers.target" in timer


def test_caminhos_vem_do_projeto_e_do_python_que_rodou():
    """Decisao 21.4: nenhum caminho do PC do Lucas escrito no codigo."""
    servico = agendador.unidades()["desperta-coleta@.service"]
    assert f"WorkingDirectory={agendador.PROJETO}\n" in servico
    assert os.path.join(os.path.dirname(sys.executable), "flask") in servico
    with open(agendador.__file__, encoding="utf-8") as arquivo:
        assert "/home/" not in arquivo.read()


def test_instalar_e_remover(tmp_path):
    comandos = []

    def rodar(args, check):
        comandos.append(args[2:])

    agendador.instalar(str(tmp_path), rodar=rodar)
    assert sorted(os.listdir(tmp_path)) == sorted(agendador.unidades())
    assert comandos == [
        ["daemon-reload"],
        ["enable", "--now", "desperta-horaria.timer", "desperta-diaria.timer", "desperta-semanal.timer",
         "desperta-mensal.timer"],
    ]

    comandos.clear()
    agendador.remover(str(tmp_path), rodar=rodar)
    assert os.listdir(tmp_path) == []
    assert comandos[0][:2] == ["disable", "--now"] and comandos[-1] == ["daemon-reload"]


def test_acao_desconhecida_mostra_a_ajuda(capsys):
    assert agendador.main(["agendador.py", "outra"]) == 1
    assert "instalar" in capsys.readouterr().out


# ======================================================
# IA DEPOIS DA COLETA
# ======================================================
@pytest.fixture
def geracao_falsa(monkeypatch):
    modelos = []

    def gerar_novos(modelo, *args, **kwargs):
        modelos.append(modelo)
        return automatico.Resumo(inicio=None)

    monkeypatch.setattr(automatico, "gerar_novos", gerar_novos)
    return modelos


def test_com_modelo_indexa_e_escreve(app, db, monkeypatch, geracao_falsa):
    modelo = object()
    monkeypatch.setattr(services, "carregar_modelo", lambda: modelo)
    monkeypatch.setattr(services, "indexar", lambda m: Counter(indexados=2) if m is modelo else None)
    indexacao, _ = automatico.depois_da_coleta()
    assert indexacao["indexados"] == 2
    assert geracao_falsa == [modelo]


def test_sem_a_roberta_nao_indexa_e_escreve_so_com_palavras(app, db, monkeypatch, geracao_falsa):
    """Decisao 21.3: sem o pendrive, a indexacao fica para a proxima vez e a geracao continua."""

    def ausente():
        raise embeddings.RobertaAusente("RoBERTaLexPT não encontrada")

    monkeypatch.setattr(services, "carregar_modelo", ausente)
    monkeypatch.setattr(services, "indexar", lambda m: pytest.fail("nao devia indexar"))
    indexacao, _ = automatico.depois_da_coleta()
    assert indexacao is None
    assert geracao_falsa == [None]


@pytest.mark.parametrize(
    "erro", [ImportError("No module named 'torch'"), embeddings.DispositivoIndisponivel("sem CUDA")]
)
def test_sem_pytorch_ou_sem_placa_avisa_no_log(app, db, monkeypatch, geracao_falsa, erro):
    def quebrar():
        raise erro

    monkeypatch.setattr(services, "carregar_modelo", quebrar)
    assert automatico.carregar_modelo_ou_nada() is None
    aviso = db.session.scalar(db.select(LogSistema).where(LogSistema.acao == "modelo_indisponivel"))
    assert aviso.nivel == "aviso" and aviso.modulo == "IA"
