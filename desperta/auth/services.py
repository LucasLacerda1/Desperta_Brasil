"""
Regras do cadastro e do login da equipe.

- atualizado_em muda so quando o cadastro muda (nome, e-mail, papel, ativo, senha); o login
  grava so ultimo_acesso (decisao 11.3).
- Administrador nunca e apagado: vira ativo = False, para manter o historico de
  noticia_revisao e log_sistema (decisao 10.4). Sempre sobra pelo menos um admin ativo.
- Tamanhos e valores conferidos aqui, antes de gravar (RNF10): o SQLite nao confere VARCHAR(n).
- Login com limite de falhas por e-mail e por IP (RNF10). A mensagem de erro e a mesma para
  e-mail desconhecido e senha errada, para nao revelar quem e da equipe.
"""

import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from desperta.ext.db import db
from desperta.ext.erros import Conflito, DadosInvalidos, MuitasTentativas, NaoAutenticado, NaoEncontrado
from desperta.sistema.models import LogSistema

from .models import ADMINISTRADOR_PAPEIS, Administrador

TAMANHO_NOME = 100
TAMANHO_EMAIL = 254
SENHA_MINIMO = 8
# Senha muito longa so serve para gastar processador no hash
SENHA_MAXIMO = 200
# Basta conferir o formato geral; o e-mail so serve para o login da equipe
FORMATO_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# O IP aguenta mais falhas que um e-mail, porque a equipe pode sair pela mesma rede
MULTIPLICADOR_DO_IP = 4
MENSAGEM_LOGIN = "E-mail ou senha incorretos."
# Conferido quando o e-mail nao existe, para a resposta demorar o mesmo que uma senha errada
_HASH_FALSO = generate_password_hash("senha-que-nao-existe")


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
    email = (email or "").strip().lower() if isinstance(email, str) else ""
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
    if not isinstance(senha, str) or len(senha) < SENHA_MINIMO:
        raise DadosInvalidos(f"A senha precisa ter pelo menos {SENHA_MINIMO} caracteres.")
    if len(senha) > SENHA_MAXIMO:
        raise DadosInvalidos(f"A senha passa de {SENHA_MAXIMO} caracteres.")
    return senha


def _ativo_valido(ativo):
    if not isinstance(ativo, bool):
        raise DadosInvalidos("O campo ativo precisa ser true ou false.")
    return ativo


def _email_livre(email, menos_id=None):
    consulta = db.select(Administrador.id).filter_by(email=email)
    if menos_id is not None:
        consulta = consulta.where(Administrador.id != menos_id)
    if db.session.scalar(consulta.limit(1)) is not None:
        raise Conflito("Ja existe alguem da equipe com este e-mail.")


def _admins_ativos(menos_id):
    consulta = db.select(db.func.count()).select_from(Administrador).filter_by(papel="admin", ativo=True)
    return db.session.scalar(consulta.where(Administrador.id != menos_id))


def _registrar(acao, descricao, por=None, alvo=None, nivel="info"):
    db.session.add(
        LogSistema(
            nivel=nivel,
            modulo="admin",
            acao=acao,
            descricao=descricao,
            admin_id=por.id if por is not None else None,
            entidade="administrador" if alvo is not None else None,
            entidade_id=str(alvo.id) if alvo is not None else None,
        )
    )


def _gravar():
    try:
        db.session.commit()
    except IntegrityError as erro:
        db.session.rollback()
        raise Conflito("O cadastro nao foi gravado: e-mail repetido ou valor invalido.") from erro


# ======================================================
# CONSULTA
# ======================================================
def como_dict(admin):
    """O que a API mostra de alguem da equipe; nunca a senha_hash."""

    def data(valor):
        return valor.isoformat() if valor else None

    return {
        "id": admin.id,
        "nome": admin.nome,
        "email": admin.email,
        "papel": admin.papel,
        "ativo": admin.ativo,
        "criado_em": data(admin.criado_em),
        "atualizado_em": data(admin.atualizado_em),
        "ultimo_acesso": data(admin.ultimo_acesso),
    }


def listar_equipe():
    """Ativos primeiro, depois por nome."""
    consulta = db.select(Administrador).order_by(Administrador.ativo.desc(), Administrador.nome)
    return list(db.session.scalars(consulta))


def buscar_administrador(admin_id):
    admin = db.session.get(Administrador, admin_id)
    if admin is None:
        raise NaoEncontrado("Membro da equipe nao encontrado.")
    return admin


# ======================================================
# CADASTRO
# ======================================================
def criar_administrador(nome, email, senha, papel="editor", por=None):
    email = _email_valido(email)
    admin = Administrador(nome=_nome_valido(nome), email=email, papel=_papel_valido(papel), ativo=True)
    admin.set_senha(_senha_valida(senha))
    _email_livre(email)
    db.session.add(admin)
    db.session.flush()
    _registrar("criar_administrador", f"Entrou na equipe: {admin.nome} ({admin.papel})", por=por, alvo=admin)
    _gravar()
    return admin


