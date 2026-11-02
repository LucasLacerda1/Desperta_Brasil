import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

# Decisao 17.2: GeradorFrases e o plano B e o padrao do MVP; GeradorRoberta so entra depois da Fase 3b.

CASO_NOVA = "nova"
CASO_SITUACAO = "situacao"
CASO_VOTACAO = "votacao"
CASOS = (CASO_NOVA, CASO_SITUACAO, CASO_VOTACAO)

LIMITE_TITULO = 200
LIMITE_RESUMO = 500
TRAMITACOES_NO_CORPO = 3

# sigla: (nome por extenso, artigo, sujeito do titulo)
TIPOS = {
    "PL": ("projeto de lei", "o", "Projeto"),
    "PLP": ("projeto de lei complementar", "o", "Projeto"),
    "PEC": ("proposta de emenda à Constituição", "a", "Proposta"),
    "MPV": ("medida provisória", "a", "Medida provisória"),
    "PDL": ("projeto de decreto legislativo", "o", "Projeto"),
}
DIAS_DA_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
# Ementas que mudam outra lei: o que interessa ao leitor vem depois de "para"
VERBOS_DE_ALTERACAO = ("altera", "acrescenta", "acresce", "modifica", "insere")
# Primeira palavra das ementas da API: so com elas a frase "Projeto <verbo> ..." fica correta
VERBOS_DE_EMENTA = VERBOS_DE_ALTERACAO + (
    "abre",
    "agrava",
    "amplia",
    "aprova",
    "assegura",
    "aumenta",
    "autoriza",
    "concede",
    "confere",
    "considera",
    "cria",
    "dá",
    "declara",
    "define",
    "denomina",
    "determina",
    "disciplina",
    "dispõe",
    "estabelece",
    "estende",
    "extingue",
    "faculta",
    "garante",
    "impede",
    "implanta",
    "impõe",
    "inclui",
    "inscreve",
    "institui",
    "introduz",
    "isenta",
    "obriga",
    "permite",
    "prevê",
    "promove",
    "prorroga",
    "proíbe",
    "reconhece",
    "regula",
    "regulamenta",
    "retira",
    "revoga",
    "suprime",
    "susta",
    "tipifica",
    "torna",
    "transforma",
    "veda",
)
# Decisao tomada com os dados reais: "aprovada" quase sempre e requerimento ou redacao final, nao o projeto
VOTACAO_DE_MERITO = re.compile(
    r"^(?:Aprovad|Rejeitad)[oa] (?:o|a) (?:Projeto de|Proposta de Emenda|Medida Provis[oó]ria|Substitutivo)"
)
PLACAR_NA_DESCRICAO = re.compile(r"\s*Sim: \d+.*$")
# "Arquivada" ou "Aguardando Parecer" nao sao avanco: so estas situacoes podem dizer "avanca"
SITUACOES_DE_AVANCO = (
    "pronta para pauta",
    "aguardando apreciação pelo senado federal",
    "aguardando redação final",
    "aguardando envio à redação final",
    "aguardando sanção",
    "transformado em norma jurídica",
)


@dataclass
class TextoGerado:
    titulo: str
    resumo: str
    corpo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0


@dataclass
class DadosTramitacao:
    data: date
    orgao: str
    descricao: str
    despacho: str


@dataclass
class DadosVotacao:
    descricao: str
    data: date
    sigla_orgao: str
    orgao: str
    aprovacao: Optional[bool]
    sim: int = 0
    nao: int = 0
    abstencao: int = 0


@dataclass
class DadosProposicao:
    sigla: str
    numero: int
    ano: int
    descricao_tipo: str
    ementa: str
    apresentada_em: date
    autor: Optional[str] = None
    mais_autores: bool = False
    situacao: Optional[str] = None


@dataclass
class DadosNoticia:
    """Os registros de origem, ja lidos do banco: e daqui que sai todo fato do texto."""

    caso: str
    proposicao: DadosProposicao
    votacao: Optional[DadosVotacao] = None
    tramitacoes: List[DadosTramitacao] = field(default_factory=list)


# === Gerador (interface de quem escreve as noticias) ===
class Gerador:
    nome = None
    versao_prompt = None

    def escrever(self, consulta, trechos, dados=None):
        """Recebe a consulta, os textos recuperados pelo RAG e os registros de origem; devolve um TextoGerado."""
        raise NotImplementedError


# === GeradorFalso (so para teste: nao escreve noticia de verdade) ===
class GeradorFalso(Gerador):
    nome = "gerador-falso"
    versao_prompt = "falso-v1"

    def escrever(self, consulta, trechos, dados=None):
        corpo = "\n\n".join(trechos)
        return TextoGerado(
            titulo=f"[TESTE] {consulta}"[:LIMITE_TITULO],
            resumo=f"[TESTE] Texto de teste montado com {len(trechos)} trechos."[:LIMITE_RESUMO],
            corpo=corpo,
            tokens_entrada=len(consulta.split()) + len(corpo.split()),
            tokens_saida=len(corpo.split()),
        )


