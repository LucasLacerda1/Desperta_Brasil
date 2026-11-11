"""
Regras do cadastro da equipe.

- atualizado_em muda so quando o cadastro muda (nome, e-mail, papel, ativo, senha); o login
  grava so ultimo_acesso (decisao 11.3).
- Administrador nunca e apagado: vira ativo = False, para manter o historico de
  noticia_revisao e log_sistema (decisao 10.4).
- Tamanhos e valores conferidos aqui, antes de gravar (RNF10): o SQLite nao confere VARCHAR(n).
"""

import re
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from desperta.ext.db import db
from desperta.ext.erros import Conflito, DadosInvalidos

from .models import ADMINISTRADOR_PAPEIS, Administrador

TAMANHO_NOME = 100
TAMANHO_EMAIL = 254
SENHA_MINIMO = 8
# Basta conferir o formato geral; o e-mail so serve para o login da equipe
FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ======================================================
# VALIDACAO
# ======================================================
def _nome_valido(nome):
    nome = (nome or "").strip()
    if not nome:
        raise DadosInvalidos("O nome e obrigatorio.")
    if len(nome) > TAMANHO_NOME:
        raise DadosInvalidos(f"O nome passa de {TAMANHO_NOME} caracteres.")
    return nome


def _email_valido(email):
    email = (email or "").strip().lower()
    if not FORMATO_EMAIL.match(email):
        raise DadosInvalidos("E-mail invalido.")
    if len(email) > TAMANHO_EMAIL:
        raise DadosInvalidos(f"O e-mail passa de {TAMANHO_EMAIL} caracteres.")
    return email


def _papel_valido(papel):
    if papel not in ADMINISTRADOR_PAPEIS:
        raise DadosInvalidos(f"Papel invalido: use {' ou '.join(ADMINISTRADOR_PAPEIS)}.")
    return papel


def _senha_valida(senha):
    if not senha or len(senha) < SENHA_MINIMO:
        raise DadosInvalidos(f"A senha precisa ter pelo menos {SENHA_MINIMO} caracteres.")
    return senha


def _email_livre(email, menos_id=None):
    consulta = db.select(Administrador.id).filter_by(email=email)
    if menos_id is not None:
        consulta = consulta.where(Administrador.id != menos_id)
    if db.session.scalar(consulta.limit(1)) is not None:
        raise Conflito("Ja existe alguem da equipe com este e-mail.")


def _gravar():
    try:
        db.session.commit()
    except IntegrityError as erro:
        db.session.rollback()
        raise Conflito("O cadastro nao foi gravado: e-mail repetido ou valor invalido.") from erro


# ======================================================
# CADASTRO
# ======================================================
def criar_administrador(nome, email, senha, papel="editor"):
    email = _email_valido(email)
    admin = Administrador(nome=_nome_valido(nome), email=email, papel=_papel_valido(papel), ativo=True)
    admin.set_senha(_senha_valida(senha))
    _email_livre(email)
    db.session.add(admin)
    _gravar()
    return admin


def editar_cadastro(admin, nome=None, email=None, papel=None, ativo=None, senha=None):
    """Muda so o que foi passado; atualizado_em muda so se algo mudou de verdade."""
    mudou = False
    if nome is not None and _nome_valido(nome) != admin.nome:
        admin.nome = _nome_valido(nome)
        mudou = True
    if email is not None:
        email = _email_valido(email)
        if email != admin.email:
            _email_livre(email, menos_id=admin.id)
            admin.email = email
            mudou = True
    if papel is not None and _papel_valido(papel) != admin.papel:
        admin.papel = papel
        mudou = True
    if ativo is not None and bool(ativo) != admin.ativo:
        admin.ativo = bool(ativo)
        mudou = True
    if senha is not None:
        admin.set_senha(_senha_valida(senha))
        mudou = True
    if mudou:
        admin.atualizado_em = _agora()
        _gravar()
    return mudou


def desativar(admin):
    """Quem sai da equipe perde o acesso, mas o historico continua ligado a ele."""
    return editar_cadastro(admin, ativo=False)


def excluir_administrador(admin):
    raise Conflito("Membro da equipe nao e apagado, para manter o historico de revisoes e do log. Use desativar.")


# ======================================================
# ACESSO
# ======================================================
def registrar_acesso(admin):
    """Login: so ultimo_acesso; atualizado_em fica como esta."""
    admin.ultimo_acesso = _agora()
    db.session.commit()
