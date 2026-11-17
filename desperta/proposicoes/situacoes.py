# ----------------------------------------------------------
# Situacao explicada (decisao 25.13)
# Para cada codigo de situacao da Camara (statusProposicao.codSituacao), uma explicacao
# em linguagem popular. RASCUNHO do Claude Code: o grupo revisa o texto.
# O nome mostrado ao leitor e sempre o que a Camara mandou; a explicacao so acompanha.
# Codigo fora do dicionario: mostra so o nome da Camara, sem explicacao inventada,
# e a geracao grava um aviso no log (situacao_desconhecida).
# ----------------------------------------------------------
SITUACOES = {
    900: "O texto aprovado está sendo preparado na forma final (os autógrafos) pela Mesa da Câmara.",
    901: "A proposta precisa de uma comissão especial, que ainda não foi montada.",
    902: "A proposta precisa de uma comissão especial, que ainda não foi criada.",
    903: "A proposta espera ser votada.",
    904: "Houve um recurso contra uma decisão sobre a proposta, e ele espera ser votado.",
    905: "A proposta espera uma decisão do presidente da Câmara sobre o caminho que ela vai seguir (o despacho).",
    907: "A comissão ainda não escolheu o deputado ou a deputada que vai estudar a proposta e dar a opinião "
    "sobre ela (o relator).",
    910: "A proposta espera ser enviada para a próxima etapa.",
    911: "A comissão especial que vai analisar a proposta já foi criada, mas ainda não começou a funcionar.",
    915: "O relator está estudando a proposta e ainda não apresentou a opinião dele (o parecer).",
    917: "A proposta foi enviada a um órgão que ainda não registrou o recebimento.",
    918: "Está aberto um prazo para recurso contra uma decisão tomada sobre a proposta.",
    922: "Deputados pediram mais tempo para examinar a proposta antes da votação (pedido de vista).",
    923: "A proposta foi arquivada: ela parou de andar e só volta se for desarquivada.",
    924: "A proposta já passou pelas etapas exigidas e pode entrar na pauta de votação.",
    925: "A proposta foi juntada a outra sobre o mesmo assunto, e as duas andam juntas.",
    926: "A Câmara terminou a parte dela; agora a proposta está com o Senado.",
    927: "A proposta espera ser juntada a outra sobre o mesmo assunto.",
    928: "O parecer do relator já foi apresentado e espera ser analisado.",
    929: "O texto foi aprovado e espera a redação final, que acerta a forma do texto.",
    932: "Ainda não foi decidido para onde a proposta segue.",
    936: "A proposta espera providências internas da Câmara.",
    937: "O presidente da República vetou (recusou) todo o texto aprovado. O Congresso ainda pode derrubar o veto.",
    939: "O texto foi vetado pelo presidente da República, e o Congresso vai decidir se mantém ou derruba o veto.",
    941: "A Câmara registrou a proposta como recusada.",
    950: "Quem apresentou a proposta pediu para retirá-la, e ela parou de andar.",
    1050: "A Câmara está conferindo o prazo para recursos.",
    1090: "A proposta espera ser analisada.",
    1091: "A proposta espera a análise sobre se ela fere a Constituição.",
    1120: "A proposta foi devolvida a quem a apresentou e não seguiu adiante.",
    1140: "A proposta virou lei (ou outra norma) e já vale no país.",
    1150: "O Congresso aprovou o texto; agora o presidente da República decide se assina (sanciona) ou veta.",
    1160: "O texto aprovado espera ser enviado ao presidente da República, que vai sancionar ou vetar.",
    1170: "O relator deixou a comissão; a proposta espera ser devolvida e ganhar outro relator.",
    1200: "A proposta espera autorização para o despacho (a decisão sobre o caminho dela).",
    1201: "A proposta espera a assinatura (chancela) do presidente da Câmara numa decisão sobre ela.",
    1220: "A proposta espera a análise do presidente da Câmara sobre o caminho que ela vai seguir.",
    1221: "A proposta espera uma autorização do presidente da Câmara.",
    1270: "O texto foi aprovado e espera ser enviado para a redação final, que acerta a forma do texto.",
    1280: "A comissão que analisa a proposta está funcionando.",
    1285: "O andamento da proposta na Câmara terminou.",
    1292: "A proposta perdeu a validade. Isso acontece, por exemplo, com medida provisória que não é votada no prazo.",
    1293: "A Câmara aprovou o texto, que espera ser enviado ao Senado.",
    1299: "A proposta foi enviada ao Congresso Nacional (a Câmara e o Senado juntos).",
    1350: "A proposta espera a notificação do deputado ou da deputada que é alvo de uma representação.",
}

# A Camara manda este codigo quando a situacao nao foi definida: vale como nao informada
SITUACOES_SEM_INFORMACAO = frozenset({1311})

# ----------------------------------------------------------
# Marcos (decisao 25.13): situacoes que viram noticia propria no filtro.
# Lista INTERNA, para a relacao com a API; o leitor nunca ve.
# ----------------------------------------------------------
MARCOS = frozenset(
    {
        924,  # Pronta para Pauta
        926,  # Aguardando Apreciacao pelo Senado Federal
        1293,  # Aguardando Envio ao Senado Federal
        1270,  # Aguardando Envio a Redacao Final
        929,  # Aguardando Redacao Final
        1150,  # Aguardando Sancao
        1140,  # Transformado em Norma Juridica
        937,  # Vetado totalmente
        939,  # Aguardando Apreciacao do Veto
        1292,  # Perdeu a Eficacia
        923,  # Arquivada
        950,  # Retirado pelo(a) Autor(a)
        1120,  # Devolvida ao(a) Autor(a)
    }
)


def situacao_informada(cod_situacao, nome):
    """A Camara informou a situacao? Codigo nulo, nome vazio ou "<Nao Definido>" contam como nao."""
    from .services import informado

    return cod_situacao is not None and cod_situacao not in SITUACOES_SEM_INFORMACAO and informado(nome) is not None


def explicar_situacao(cod_situacao, nome):
    """
    Situacao publica (decisao 25.13): o nome exato da Camara e, se o codigo estiver no
    dicionario, a explicacao popular. conhecida=False pede um aviso no log.
    """
    if not situacao_informada(cod_situacao, nome):
        return {"informada": False, "codigo": cod_situacao, "nome_da_camara": None, "explicacao": None}
    return {
        "informada": True,
        "codigo": cod_situacao,
        "nome_da_camara": nome.strip(),
        "explicacao": SITUACOES.get(cod_situacao),
    }


def situacao_conhecida(cod_situacao, nome):
    """False so quando a Camara informou um codigo que o dicionario nao tem."""
    return not situacao_informada(cod_situacao, nome) or cod_situacao in SITUACOES
