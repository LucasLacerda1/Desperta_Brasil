from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from flask import current_app

from desperta.ext.api import BRASILIA, iso, url_camara
from desperta.ext.db import db

from .models import LogSistema

# ----------------------------------------------------------
# Lacunas da Camara (decisao 25.13)
# O que os dados abertos da Camara nao informam, ou informam de um jeito que nao fecha.
# Toda lacuna diz POR QUE e ONDE, com PROVA: o endereco da API consultado, o campo, o valor
# como veio e quando foi a consulta (de sincronizado_em, filhos_sincronizados_em ou do log).
# O texto ao leitor afirma so o que da para provar e fala dos "dados abertos da Camara".
# ----------------------------------------------------------

# Niveis: INTERNOS, o leitor nao ve (servem para a fila e para o filtro)
CONTRADICAO = 1  # os dados se contradizem (votos x placar, registro que sumiu)
OCULTACAO = 2  # so o resultado, sem o detalhe (so o placar, sem o voto de cada deputado)
ATRASO = 3  # ainda nao publicado (sem tema)
CAMPO_VAZIO = 4  # campo nao informado (situacao, regime, inteiro teor)
PRATICA_NORMAL = 5  # nao e falha (votacao simbolica)
NIVEIS = {
    CONTRADICAO: "contradição",
    OCULTACAO: "ocultação",
    ATRASO: "atraso",
    CAMPO_VAZIO: "campo vazio",
    PRATICA_NORMAL: "prática normal",
}

# Grau de certeza sobre o MOTIVO da lacuna (o fato em si sempre tem prova)
COMPROVADO = "comprovado"  # os proprios dados mostram o motivo (o campo veio vazio)
INDICADO = "indicado"  # o motivo e deducao (lista de votos vazia costuma ser votacao simbolica)
SEM_EXPLICACAO = "sem_explicacao"  # os dados abertos nao dizem por que
CERTEZAS = (COMPROVADO, INDICADO, SEM_EXPLICACAO)

MAIS_INFORMACOES = "Para mais informações, acesse o site da Câmara dos Deputados"
URL_FICHA = "https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={}"
ACAO_AUSENTE = "nao_encontrado_na_camara"


@dataclass
class Prova:
    endereco: str
    campo: str
    # O valor como veio da API, em texto: "null", '"."', "[] (lista vazia)"
    valor: str
    # Em UTC, como o banco grava
    consultado_em: Optional[datetime] = None

    def como_dict(self):
        return {
            "endereco": self.endereco,
            "campo": self.campo,
            "valor": self.valor,
            "consultado_em": iso(self.consultado_em),
        }

    def em_texto(self):
        quando = f" em {horario_de_brasilia(self.consultado_em)}" if self.consultado_em else ""
        return f"Consulta aos dados abertos{quando}: {self.endereco} (campo {self.campo}: {self.valor})."


@dataclass
class Lacuna:
    codigo: str
    nivel: int
    certeza: str
    texto: str
    provas: List[Prova] = field(default_factory=list)
    proposicao_id: Optional[int] = None

    @property
    def falha_da_camara(self):
        return self.nivel != PRATICA_NORMAL

    @property
    def url_mais_informacoes(self):
        return URL_FICHA.format(self.proposicao_id) if self.proposicao_id else "https://www.camara.leg.br"

    def publica(self):
        """O que o leitor ve: sem o nivel (interno)."""
        return {
            "codigo": self.codigo,
            "texto": self.texto,
            "certeza": self.certeza,
            "falha_da_camara": self.falha_da_camara,
            "provas": [prova.como_dict() for prova in self.provas],
            "mais_informacoes": {"texto": MAIS_INFORMACOES, "url": self.url_mais_informacoes},
        }

    def interna(self):
        """Area da equipe: com o nivel."""
        dados = self.publica()
        dados.update({"nivel": self.nivel, "nome_do_nivel": NIVEIS[self.nivel]})
        return dados


def horario_de_brasilia(momento):
    """Data do banco (UTC) em texto, no horario de Brasilia: "17/11/2026 às 03:31"."""
    local = momento.replace(tzinfo=timezone.utc).astimezone(BRASILIA)
    return f"{local:%d/%m/%Y} às {local:%H:%M}"


def valor_como_veio(valor):
    """Mostra o valor exatamente como a API mandou, com um nome para o leitor entender."""
    if valor is None:
        return "null (vazio)"
    texto = str(valor)
    if texto.strip() == "":
        return '"" (texto vazio)'
    if texto.strip() == ".":
        return '"." (só um ponto)'
    if texto.strip() == "-":
        return '"-" (só um traço)'
    return f'"{texto}"'


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ausente_na_camara(tabela, ref_id, desde):
    """
    Decisao 25.8: o ultimo aviso de 404 do detalhe, se for depois da ultima vez que o
    registro apareceu na API (senao a Camara ja voltou a mandar o registro).
    """
    aviso = db.session.scalar(
        db.select(LogSistema)
        .where(LogSistema.acao == ACAO_AUSENTE, LogSistema.entidade == tabela, LogSistema.entidade_id == str(ref_id))
        .order_by(LogSistema.data_hora.desc(), LogSistema.id.desc())
        .limit(1)
    )
    if aviso is None or (desde is not None and aviso.data_hora <= desde):
        return None
    return aviso


