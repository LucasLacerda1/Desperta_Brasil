from flask import Blueprint, request

from desperta.ext.api import corpo_json

from . import services, sessao

bp = Blueprint("auth", __name__)


# ======================================================
# LOGIN
# ======================================================
@bp.post("/login")
def login():
    dados = corpo_json()
    admin = services.autenticar(dados.get("email"), dados.get("senha"), ip=request.remote_addr)
    sessao.entrar(admin)
    return {"administrador": services.como_dict(admin)}


@bp.post("/logout")
def logout():
    sessao.sair()
    return "", 204


@bp.get("/eu")
@sessao.login_obrigatorio
def eu():
    return {"administrador": services.como_dict(sessao.admin_atual())}


@bp.post("/eu/senha")
@sessao.login_obrigatorio
def trocar_senha():
    dados = corpo_json()
    admin = sessao.admin_atual()
    services.trocar_propria_senha(admin, dados.get("senha_atual"), dados.get("senha_nova"))
    sessao.renovar(admin)
    return "", 204


# ======================================================
# EQUIPE (so admin)
# ======================================================
@bp.get("/equipe")
@sessao.so_admin
def listar_equipe():
    return {"itens": [services.como_dict(admin) for admin in services.listar_equipe()]}


@bp.post("/equipe")
@sessao.so_admin
def criar_membro():
    dados = corpo_json()
    admin = services.criar_administrador(
        dados.get("nome"), dados.get("email"), dados.get("senha"), dados.get("papel", "editor"),
        por=sessao.admin_atual(),
    )
    return {"administrador": services.como_dict(admin)}, 201


@bp.patch("/equipe/<int:admin_id>")
@sessao.so_admin
def editar_membro(admin_id):
    dados = corpo_json()
    campos = {c: dados[c] for c in ("nome", "email", "papel", "ativo", "senha") if c in dados}
    admin = services.buscar_administrador(admin_id)
    services.editar_cadastro(admin, por=sessao.admin_atual(), **campos)
    return {"administrador": services.como_dict(admin)}
