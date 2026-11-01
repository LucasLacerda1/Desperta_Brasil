from dataclasses import dataclass

# Secao 6.1: o modelo de linguagem que escreve ainda nao foi escolhido pelo grupo (decisao 14.5).


@dataclass
class TextoGerado:
    titulo: str
    resumo: str
    corpo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0


# === Gerador (interface do modelo de linguagem que escreve as noticias) ===
class Gerador:
    nome = None
    versao_prompt = None

    def escrever(self, consulta, trechos):
        """Recebe a consulta e os textos recuperados pelo RAG; devolve um TextoGerado."""
        raise NotImplementedError


# === GeradorFalso (so para teste: nao escreve noticia de verdade) ===
class GeradorFalso(Gerador):
    nome = "gerador-falso"
    versao_prompt = "falso-v1"

    def escrever(self, consulta, trechos):
        corpo = "\n\n".join(trechos)
        return TextoGerado(
            titulo=f"[TESTE] {consulta}"[:200],
            resumo=f"[TESTE] Texto de teste montado com {len(trechos)} trechos."[:500],
            corpo=corpo,
            tokens_entrada=len(consulta.split()) + len(corpo.split()),
            tokens_saida=len(corpo.split()),
        )