def _lacuna_404(tabela, ref_id, caminho, nome, proposicao_id, sincronizado_em):
    aviso = _ausente_na_camara(tabela, ref_id, sincronizado_em)
    if aviso is None:
        return None
    return Lacuna(
        codigo="registro_sumiu",
        nivel=CONTRADICAO,
        certeza=SEM_EXPLICACAO,
        texto=(
            f"{nome} já apareceu nos dados abertos da Câmara, mas na última consulta o endereço dela "
            "respondeu que o registro não existe (erro 404). Os dados abertos não dizem por quê."
        ),
        provas=[Prova(url_camara(caminho), "resposta HTTP", "404 (não encontrado)", aviso.data_hora)],
        proposicao_id=proposicao_id,
    )


# ======================================================
# PROPOSICAO
# ======================================================
def lacunas_da_proposicao(proposicao, agora=None):
    from desperta.proposicoes.services import informado
    from desperta.proposicoes.situacoes import situacao_informada

    agora = agora or _agora()
    lacunas = []
    endereco = url_camara(f"proposicoes/{proposicao.id}")
    consultado = proposicao.sincronizado_em

    def campo_vazio(codigo, campo, valor, texto):
        lacunas.append(
            Lacuna(
                codigo=codigo,
                nivel=CAMPO_VAZIO,
                certeza=COMPROVADO,
                texto=texto,
                provas=[Prova(endereco, campo, valor_como_veio(valor), consultado)],
                proposicao_id=proposicao.id,
            )
        )

    sumiu = _lacuna_404(
        "proposicao", proposicao.id, f"proposicoes/{proposicao.id}", "A proposição", proposicao.id, consultado
    )
    if sumiu:
        lacunas.append(sumiu)

    # Tema: so conta depois que os temas foram consultados (filhos_sincronizados_em)
    if not proposicao.temas and proposicao.filhos_sincronizados_em is not None:
        dias = (agora.date() - proposicao.data_apresentacao.date()).days
        limite = current_app.config["LACUNA_ATRASO_DIAS"]
        texto = "A Câmara ainda não informou o tema desta proposição."
        if dias > limite:
            texto += f" Ela foi apresentada há {dias} dias."
        lacunas.append(
            Lacuna(
                codigo="sem_tema",
                nivel=OCULTACAO if dias > limite else ATRASO,
                certeza=COMPROVADO,
                texto=texto,
                provas=[
                    Prova(
                        url_camara(f"proposicoes/{proposicao.id}/temas"),
                        "dados",
                        "[] (lista vazia)",
                        proposicao.filhos_sincronizados_em,
                    )
                ],
                proposicao_id=proposicao.id,
            )
        )

    if not situacao_informada(proposicao.cod_situacao, proposicao.situacao):
        valor = proposicao.situacao if proposicao.cod_situacao is not None else None
        campo_vazio(
            "sem_situacao",
            "statusProposicao.descricaoSituacao",
            valor,
            "A Câmara não informou a situação atual desta proposição.",
        )
    if proposicao.data_status is None:
        campo_vazio(
            "sem_data_da_situacao",
            "statusProposicao.dataHora",
            None,
            "A Câmara não informou a data da situação atual desta proposição.",
        )
    if informado(proposicao.regime) is None:
        campo_vazio(
            "sem_regime",
            "statusProposicao.regime",
            proposicao.regime,
            "A Câmara não informou o regime de tramitação desta proposição (por exemplo, se ela tem urgência).",
        )
    if informado(proposicao.apreciacao) is None:
        campo_vazio(
            "sem_apreciacao",
            "statusProposicao.apreciacao",
            proposicao.apreciacao,
            "A Câmara não informou quem decide sobre esta proposição: só as comissões ou também o Plenário.",
        )
    if informado(proposicao.url_inteiro_teor) is None:
        campo_vazio(
            "sem_inteiro_teor",
            "urlInteiroTeor",
            proposicao.url_inteiro_teor,
            "A Câmara não publicou nos dados abertos o link para o texto completo desta proposição.",
        )
    return lacunas


