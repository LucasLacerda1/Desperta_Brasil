import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from desperta.noticias.services import MARCA_SECAO
from desperta.proposicoes.services import ou_nao_informado
from desperta.proposicoes.situacoes import situacao_informada
from desperta.votacoes.services import e_votacao_de_merito

# Decisao 17.2: GeradorFrases e o plano B e o padrao do MVP; GeradorRoberta so entra depois da Fase 3b.

CASO_NOVA = "nova"
CASO_SITUACAO = "situacao"
CASO_VOTACAO = "votacao"
CASOS = (CASO_NOVA, CASO_SITUACAO, CASO_VOTACAO)

LIMITE_TITULO = 200
LIMITE_RESUMO = 500
TRAMITACOES_NO_CORPO = 3

# Decisao 25.13: estrutura da noticia. O resumo (paragrafo principal) traz so o fato; o resto
# vai para secoes do corpo, cada uma comecando com "## " (a API entrega as partes separadas)
SECAO_PROPOE = "O que propõe"
SECAO_VOTACAO = "Resultado da votação"
SECAO_ONDE_ESTA = "Onde está na Câmara"
SECAO_LACUNAS = "O que a Câmara não informou"
INTRO_LACUNAS = "Situação dos dados abertos da Câmara quando este texto foi escrito:"
MAIS_INFORMACOES = "Para mais informações, acesse o site da Câmara dos Deputados"

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
    # Transparencia: nominal, so_placar, simbolica, pendente, erro_na_coleta ou inconsistente
    situacao: str = "nominal"
    explicacao: str = ""


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
    regime: Optional[str] = None
    apreciacao: Optional[str] = None
    cod_situacao: Optional[int] = None
    # Decisao 25.13: explicacao popular da situacao (None se o codigo nao esta no dicionario)
    explicacao_situacao: Optional[str] = None


@dataclass
class DadosLacuna:
    """Lacuna da Camara ja em texto (desperta/sistema/lacunas.py): o que falta e a prova."""

    texto: str
    provas: List[str] = field(default_factory=list)


@dataclass
class DadosNoticia:
    """Os registros de origem, ja lidos do banco: e daqui que sai todo fato do texto."""

    caso: str
    proposicao: DadosProposicao
    votacao: Optional[DadosVotacao] = None
    tramitacoes: List[DadosTramitacao] = field(default_factory=list)
    # So as falhas da Camara (sem a pratica normal) e o link da ficha da proposicao
    lacunas: List[DadosLacuna] = field(default_factory=list)
    url_mais_informacoes: Optional[str] = None


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


def _explicado(proposicao, maiuscula=False):
    """
    Planta da noticia (25.18): a sigla explicada na primeira vez, para o brasileiro comum:
    "o projeto de lei PL 1/2024", "a proposta de emenda à Constituição PEC 2/2023".
    """
    if proposicao.sigla in TIPOS:
        extenso, artigo, _ = _tipo(proposicao)
        texto = f"{artigo} {extenso} {_identificacao(proposicao)}"
    else:
        texto = f"a proposição {_identificacao(proposicao)}"
    return texto[:1].upper() + texto[1:] if maiuscula else texto


def _de_explicado(proposicao):
    """ "do projeto de lei PL 1/2024", "da proposta de emenda à Constituição PEC 2/2023"."""
    texto = _explicado(proposicao)
    return f"d{texto}" if texto[:2] in ("o ", "a ") else f"de {texto}"


# Autor que nao e pessoa: "do Poder Executivo", "da Comissao de Saude" (e nao "de Poder Executivo")
ARTIGO_DO_AUTOR = {
    "Poder": "do",
    "Senado": "do",
    "Supremo": "do",
    "Tribunal": "do",
    "Ministério": "do",
    "Comissão": "da",
    "Mesa": "da",
    "Câmara": "da",
    "Procuradoria": "da",
    "Defensoria": "da",
}


def _de_autor(autor):
    artigo = ARTIGO_DO_AUTOR.get(autor.split(" ", 1)[0])
    return f"{artigo} {autor}" if artigo else f"de {autor}"


