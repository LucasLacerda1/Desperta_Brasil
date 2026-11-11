"""
Extrai o texto limpo do inteiro teor de uma PEC (PDF do Infoleg da Camara) com o PyMuPDF.

So para os scripts de analise, fora do portal: o PyMuPDF e AGPL-3.0 (decisao 18.3 em aberto).

O que sai, pelas pistas que o PDF da Camara da:
- linhas verticais (carimbo "PEC n.", "Apresentacao: ..." e codigo de barras);
- margem de baixo ("Assinado eletronicamente...", "Para verificar as assinaturas...");
- numero da pagina no topo;
- paginas do autenticador, com a lista das assinaturas ("Assinaram eletronicamente o documento").
O que vira nota: linhas com fonte menor que a do texto, no pe da pagina; a marca da nota no texto
(numero em fonte pequena, ex.: "criancas1.") sai do texto e fica registrada.
Paragrafos: linha com recuo (primeira linha do paragrafo) ou espaco vertical maior que o normal.

Uso: python scripts/analise_pec/extrair_pdf.py <arquivo.pdf> [--saida texto.txt]
"""

import argparse
import re
import statistics

import pymupdf

MARGEM_DE_BAIXO = 800
MARGEM_DE_CIMA = 60
INICIO_DAS_ASSINATURAS = "Assinaram eletronicamente o documento"
FIM_DO_TEXTO = re.compile(r"^Sala das Sess[õo]es", re.IGNORECASE)
# Codigo interno do documento no pe da ultima pagina (ex.: 2024-10435)
CODIGO_DO_DOCUMENTO = re.compile(r"^\d{4}-\d+$")
INICIO_DE_NOTA = re.compile(r"^\d+\s")
FIM_DE_FRASE = (".", ":", ";", "”", '"', "!", "?", ")")


def _linhas(pagina):
    """Linhas horizontais com texto, cada uma com posicao, tamanho e o texto sem a marca de nota."""
    saida = []
    for bloco in pagina.get_text("dict", sort=True)["blocks"]:
        if bloco["type"] != 0:
            continue
        for linha in bloco["lines"]:
            if round(linha["dir"][0]) != 1 or round(linha["dir"][1]) != 0:
                continue
            spans = [s for s in linha["spans"] if s["text"].strip()]
            if not spans:
                continue
            tamanho = max(s["size"] for s in spans)
            texto, notas = "", []
            for span in spans:
                # Numero em fonte bem menor, colado ao texto: marca de nota de rodape
                if span["size"] < 0.7 * tamanho and span["text"].strip().isdigit() and texto:
                    notas.append(span["text"].strip())
                    continue
                texto += span["text"]
            x0, y0, x1, y1 = linha["bbox"]
            saida.append({"x0": x0, "y0": y0, "y1": y1, "tamanho": tamanho, "texto": " ".join(texto.split()),
                          "marcas": notas})
    return saida


def _juntar_nota(linhas):
    """Notas trazem enderecos quebrados no meio: a linha seguinte cola sem espaco depois de '-' ou '='."""
    texto = ""
    for linha in linhas:
        if texto and not texto.endswith(("-", "=", "/", "%")) and not linha["texto"].startswith("%"):
            texto += " "
        texto += linha["texto"]
    return texto


def extrair(caminho):
    documento = pymupdf.open(caminho)
    corpo, descartadas = [], 0
    paginas_de_texto = 0
    for pagina in documento:
        linhas = _linhas(pagina)
        if any(INICIO_DAS_ASSINATURAS in linha["texto"] for linha in linhas):
            break
        paginas_de_texto += 1
        for linha in linhas:
            if (
                linha["y0"] > MARGEM_DE_BAIXO
                or (linha["y1"] < MARGEM_DE_CIMA and linha["texto"].isdigit())
                or CODIGO_DO_DOCUMENTO.match(linha["texto"])
            ):
                descartadas += 1
                continue
            linha["pagina"] = paginas_de_texto
            corpo.append(linha)

    if not corpo:
        # PDF escaneado (so imagem): precisaria de OCR, por exemplo o Tesseract (Apache 2.0)
        return {"paginas_de_texto": 0, "paginas_no_pdf": len(documento), "paragrafos": [], "depois_do_texto": [],
                "notas": [], "marcas_de_nota": [], "linhas_descartadas": descartadas, "sem_texto": True}

    # Tamanho do texto normal: o mais comum; o que e bem menor e nota de rodape
    tamanho_normal = statistics.mode(round(linha["tamanho"]) for linha in corpo)
    texto, notas = [], []
    for linha in corpo:
        (notas if linha["tamanho"] < tamanho_normal - 1.5 else texto).append(linha)

    margem = min(linha["x0"] for linha in texto)
    paragrafos, atual, anterior = [], [], None
    for linha in texto:
        if anterior is not None:
            espaco = linha["y0"] - anterior["y1"]
            altura = anterior["y1"] - anterior["y0"]
            recuo = linha["x0"] > margem + 30 and abs(linha["x0"] - anterior["x0"]) > 30
            if linha["pagina"] != anterior["pagina"]:
                # Paragrafo que continua na pagina seguinte: a anterior nao fechou a frase e esta nao tem recuo
                continua = not anterior["texto"].endswith(FIM_DE_FRASE) and not recuo
                novo = not continua
            else:
                novo = espaco > 0.9 * altura or recuo
            if novo:
                paragrafos.append(atual)
                atual = []
        atual.append(linha)
        anterior = linha
    paragrafos.append(atual)

    def juntar(linhas):
        partes = []
        for linha in linhas:
            if partes and partes[-1].endswith("-") and linha["texto"][:1].islower():
                partes[-1] = partes[-1][:-1] + linha["texto"]
            else:
                partes.append(linha["texto"])
        return " ".join(partes)

    textos = [juntar(p) for p in paragrafos]

    # Linhas de nota: cada nota comeca com o numero; as seguintes continuam a mesma nota
    notas_juntas = []
    for linha in notas:
        if INICIO_DE_NOTA.match(linha["texto"]) or not notas_juntas:
            notas_juntas.append([linha])
        else:
            notas_juntas[-1].append(linha)
    fim = next((i for i, t in enumerate(textos) if FIM_DO_TEXTO.match(t)), len(textos))
    return {
        "paginas_de_texto": paginas_de_texto,
        "paginas_no_pdf": len(documento),
        "paragrafos": textos[:fim],
        "depois_do_texto": textos[fim:],
        "notas": [_juntar_nota(nota) for nota in notas_juntas],
        "marcas_de_nota": [m for linha in corpo for m in linha["marcas"]],
        "linhas_descartadas": descartadas,
        "sem_texto": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--saida")
    argumentos = parser.parse_args()
    resultado = extrair(argumentos.pdf)
    texto = "\n\n".join(resultado["paragrafos"])
    if argumentos.saida:
        with open(argumentos.saida, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto + "\n")
    else:
        print(texto)
    print(
        f"\n-- {resultado['paginas_de_texto']} de {resultado['paginas_no_pdf']} paginas com texto; "
        f"{len(resultado['paragrafos'])} paragrafos; {resultado['linhas_descartadas']} linhas de carimbo descartadas; "
        f"notas: {resultado['notas']}; marcas: {resultado['marcas_de_nota']}; "
        f"depois do texto: {resultado['depois_do_texto']}"
    )


if __name__ == "__main__":
    main()