def editar_cadastro(admin, nome=None, email=None, papel=None, ativo=None, senha=None, por=None):
    """Muda so o que foi passado; atualizado_em muda so se algo mudou de verdade."""
    mudancas = []
    era_admin_ativo = admin.papel == "admin" and admin.ativo
    if nome is not None and _nome_valido(nome) != admin.nome:
        admin.nome = _nome_valido(nome)
        mudancas.append("nome")
    if email is not None:
        email = _email_valido(email)
        if email != admin.email:
            _email_livre(email, menos_id=admin.id)
            admin.email = email
            mudancas.append("e-mail")
    if papel is not None and _papel_valido(papel) != admin.papel:
        mudancas.append(f"papel {admin.papel} -> {papel}")
        admin.papel = papel
    if ativo is not None and _ativo_valido(ativo) != admin.ativo:
        admin.ativo = ativo
        mudancas.append("ativado" if ativo else "desativado")
    if senha is not None:
        admin.set_senha(_senha_valida(senha))
        mudancas.append("senha")
    if not mudancas:
        return False
    deixou_de_ser_admin = era_admin_ativo and (admin.papel != "admin" or not admin.ativo)
    if deixou_de_ser_admin and _admins_ativos(menos_id=admin.id) == 0:
        db.session.rollback()
        raise Conflito("A equipe precisa de pelo menos um admin ativo.")
    admin.atualizado_em = _agora()
    _registrar("editar_administrador", f"Cadastro de {admin.nome}: {', '.join(mudancas)}", por=por, alvo=admin)
    _gravar()
    return True


def desativar(admin, por=None):
    """Quem sai da equipe perde o acesso, mas o historico continua ligado a ele."""
    return editar_cadastro(admin, ativo=False, por=por)


def trocar_propria_senha(admin, senha_atual, senha_nova):
    if not isinstance(senha_atual, str) or not admin.confere_senha(senha_atual):
        raise DadosInvalidos("A senha atual nao confere.")
    return editar_cadastro(admin, senha=senha_nova, por=admin)


def excluir_administrador(admin):
    raise Conflito("Membro da equipe nao e apagado, para manter o historico de revisoes e do log. Use desativar.")


# ======================================================
# LIMITE DE TENTATIVAS (RNF10)
# ======================================================
# Na memoria do processo: basta para um servidor com um processo do Flask. Com varios
# processos do Gunicorn, cada um conta as suas (o limite real fica multiplicado por eles).
_falhas = defaultdict(deque)
_trava_falhas = threading.Lock()


def _recentes(chave, janela_s, agora):
    fila = _falhas[chave]
    while fila and agora - fila[0] > janela_s:
        fila.popleft()
    return len(fila)


def _bloqueado(email, ip):
    limite = current_app.config["LOGIN_TENTATIVAS"]
    janela_s = current_app.config["LOGIN_JANELA_MIN"] * 60
    agora = time.monotonic()
    with _trava_falhas:
        return (
            _recentes(("email", email), janela_s, agora) >= limite
            or _recentes(("ip", ip), janela_s, agora) >= limite * MULTIPLICADOR_DO_IP
        )


def _anotar_falha(email, ip):
    agora = time.monotonic()
    with _trava_falhas:
        _falhas[("email", email)].append(agora)
        _falhas[("ip", ip)].append(agora)


def _esquecer_falhas(email):
    with _trava_falhas:
        _falhas.pop(("email", email), None)


def limpar_tentativas():
    """Para os testes e para o admin destravar alguem pelo flask shell."""
    with _trava_falhas:
        _falhas.clear()


# ======================================================
# LOGIN
# ======================================================
def autenticar(email, senha, ip=None):
    """Devolve o administrador ou levanta NaoAutenticado / MuitasTentativas."""
    email = email.strip().lower() if isinstance(email, str) else ""
    if not email or not isinstance(senha, str) or not senha:
        raise DadosInvalidos("Informe e-mail e senha.")
    ip = ip or "desconhecido"
    if _bloqueado(email, ip):
        raise MuitasTentativas(
            f"Muitas tentativas. Espere {current_app.config['LOGIN_JANELA_MIN']} minutos e tente de novo."
        )

    admin = db.session.scalar(db.select(Administrador).filter_by(email=email[:TAMANHO_EMAIL]))
    senha = senha[:SENHA_MAXIMO]
    senha_certa = admin.confere_senha(senha) if admin is not None else check_password_hash(_HASH_FALSO, senha)
    if admin is None or not senha_certa or not admin.ativo:
        _anotar_falha(email, ip)
        _registrar("login_falhou", f"Login recusado (IP {ip[:45]})", alvo=admin, nivel="aviso")
        db.session.commit()
        raise NaoAutenticado(MENSAGEM_LOGIN)

    _esquecer_falhas(email)
    registrar_acesso(admin)
    return admin


def registrar_acesso(admin):
    """Login: so ultimo_acesso; atualizado_em fica como esta."""
    admin.ultimo_acesso = _agora()
    _registrar("login", f"{admin.nome} entrou", por=admin, alvo=admin)
    db.session.commit()