def _no_dia(data):
    """A noticia pode sair dias depois: nada de "nesta terca-feira", que ficaria errado."""
    artigo = "no" if data.weekday() >= 5 else "na"
    return f"{artigo} {DIAS_DA_SEMANA[data.weekday()]} ({data:%d/%m/%Y})"


def _frase(texto):
    return texto if texto.endswith((".", "!", "?", "…")) else f"{texto}."


def _quem_votou(votacao):
    return "O Plenário da Câmara" if votacao.sigla_orgao == "PLEN" else f"O órgão {votacao.orgao}"


def _titulo_da_votacao(votacao):
    return "Câmara" if votacao.sigla_orgao == "PLEN" else votacao.orgao


def _placar(votacao):
    # So o placar, simbolica, pendente: a explicacao diz o que os dados mostram
    if votacao.situacao != "nominal":
        return _frase(votacao.explicacao) if votacao.explicacao else ""
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
    nome = "frases-v3"
    # v2 (decisao 25.13): paragrafo principal so com o fato; placar, situacao e lacunas em secoes
    # v3 (decisao 25.18): segue a planta da noticia (docs/PLANTA_DA_NOTICIA.md): sigla no titulo e
    # explicada no paragrafo principal; situacao contada com a explicacao popular, sem o jargao do passo
    versao_prompt = "frases-v3"

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
        identificacao = _identificacao(proposicao)
        forma, ementa = simplificar_ementa(proposicao.ementa)
        titulo = {
            "verbo": f"{identificacao} {ementa}",
            "finalidade": f"{identificacao} propõe {ementa}",
            "livre": f"{identificacao} propõe: {ementa}",
        }[forma]
        apresentado = "apresentada" if _tipo(proposicao)[1] == "a" else "apresentado"
        autoria = f", de autoria {_de_autor(self._autoria(proposicao))}," if proposicao.autor else ""
        quando = f"{proposicao.apresentada_em:%d/%m/%Y}"
        resumo = f"{_explicado(proposicao, maiuscula=True)}{autoria} foi {apresentado} em {quando}."
        # A ementa simplificada so por regra (sem acrescentar fato); a oficial fica em "O que propoe"
        if forma == "verbo":
            resumo += f" O texto {_frase(ementa)}"
        elif forma == "finalidade":
            resumo += f" O objetivo é {_frase(ementa)}"
        return titulo, resumo

    def _situacao(self, dados):
        proposicao = dados.proposicao
        if not situacao_informada(proposicao.cod_situacao, proposicao.situacao):
            return self._sem_situacao(dados)
        situacao = proposicao.situacao.strip()
        if situacao.lower() in SITUACOES_DE_AVANCO:
            titulo = f"{_identificacao(proposicao)} avança na Câmara"
        else:
            titulo = f'{_identificacao(proposicao)}: situação agora é "{situacao}"'
        # 25.18: o fato e a explicacao popular da situacao (25.14); o passo do andamento fica em "Onde esta"
        resumo = f'A situação {_de_explicado(proposicao)} na Câmara mudou para "{situacao}".'
        if proposicao.explicacao_situacao:
            resumo += f" {proposicao.explicacao_situacao}"
        return titulo, resumo

    def _votacao(self, dados):
        votacao = dados.votacao
        proposicao = dados.proposicao
        identificacao = _identificacao(proposicao)
        descricao = _descricao_da_votacao(votacao)
        merito = proposicao.sigla in TIPOS and e_votacao_de_merito(descricao)
        if merito and votacao.aprovacao is not None:
            verbo = "aprova" if votacao.aprovacao else "rejeita"
            feito = "aprovou" if votacao.aprovacao else "rejeitou"
            titulo = f"{_titulo_da_votacao(votacao)} {verbo} {self._o_que_foi_votado(proposicao)}"
            # 25.13: o placar sai do paragrafo principal e vai para a secao "Resultado da votacao"
            resumo = f"{_quem_votou(votacao)} {feito}, {_no_dia(votacao.data)}, {_explicado(proposicao)}."
        else:
            # Requerimento, destaque, redacao final: conta o que a Camara registrou, sem dizer que o projeto passou
            titulo = f"{identificacao}: {descricao}"
            resumo = (
                f"{_quem_votou(votacao)} votou, {_no_dia(votacao.data)}, sobre {_explicado(proposicao)}: "
                f"{_frase(descricao)}"
            )
        return titulo, resumo.strip()

    def _o_que_foi_votado(self, proposicao):
        """25.18: a sigla no titulo ("Camara aprova PL 1/2024, que institui ...")."""
        identificacao = _identificacao(proposicao)
        forma, ementa = simplificar_ementa(proposicao.ementa)
        if forma == "finalidade":
            return f"{identificacao} para {ementa}"
        if forma == "verbo":
            return f"{identificacao}, que {ementa}"
        return f"{identificacao}: {ementa}"

    def _autoria(self, proposicao):
        return f"{proposicao.autor} e outros" if proposicao.mais_autores else proposicao.autor

    def _sem_situacao(self, dados):
        """
        Decisao 25.1: quando a Camara nao informa a situacao, a noticia conta o ultimo passo
        do andamento; a descricao do passo nunca e apresentada como se fosse a situacao.
        Decisao 25.13: que a situacao nao foi informada vai para as secoes, nao para o resumo.
        """
        if not dados.tramitacoes:
            raise ValueError("A proposicao nao tem situacao nem tramitacao.")
        proposicao = dados.proposicao
        passo = dados.tramitacoes[-1]
        titulo = f"{_identificacao(proposicao)}: {passo.descricao.strip()}"
        resumo = _tramitacao_em_frase(passo)
        return titulo, resumo

    def _corpo(self, dados):
        """Decisao 25.13: secoes na ordem; cada uma comeca com "## " e o titulo."""
        secoes = [(SECAO_PROPOE, self._o_que_propoe(dados))]
        if dados.votacao:
            secoes.append((SECAO_VOTACAO, self._resultado(dados.votacao)))
        secoes.append((SECAO_ONDE_ESTA, self._onde_esta(dados)))
        if dados.lacunas:
            secoes.append((SECAO_LACUNAS, self._lacunas(dados)))
        return "\n\n".join(f"{MARCA_SECAO}{titulo}\n\n{texto}" for titulo, texto in secoes)

    def _o_que_propoe(self, dados):
        proposicao = dados.proposicao
        partes = [f"Ementa oficial: {_frase(_limpar_ementa(proposicao.ementa))}"]
        if proposicao.autor:
            partes.append(f"Autoria: {self._autoria(proposicao)}.")
        return "\n\n".join(partes)

    def _resultado(self, votacao):
        resultado = {True: "aprovado", False: "rejeitado", None: "não informado pela Câmara"}[votacao.aprovacao]
        partes = [
            f"Votação em {votacao.data:%d/%m/%Y}, em {votacao.orgao}: {_frase(_descricao_da_votacao(votacao))}",
            f"Resultado: {resultado}.",
        ]
        placar = _placar(votacao)
        if placar:
            partes.append(placar)
        return "\n\n".join(partes)

    def _onde_esta(self, dados):
        proposicao = dados.proposicao
        if situacao_informada(proposicao.cod_situacao, proposicao.situacao):
            situacao = f'Situação: "{proposicao.situacao.strip()}".'
            if proposicao.explicacao_situacao:
                situacao += f" {proposicao.explicacao_situacao}"
        else:
            situacao = "Situação: não informada pela Câmara."
        # Transparencia: o que a Camara nao informou aparece como nao informado
        partes = [
            situacao,
            f"Regime de tramitação: {ou_nao_informado(proposicao.regime)}. "
            f"Apreciação: {ou_nao_informado(proposicao.apreciacao, feminino=True)}.",
        ]
        recentes = dados.tramitacoes[-TRAMITACOES_NO_CORPO:]
        if recentes:
            partes.append("Últimos passos:\n" + "\n".join(_tramitacao_em_frase(passo) for passo in recentes))
        return "\n\n".join(partes)

    def _lacunas(self, dados):
        """A introducao mantem o texto verdadeiro mesmo depois que a Camara corrigir os dados."""
        itens = [" ".join([f"- {lacuna.texto}", *lacuna.provas]) for lacuna in dados.lacunas]
        partes = [INTRO_LACUNAS, "\n".join(itens)]
        if dados.url_mais_informacoes:
            partes.append(f"{MAIS_INFORMACOES}: {dados.url_mais_informacoes}")
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