def _cortar(texto, limite):
    """Corta entre palavras, para nao partir um numero ou um nome no meio."""
    if len(texto) <= limite:
        return texto
    return texto[: limite - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _limpar_ementa(ementa):
    """A API traz aspas de abertura, "NOVA EMENTA:" e espacos sobrando."""
    texto = re.sub(r"\s*NOVA EMENTA:?.*$", "", ementa, flags=re.DOTALL)
    texto = re.sub(r"\s+", " ", texto).strip().strip('"“”').strip()
    return re.sub(r",?\s+e dá outras providências\.?$", "", texto, flags=re.IGNORECASE).rstrip(" .")


def _minuscula_inicial(texto):
    return texto[:1].lower() + texto[1:]


def simplificar_ementa(ementa):
    """
    So com regras, sem IA, e sem acrescentar nenhum fato: tira o que e formula e devolve (forma, texto).
    Forma: "finalidade" comeca no infinitivo ("prever..."), "verbo" no presente ("institui...");
    "livre" e qualquer outro comeco.
    """
    limpa = _limpar_ementa(ementa)
    primeira = re.split(r"[\s,]", limpa, maxsplit=1)[0].lower()
    if primeira in VERBOS_DE_ALTERACAO:
        finalidade = re.search(r"\bpara ([a-zà-ú]+(?:ar|er|ir|or)\b.*)$", limpa)
        if finalidade:
            return "finalidade", finalidade.group(1)
    if primeira in VERBOS_DE_EMENTA:
        return "verbo", _minuscula_inicial(limpa)
    return "livre", limpa


def _identificacao(proposicao):
    return f"{proposicao.sigla} {proposicao.numero}/{proposicao.ano}"


def _tipo(proposicao):
    return TIPOS.get(proposicao.sigla, (proposicao.descricao_tipo.lower(), "a", "Proposição"))


def _nome_com_artigo(proposicao):
    """ "O PL 1/2024"; tipos fora dos acompanhados vem de "A proposicao REQ 1/2024"."""
    if proposicao.sigla in TIPOS:
        return f"{_tipo(proposicao)[1].upper()} {_identificacao(proposicao)}"
    return f"A proposição {_identificacao(proposicao)}"


def _no_dia(data):
    """A noticia pode sair dias depois: nada de "nesta terca-feira", que ficaria errado."""
    artigo = "no" if data.weekday() >= 5 else "na"
    return f"{artigo} {DIAS_DA_SEMANA[data.weekday()]} ({data:%d/%m/%Y})"


def _frase(texto):
    return texto if texto.endswith((".", "!", "?", "…")) else f"{texto}."


def _quem_votou(votacao):
    return "O Plenário" if votacao.sigla_orgao == "PLEN" else f"O órgão {votacao.orgao}"


def _titulo_da_votacao(votacao):
    return "Câmara" if votacao.sigla_orgao == "PLEN" else votacao.orgao


def _placar(votacao):
    if not (votacao.sim or votacao.nao or votacao.abstencao):
        return ""
    votos = "1 voto" if votacao.sim == 1 else f"{votacao.sim} votos"
    placar = f"{'Foi' if votacao.sim == 1 else 'Foram'} {votos} a favor e {votacao.nao} contra"
    if votacao.abstencao:
        placar += f", com {votacao.abstencao} de abstenção"
    return f"{placar}."


def _descricao_da_votacao(votacao):
    return PLACAR_NA_DESCRICAO.sub("", votacao.descricao).strip()


def _tramitacao_em_frase(tramitacao):
    texto = (tramitacao.despacho or tramitacao.descricao).strip()
    return f"Em {tramitacao.data:%d/%m/%Y}, em {tramitacao.orgao}: {_frase(texto)}"


# === GeradorFrases (frases prontas: nunca escreve fato que nao esteja nos registros) ===
class GeradorFrases(Gerador):
    nome = "frases-v1"
    versao_prompt = "frases-v1"

    def escrever(self, consulta, trechos, dados=None):
        if dados is None:
            raise ValueError("O GeradorFrases precisa dos registros de origem.")
        titulo, resumo = {
            CASO_NOVA: self._nova,
            CASO_SITUACAO: self._situacao,
            CASO_VOTACAO: self._votacao,
        }[
            dados.caso
        ](dados)
        corpo = self._corpo(dados)
        return TextoGerado(
            titulo=_cortar(titulo, LIMITE_TITULO),
            resumo=_cortar(resumo, LIMITE_RESUMO),
            corpo=corpo,
            tokens_entrada=len(consulta.split()) + sum(len(trecho.split()) for trecho in trechos),
            tokens_saida=len(titulo.split()) + len(resumo.split()) + len(corpo.split()),
        )

    def _nova(self, dados):
        proposicao = dados.proposicao
        sujeito = _tipo(proposicao)[2]
        forma, ementa = simplificar_ementa(proposicao.ementa)
        titulo = f"{sujeito} {ementa}" if forma == "verbo" else f"{sujeito} propõe {ementa}"
        if forma == "livre":
            titulo = f"{sujeito} propõe: {ementa}"
        apresentado = "apresentada" if _tipo(proposicao)[1] == "a" else "apresentado"
        autoria = f", de autoria de {self._autoria(proposicao)}," if proposicao.autor else ""
        resumo = (
            f"{_nome_com_artigo(proposicao)}{autoria} foi {apresentado} em {proposicao.apresentada_em:%d/%m/%Y}. "
            f"{_frase(_limpar_ementa(proposicao.ementa))}"
        )
        return titulo, resumo

    def _situacao(self, dados):
        proposicao = dados.proposicao
        situacao = self._situacao_atual(dados)
        if situacao.lower() in SITUACOES_DE_AVANCO:
            titulo = f"{_identificacao(proposicao)} avança na Câmara"
        else:
            titulo = f'{_identificacao(proposicao)}: situação agora é "{situacao}"'
        resumo = f'{_nome_com_artigo(proposicao)} está com a situação "{situacao}".'
        if dados.tramitacoes:
            resumo += f" {_tramitacao_em_frase(dados.tramitacoes[-1])}"
        return titulo, resumo

    def _votacao(self, dados):
        votacao = dados.votacao
        proposicao = dados.proposicao
        identificacao = _identificacao(proposicao)
        descricao = _descricao_da_votacao(votacao)
        merito = proposicao.sigla in TIPOS and VOTACAO_DE_MERITO.match(descricao)
        if merito and votacao.aprovacao is not None:
            verbo = "aprova" if votacao.aprovacao else "rejeita"
            feito = "aprovou" if votacao.aprovacao else "rejeitou"
            titulo = f"{_titulo_da_votacao(votacao)} {verbo} {self._o_que_foi_votado(proposicao)}"
            artigo = _tipo(proposicao)[1]
            resumo = (
                f"{_quem_votou(votacao)} {feito}, {_no_dia(votacao.data)}, {artigo} {identificacao}. {_placar(votacao)}"
            )
        else:
            # Requerimento, destaque, redacao final: conta o que a Camara registrou, sem dizer que o projeto passou
            titulo = f"{identificacao}: {descricao}"
            resumo = f"Votação {_no_dia(votacao.data)} sobre {identificacao}: {_frase(descricao)} {_placar(votacao)}"
        return titulo, resumo.strip()

    def _o_que_foi_votado(self, proposicao):
        extenso = _tipo(proposicao)[0]
        forma, ementa = simplificar_ementa(proposicao.ementa)
        if forma == "finalidade":
            return f"{extenso} para {ementa}"
        if forma == "verbo":
            return f"{extenso} que {ementa}"
        return f"{extenso}: {ementa}"

    def _autoria(self, proposicao):
        return f"{proposicao.autor} e outros" if proposicao.mais_autores else proposicao.autor

    def _situacao_atual(self, dados):
        if dados.proposicao.situacao:
            return dados.proposicao.situacao.strip()
        if dados.tramitacoes:
            return dados.tramitacoes[-1].descricao.strip()
        raise ValueError("A proposicao nao tem situacao nem tramitacao.")

    def _corpo(self, dados):
        proposicao = dados.proposicao
        partes = [f"Ementa oficial: {_frase(_limpar_ementa(proposicao.ementa))}"]
        if proposicao.autor:
            partes.append(f"Autoria: {self._autoria(proposicao)}.")
        if dados.votacao:
            votacao = dados.votacao
            partes.append(
                f"Votação em {votacao.data:%d/%m/%Y}, em {votacao.orgao}: "
                f"{_frase(_descricao_da_votacao(votacao))} {_placar(votacao)}".strip()
            )
        if proposicao.situacao:
            partes.append(f"Situação atual: {_frase(proposicao.situacao.strip())}")
        recentes = dados.tramitacoes[-TRAMITACOES_NO_CORPO:]
        if recentes:
            partes.append("Últimos passos:\n" + "\n".join(_tramitacao_em_frase(passo) for passo in recentes))
        return "\n\n".join(partes)


def criar_gerador(nome):
    """Decisao 17.2: a troca de quem escreve e so de configuracao (GERADOR)."""
    if nome == "falso":
        return GeradorFalso()
    if nome == "frases":
        return GeradorFrases()
    if nome == "roberta":
        raise ValueError("A Roberta escritora so entra no portal depois de passar na avaliacao (Fase 3b).")
    raise ValueError(f"Gerador desconhecido: {nome}")
