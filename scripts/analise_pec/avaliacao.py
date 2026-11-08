"""
Notas dos testes do estudo (docs/ESTUDO_ROBERTA_X_GRUPO.md e docs/LEITURA_ENCADEADA.md).
So conta: nenhuma funcao aqui carrega o modelo. Compara sempre posicoes, nunca o valor da similaridade.
"""

import math
import re
import unicodedata
from collections import Counter

PALAVRA = re.compile(r"\w+(?:-\w+)*")
FORA_DO_TEXTO = "fora do texto da PEC"


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def palavras_simples(texto, vazias):
    return [p for p in (_sem_acento(m.group(0)) for m in PALAVRA.finditer(texto)) if len(p) >= 3 and p not in vazias]


def ordenar(vetor_alvo, vetores, cosseno):
    """Codigos do mais parecido para o menos parecido."""
    return sorted(vetores, key=lambda codigo: -cosseno(vetores[codigo], vetor_alvo))


# ======================================================
# A. FRASES CENTRAIS
# ======================================================
def teste_a(ordem, escolhidas, total):
    top = ordem[:5]
    acertos = len(set(top) & set(escolhidas))
    return {"top5": top, "acertos": acertos, "de": len(escolhidas), "acaso": round(5 * len(escolhidas) / total, 2)}


def centralidade_por_palavras(frases, vazias):
    """Adversario do teste A: frase com palavras que se repetem na PEC fica no topo."""
    contagem = Counter(p for _, texto in frases for p in set(palavras_simples(texto, vazias)))
    nota = {}
    for codigo, texto in frases:
        palavras = set(palavras_simples(texto, vazias))
        nota[codigo] = sum(contagem[p] for p in palavras) / math.sqrt(len(palavras) or 1)
    return sorted(nota, key=lambda codigo: -nota[codigo])


# ======================================================
# B. RESUMO -> FRASE DA PEC
# ======================================================
def certas_do_resumo(resumo):
    """So as frases do resumo que dizem de qual frase da PEC vieram (as de fora do texto nao entram)."""
    itens = []
    for item in resumo:
        origem = item.get("de_qual_frase_da_pec")
        if not origem or origem == FORA_DO_TEXTO or str(origem).startswith("<"):
            continue
        itens.append((item["frase"], set(origem if isinstance(origem, list) else [origem])))
    return itens


def teste_b(achadas, certas, total):
    """achadas: a frase da PEC mais parecida com cada frase do resumo, na mesma ordem de certas."""
    acertos = sum(1 for achada, (_, conjunto) in zip(achadas, certas) if achada in conjunto)
    acaso = sum(len(conjunto) for _, conjunto in certas) / total if certas else 0
    return {"acertos": acertos, "de": len(certas), "achadas": achadas, "acaso": round(acaso, 2)}


def mais_parecida_por_palavras(texto, frases, vazias):
    """Adversario do teste B: a frase da PEC que mais divide palavras com a frase do resumo."""
    alvo = set(palavras_simples(texto, vazias))

    def nota(item):
        palavras = set(palavras_simples(item[1], vazias))
        return len(alvo & palavras) / math.sqrt((len(alvo) or 1) * (len(palavras) or 1))

    return max(frases, key=nota)[0]


# ======================================================
# C. RESUMO -> PEC CERTA
# ======================================================
def teste_c(ordem, certa):
    return {"posicao": ordem.index(certa) + 1, "de": len(ordem), "acaso_1o_lugar": round(1 / len(ordem), 3)}


# ======================================================
# D. TEMAS (nota exata e nota ampla, decisao 8)
# ======================================================
def teste_d(top3, temas, aceitos, oficiais):
    return {
        "top3": top3,
        "exata": len(set(top3) & set(temas)),
        "ampla": len(set(top3) & (set(temas) | set(aceitos))),
        "oficiais": len(set(top3) & set(oficiais)),
        "de": 3,
    }


# ======================================================
# E. PALAVRAS-CHAVE
# ======================================================
def teste_e_pesos(pesos, palavras_do_leitor):
    top = sorted(pesos, key=lambda p: -pesos[p])[:10]
    alvo = {_sem_acento(p) for p in palavras_do_leitor}
    return {"top10": top, "em_comum": sorted(alvo & {_sem_acento(p) for p in top}), "de": len(alvo)}


def teste_e_lacunas(resultados):
    """resultados: (palavra, acertou ou None se nao da para testar)."""
    testadas = [(p, a) for p, a in resultados if a is not None]
    return {
        "acertos": sum(1 for _, a in testadas if a),
        "testadas": len(testadas),
        "nao_testadas": [p for p, a in resultados if a is None],
        "acertadas": [p for p, a in testadas if a],
    }


# ======================================================
# BLOCOS DA PLANTA
# ======================================================
def bloco_bate(escolhido, certo):
    """F1 junta os blocos 1 e 2: vale qualquer um dos dois."""
    return escolhido == certo or (" e " in certo and escolhido in certo.split(" e "))


def teste_blocos(escolhidos, certos):
    acertos = sum(1 for codigo in certos if bloco_bate(escolhidos[codigo], certos[codigo]))
    maior = Counter(certos.values()).most_common(1)[0][1]
    return {
        "acertos": acertos,
        "de": len(certos),
        "sempre_o_maior_bloco": maior,
        "erradas": {c: escolhidos[c] for c in certos if not bloco_bate(escolhidos[c], certos[c])},
    }
