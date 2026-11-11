from datetime import datetime

import pytest

import fabricas
from desperta.auth import services
from desperta.auth.models import Administrador
from desperta.ext.erros import Conflito, DadosInvalidos, MuitasTentativas, NaoAutenticado
from desperta.sistema.models import LogSistema

ANTIGO = datetime(2020, 1, 1, 12, 0)


@pytest.fixture
def admin(db):
    pessoa = fabricas.administrador(atualizado_em=ANTIGO)
    db.session.add(pessoa)
    db.session.commit()
    return pessoa


# ======================================================
# CRIAR
# ======================================================
def test_criar_administrador_grava_hash_e_padroes(db):
    pessoa = services.criar_administrador(" Caio ", " Caio@Desperta.org ", "senha-forte")
    assert (pessoa.nome, pessoa.email, pessoa.papel, pessoa.ativo) == ("Caio", "caio@desperta.org", "editor", True)
    assert pessoa.senha_hash != "senha-forte"
    assert pessoa.confere_senha("senha-forte")


def test_criar_com_email_repetido_da_409(db, admin):
    with pytest.raises(Conflito):
        services.criar_administrador("Outro", admin.email.upper(), "senha-forte")
    assert db.session.scalar(db.select(db.func.count()).select_from(Administrador)) == 1


@pytest.mark.parametrize(
    "campos",
    [
        {"nome": ""},
        {"nome": "x" * 101},
        {"email": "sem-arroba"},
        {"email": "a@" + "b" * 250 + ".org"},
        {"senha": "curta"},
        {"papel": "dono"},
    ],
)
def test_criar_confere_os_campos_antes_de_gravar(db, campos):
    dados = {"nome": "Rhuan", "email": "rhuan@desperta.org", "senha": "senha-forte", "papel": "editor", **campos}
    with pytest.raises(DadosInvalidos):
        services.criar_administrador(**dados)
    assert db.session.scalar(db.select(Administrador)) is None


# ======================================================
# EDITAR (decisao 11.3)
# ======================================================
@pytest.mark.parametrize(
    "mudanca",
    [
        {"nome": "Lucas Freire"},
        {"email": "outro@desperta.org"},
        {"papel": "admin"},
        {"ativo": False},
        {"senha": "nova-senha"},
    ],
)
def test_editar_cadastro_muda_atualizado_em(db, admin, mudanca):
    assert services.editar_cadastro(admin, **mudanca) is True
    db.session.expire_all()
    assert admin.atualizado_em > ANTIGO


def test_editar_sem_mudanca_real_nao_mexe_em_atualizado_em(db, admin):
    assert services.editar_cadastro(admin, nome=admin.nome, email=admin.email, papel=admin.papel, ativo=True) is False
    db.session.expire_all()
    assert admin.atualizado_em == ANTIGO


def test_editar_para_email_de_outra_pessoa_da_409(db, admin):
    services.criar_administrador("Caio", "caio@desperta.org", "senha-forte")
    with pytest.raises(Conflito):
        services.editar_cadastro(admin, email="caio@desperta.org")


def test_trocar_senha_vale_no_login(db, admin):
    services.editar_cadastro(admin, senha="outra-senha")
    assert admin.confere_senha("outra-senha") and not admin.confere_senha("senha-de-teste")


# ======================================================
# LOGIN, DESATIVAR E APAGAR (decisao 10.4)
# ======================================================
def test_registrar_acesso_grava_so_ultimo_acesso(db, admin):
    services.registrar_acesso(admin)
    db.session.expire_all()
    assert admin.ultimo_acesso is not None
    assert admin.atualizado_em == ANTIGO


def test_desativar_mantem_o_cadastro(db, admin):
    services.desativar(admin)
    db.session.expire_all()
    assert admin.ativo is False
    assert db.session.get(Administrador, admin.id) is not None


def test_administrador_nao_e_apagado(db, admin):
    with pytest.raises(Conflito):
        services.excluir_administrador(admin)
    assert db.session.get(Administrador, admin.id) is not None


# ======================================================
# ULTIMO ADMIN E LOGIN
# ======================================================
def test_ultimo_admin_ativo_nao_e_desativado_nem_rebaixado(db, admin):
    services.editar_cadastro(admin, papel="admin")
    for mudanca in ({"ativo": False}, {"papel": "editor"}):
        with pytest.raises(Conflito):
            services.editar_cadastro(admin, **mudanca)
        db.session.expire_all()
        assert (admin.papel, admin.ativo) == ("admin", True)
    services.criar_administrador("Caio", "caio@desperta.org", "senha-forte", papel="admin")
    assert services.desativar(admin) is True


@pytest.fixture
def sem_falhas(app):
    services.limpar_tentativas()
    yield
    services.limpar_tentativas()


def test_autenticar_certo_grava_ultimo_acesso_e_log(db, admin, sem_falhas):
    assert services.autenticar(" LUCAS@desperta.org ", "senha-de-teste", ip="10.0.0.1") is admin
    assert admin.ultimo_acesso is not None
    assert db.session.scalar(db.select(LogSistema).filter_by(acao="login")).admin_id == admin.id


@pytest.mark.parametrize("email, senha", [("lucas@desperta.org", "errada-123"), ("ninguem@desperta.org", "x" * 9)])
def test_autenticar_errado_tem_a_mesma_mensagem(db, admin, sem_falhas, email, senha):
    with pytest.raises(NaoAutenticado) as erro:
        services.autenticar(email, senha, ip="10.0.0.1")
    assert erro.value.mensagem == services.MENSAGEM_LOGIN
    assert db.session.scalar(db.select(LogSistema).filter_by(acao="login_falhou")).nivel == "aviso"


def test_desativado_nao_entra(db, admin, sem_falhas):
    services.desativar(admin)
    with pytest.raises(NaoAutenticado):
        services.autenticar("lucas@desperta.org", "senha-de-teste")


def test_muitas_falhas_bloqueiam_ate_a_senha_certa(db, admin, sem_falhas, app):
    for _ in range(app.config["LOGIN_TENTATIVAS"]):
        with pytest.raises(NaoAutenticado):
            services.autenticar("lucas@desperta.org", "errada-123", ip="10.0.0.1")
    with pytest.raises(MuitasTentativas):
        services.autenticar("lucas@desperta.org", "senha-de-teste", ip="10.0.0.2")


def test_trocar_propria_senha_confere_a_atual(db, admin):
    with pytest.raises(DadosInvalidos):
        services.trocar_propria_senha(admin, "errada-123", "nova-senha-1")
    assert services.trocar_propria_senha(admin, "senha-de-teste", "nova-senha-1") is True
    assert admin.confere_senha("nova-senha-1")
