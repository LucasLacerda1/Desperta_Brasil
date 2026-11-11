"""
Sessao da equipe (cookie assinado pelo Flask com a SECRET_KEY).

A cada requisicao, o administrador e lido de novo do banco: quem foi desativado ou trocou de
papel perde o acesso na hora. Trocar a senha encerra as outras sessoes, porque a sessao guarda
um pedaco da senha_hash, que muda a cada troca.
"""

from functools import wraps

from flask import g, session

from desperta.ext.db import db
from desperta.ext.erros import AcessoNegado, NaoAutenticado

from .models import Administrador

CHAVE_ID = "admin_id"
CHAVE_SENHA = "admin_senha"


def _marca_da_senha(admin):
    return admin.senha_hash[-16:]


def entrar(admin):
    session.clear()
    session.permanent = True
    session[CHAVE_ID] = admin.id
    session[CHAVE_SENHA] = _marca_da_senha(admin)


def sair():
    session.clear()


def admin_atual():
    """Quem esta logado, ou None. Sessao de quem foi desativado ou trocou a senha e apagada."""
    if "admin_atual" in g:
        return g.admin_atual
    admin = None
    admin_id = session.get(CHAVE_ID)
    if admin_id is not None:
        admin = db.session.get(Administrador, admin_id)
        if admin is None or not admin.ativo or session.get(CHAVE_SENHA) != _marca_da_senha(admin):
            session.clear()
            admin = None
    g.admin_atual = admin
    return admin


def renovar(admin):
    """Depois de trocar a propria senha, a sessao atual continua valendo."""
    session[CHAVE_SENHA] = _marca_da_senha(admin)


# ======================================================
# DECORADORES DAS ROTAS
# ======================================================
def login_obrigatorio(rota):
    @wraps(rota)
    def protegida(*args, **kwargs):
        if admin_atual() is None:
            raise NaoAutenticado("Entre com o seu e-mail e senha da equipe.")
        return rota(*args, **kwargs)

    return protegida


def so_admin(rota):
    @wraps(rota)
    @login_obrigatorio
    def protegida(*args, **kwargs):
        if admin_atual().papel != "admin":
            raise AcessoNegado("Esta area e so para quem tem o papel admin.")
        return rota(*args, **kwargs)

    return protegida