# ======================================================
# VOTACAO
# ======================================================
def lacunas_da_votacao(votacao, proposicao_id=None):
    """Pendente e erro na coleta sao do portal, nao da Camara: nao viram lacuna (a explicacao ja diz)."""
    from desperta.votacoes import services as votacoes

    proposicao_id = proposicao_id or votacao.proposicao_id
    lacunas = []
    endereco = url_camara(f"votacoes/{votacao.id}")
    endereco_votos = url_camara(f"votacoes/{votacao.id}/votos")

    sumiu = _lacuna_404(
        "votacao", votacao.id, f"votacoes/{votacao.id}", "A votação", proposicao_id, votacao.sincronizado_em
    )
    if sumiu:
        lacunas.append(sumiu)

    if votacao.aprovacao is None:
        lacunas.append(
            Lacuna(
                codigo="sem_resultado",
                nivel=CAMPO_VAZIO,
                certeza=COMPROVADO,
                texto="A Câmara não informou nos dados abertos se esta votação aprovou ou rejeitou o que foi votado.",
                provas=[Prova(endereco, "aprovacao", "null (vazio)", votacao.sincronizado_em)],
                proposicao_id=proposicao_id,
            )
        )

    situacao = votacoes.situacao_dos_votos(votacao)
    total = sum(situacao.votos.values())
    placar = situacao.placar_da_camara
    prova_votos = Prova(
        endereco_votos,
        "tipoVoto",
        f"null em {situacao.votos[None]} de {total} registros",
        votacao.filhos_sincronizados_em,
    )
    prova_placar = Prova(endereco, "descricao", valor_como_veio(votacao.descricao), votacao.sincronizado_em)

    if situacao.codigo == votacoes.SO_PLACAR:
        frase = votacoes.placar_em_frase(placar)
        presencas = "1 presença" if total == 1 else f"{total} presenças"
        texto = (
            f"Os dados abertos da Câmara registram {presencas} nesta votação, mas não informam o voto de cada deputado"
        )
        texto += f": trazem só o placar total ({frase})." if frase else " nem o placar."
        lacunas.append(
            Lacuna(
                codigo="so_placar",
                nivel=OCULTACAO,
                certeza=SEM_EXPLICACAO,
                texto=f"{texto} Os dados abertos não dizem por quê.",
                provas=[prova_votos, prova_placar] if frase else [prova_votos],
                proposicao_id=proposicao_id,
            )
        )
    elif situacao.codigo == votacoes.INCONSISTENTE:
        lacunas.append(
            Lacuna(
                codigo="votos_sem_tipo",
                nivel=CONTRADICAO,
                certeza=SEM_EXPLICACAO,
                texto=(
                    f"Os dados abertos da Câmara trazem {situacao.votos[None]} dos {total} votos desta votação "
                    "sem dizer qual foi o voto. Os dados abertos não dizem por quê."
                ),
                provas=[prova_votos],
                proposicao_id=proposicao_id,
            )
        )
    elif situacao.codigo == votacoes.NOMINAL:
        diferentes = [
            tipo
            for tipo in ("Sim", "Não", "Abstenção", "Obstrução")
            if tipo in placar and placar[tipo] != situacao.votos.get(tipo, 0)
        ]
        if diferentes:
            registrados = votacoes.placar_em_frase({tipo: situacao.votos.get(tipo, 0) for tipo in placar})
            lacunas.append(
                Lacuna(
                    codigo="placar_diferente",
                    nivel=CONTRADICAO,
                    certeza=SEM_EXPLICACAO,
                    texto=(
                        f"O placar escrito pela Câmara na descrição da votação ({votacoes.placar_em_frase(placar)}) "
                        f"não bate com os votos de cada deputado nos dados abertos ({registrados})."
                    ),
                    provas=[
                        prova_placar,
                        Prova(endereco_votos, "tipoVoto", f"{total} registros", votacao.filhos_sincronizados_em),
                    ],
                    proposicao_id=proposicao_id,
                )
            )
    elif situacao.codigo == votacoes.SIMBOLICA:
        lacunas.append(
            Lacuna(
                codigo="simbolica",
                nivel=PRATICA_NORMAL,
                certeza=INDICADO,
                texto=(
                    "Os dados abertos não trazem o voto de cada deputado nesta votação. Isso é o normal na votação "
                    "simbólica, em que o resultado é anunciado sem o registro do voto de cada um."
                ),
                provas=[Prova(endereco_votos, "dados", "[] (lista vazia)", votacao.filhos_sincronizados_em)],
                proposicao_id=proposicao_id,
            )
        )
    return lacunas


# ======================================================
# NOTICIA: lacunas das fontes
# ======================================================
def lacunas_das_fontes(fontes):
    """fontes: (tipo, ref_id) na ordem da noticia. Mais graves primeiro; sem repetir."""
    from desperta.proposicoes.models import Proposicao
    from desperta.votacoes.models import Votacao

    proposicao_principal = next((int(ref) for tipo, ref in fontes if tipo == "proposicao"), None)
    lacunas = []
    for tipo, ref in fontes:
        if tipo == "proposicao":
            proposicao = db.session.get(Proposicao, int(ref))
            if proposicao is not None:
                lacunas.extend(lacunas_da_proposicao(proposicao))
        elif tipo == "votacao":
            votacao = db.session.get(Votacao, str(ref))
            if votacao is not None:
                lacunas.extend(lacunas_da_votacao(votacao, proposicao_principal))
    return sorted(lacunas, key=lambda lacuna: lacuna.nivel)
