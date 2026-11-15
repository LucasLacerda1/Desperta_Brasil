import json
import logging
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError, StatementError

from desperta.ext.db import db
from desperta.sistema.models import Coleta, LogSistema

from .cliente import ErroAPI, TempoEsgotado
from .normalizacao import agora_utc, calcular_hash

logger = logging.getLogger(__name__)

NOVO = "novo"
ATUALIZADO = "atualizado"
IGUAL = "igual"
MAX_FALHAS_API_SEGUIDAS = 5
# O detalhe do proprio item deu 404: a Camara nao tem mais o registro (23.12). Nao e falha da coleta.
ACAO_AUSENTE = "nao_encontrado_na_camara"


# === Execucao (uma coleta: grava registros, conta e registra erros) ===
class Execucao:
    def __init__(self, cliente, recurso, tipo, endpoint, parametros=None, data_inicio_ref=None, data_fim_ref=None):
        self.cliente = cliente
        self.inicio = agora_utc()
        self.falhas = 0
        self.ausentes = 0
        self.ausentes_pulados = 0
        self._ausentes_recentes = {}
        self._falhas_api_seguidas = 0
        self._requisicoes_antes = cliente.requisicoes
        self._erros_http_antes = cliente.erros_http
        self.coleta = Coleta(
            recurso=recurso,
            tipo=tipo,
            endpoint=endpoint,
            parametros=json.dumps(parametros, ensure_ascii=False, default=str) if parametros else None,
            data_inicio_ref=data_inicio_ref,
            data_fim_ref=data_fim_ref,
            iniciado_em=self.inicio,
            # So vira ok no fim; se o processo morrer no meio, a coleta nao conta como concluida
            status="parcial",
        )
        db.session.add(self.coleta)
        db.session.commit()

    def __enter__(self):
        return self

    def __exit__(self, tipo_erro, erro, rastro):
        if erro is None:
            self.finalizar()
            return False
        db.session.rollback()
        if isinstance(erro, ErroAPI):
            # A API caiu de vez: o que ja foi gravado fica, e o erro nao derruba as proximas coletas
            self.log("erro", "falha_api", str(erro))
            self.finalizar(status="erro", mensagem=str(erro))
            return True
        if isinstance(erro, TempoEsgotado):
            # Decisao 14.2: o item em andamento foi desfeito e sera buscado de novo
            self.log("aviso", "tempo_esgotado", str(erro))
            self.finalizar(status="parcial", mensagem=str(erro))
            return True
        self.finalizar(status="erro", mensagem=f"{type(erro).__name__}: {erro}")
        return False

    # ------------------------------------------------------
    # GRAVACAO
    # ------------------------------------------------------
    def _proteger(self, modelo, chave, gravar):
        """Cada registro em begin_nested: se falhar, desfaz so ele, registra e segue (decisao 10.2)."""
        try:
            with db.session.begin_nested():
                return gravar()
        except (IntegrityError, StatementError, ValueError, TypeError) as erro:
            self.registrar_falha(modelo.__tablename__, chave, erro)
            return None

    def registrar_falha(self, tabela, chave, erro):
        self.falhas += 1
        descricao = str(getattr(erro, "orig", None) or erro)
        self.log("erro", "gravar_registro", descricao, entidade=tabela, entidade_id=_id_texto(chave))

    def principal(self, modelo, chave, valores, ajustar=None):
        """
        Upsert de registro principal pelo hash_origem:
        novo conta em itens_novos, hash diferente em itens_atualizados, igual so marca sincronizado_em.
        ajustar(registro, valores) permite ao modulo trocar valores antes de comparar.
        Devolve o registro, ou None se a gravacao falhou.
        """
        self.coleta.total_itens += 1
        resultado = self._proteger(modelo, chave, lambda: self._upsert_principal(modelo, chave, valores, ajustar))
        if resultado is None:
            return None
        registro, situacao = resultado
        if situacao == NOVO:
            self.coleta.itens_novos += 1
        elif situacao == ATUALIZADO:
            self.coleta.itens_atualizados += 1
        registro.situacao_coleta = situacao
        return registro

    def _upsert_principal(self, modelo, chave, valores, ajustar):
        registro = (
            db.session.get(modelo, chave)
            if not isinstance(chave, dict)
            else (db.session.scalar(db.select(modelo).filter_by(**chave)))
        )
        if registro is not None and ajustar is not None:
            valores = ajustar(registro, valores)
        hash_origem = calcular_hash(valores)
        if registro is None:
            registro = modelo(
                **valores, hash_origem=hash_origem, atualizado_em=self.inicio, sincronizado_em=self.inicio
            )
            db.session.add(registro)
            db.session.flush()
            return registro, NOVO
        registro.sincronizado_em = self.inicio
        if registro.hash_origem == hash_origem:
            db.session.flush()
            return registro, IGUAL
        for coluna, valor in valores.items():
            setattr(registro, coluna, valor)
        registro.hash_origem = hash_origem
        registro.atualizado_em = self.inicio
        db.session.flush()
        return registro, ATUALIZADO

    def vinculo(self, modelo, chave, valores):
        """Upsert de linha filha ou associativa; devolve True se gravou."""
        self.coleta.total_itens += 1
        resultado = self._proteger(modelo, chave, lambda: self._upsert_vinculo(modelo, chave, valores))
        if resultado is None:
            return False
        if resultado == NOVO:
            self.coleta.itens_novos += 1
        elif resultado == ATUALIZADO:
            self.coleta.itens_atualizados += 1
        return True

    def _upsert_vinculo(self, modelo, chave, valores):
        registro = db.session.get(modelo, chave)
        if registro is None:
            db.session.add(modelo(**valores, sincronizado_em=self.inicio))
            db.session.flush()
            return NOVO
        mudou = False
        for coluna, valor in valores.items():
            if getattr(registro, coluna) != valor:
                setattr(registro, coluna, valor)
                mudou = True
        registro.sincronizado_em = self.inicio
        db.session.flush()
        return ATUALIZADO if mudou else IGUAL

    def remover_sumidos(self, modelo, *filtros):
        """Apaga as linhas daquele pai que nao vieram nesta coleta (sincronizado_em anterior ao inicio)."""
        db.session.execute(db.delete(modelo).where(*filtros, modelo.sincronizado_em < self.inicio))

    # ------------------------------------------------------
    # REGISTRO
    # ------------------------------------------------------
    def log(self, nivel, acao, descricao, entidade=None, entidade_id=None):
        db.session.add(
            LogSistema(
                nivel=nivel,
                modulo="coletor",
                acao=acao[:100],
                descricao=descricao,
                coleta_id=self.coleta.id,
                entidade=entidade,
                entidade_id=_id_texto(entidade_id),
            )
        )
        if nivel == "erro":
            logger.warning("%s %s: %s", entidade or "-", entidade_id or "-", descricao)

    def processar(self, tabela, chave, funcao):
        """
        Processa um item pai: erro de API desse item nao derruba a coleta, mas
        varias falhas seguidas indicam que a API caiu, e a coleta para.
        Item que a Camara nao tem mais (404 no proprio detalhe) vira aviso, nao falha,
        e fica sem ser pedido de novo por COLETOR_AUSENTE_HORAS.
        Devolve True se o item terminou sem erro de API.
        """
        if _id_texto(chave) in self._ausentes_desde_ha_pouco(tabela):
            self.ausentes_pulados += 1
            return False
        try:
            funcao()
        except ErroAPI as erro:
            db.session.rollback()
            if _item_nao_existe(erro, chave):
                self._registrar_ausente(tabela, chave, erro)
                # A API respondeu: nao conta como queda
                self._falhas_api_seguidas = 0
                self.concluir_item()
                return False
            self.registrar_falha(tabela, chave, erro)
            self._falhas_api_seguidas += 1
            self.concluir_item()
            if self._falhas_api_seguidas >= MAX_FALHAS_API_SEGUIDAS:
                raise
            return False
        self._falhas_api_seguidas = 0
        self.concluir_item()
        return True

    def _ausentes_desde_ha_pouco(self, tabela):
        """Ids desta tabela que deram 404 dentro do prazo; lido uma vez por coleta."""
        if tabela not in self._ausentes_recentes:
            horas = current_app.config.get("COLETOR_AUSENTE_HORAS", 24)
            if horas <= 0:
                self._ausentes_recentes[tabela] = set()
            else:
                desde = agora_utc() - timedelta(hours=horas)
                self._ausentes_recentes[tabela] = set(
                    db.session.scalars(
                        db.select(LogSistema.entidade_id).where(
                            LogSistema.acao == ACAO_AUSENTE,
                            LogSistema.entidade == tabela,
                            LogSistema.data_hora >= desde,
                        )
                    )
                )
        return self._ausentes_recentes[tabela]

    def _registrar_ausente(self, tabela, chave, erro):
        self.ausentes += 1
        horas = current_app.config.get("COLETOR_AUSENTE_HORAS", 24)
        descricao = f"{erro}: a Camara nao tem este registro; nova tentativa depois de {horas} h"
        self.log("aviso", ACAO_AUSENTE, descricao, entidade=tabela, entidade_id=chave)
        logger.warning("%s %s: %s", tabela, chave, descricao)

    def concluir_item(self):
        """Fecha a transacao a cada item, para nao segurar o SQLite durante as chamadas HTTP."""
        self.atualizar_contadores()
        db.session.commit()

    def atualizar_contadores(self):
        self.coleta.requisicoes = self.cliente.requisicoes - self._requisicoes_antes
        self.coleta.erros_http = self.cliente.erros_http - self._erros_http_antes

    def finalizar(self, status=None, mensagem=None):
        self.atualizar_contadores()
        self.coleta.finalizado_em = agora_utc()
        self.coleta.status = status or ("parcial" if self.falhas else "ok")
        self.coleta.mensagem_erro = mensagem or (f"{self.falhas} registros com erro" if self.falhas else None)
        self.log(
            "erro" if self.coleta.status == "erro" else "info",
            "fim_coleta",
            (
                f"{self.coleta.recurso}: status={self.coleta.status} total={self.coleta.total_itens} "
                f"novos={self.coleta.itens_novos} atualizados={self.coleta.itens_atualizados} "
                f"requisicoes={self.coleta.requisicoes} erros_http={self.coleta.erros_http} falhas={self.falhas}"
                + (
                    f" nao_encontrados_na_camara={self.ausentes} pulados_por_404_recente={self.ausentes_pulados}"
                    if self.ausentes or self.ausentes_pulados
                    else ""
                )
            ),
        )
        db.session.commit()


def _item_nao_existe(erro, chave):
    """404 no detalhe do proprio item (a URL termina no id), e nao num filho como /pauta ou /votos."""
    return (
        erro.status == 404
        and not isinstance(chave, (tuple, dict))
        and erro.url.split("?")[0].rstrip("/").endswith(f"/{chave}")
    )


def _id_texto(chave):
    if chave is None:
        return None
    if isinstance(chave, dict):
        chave = tuple(chave.values())
    if isinstance(chave, tuple):
        return "/".join(str(parte) for parte in chave)[:50]
    return str(chave)[:50]
