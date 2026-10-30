from desperta.parlamentares.models import Lideranca

from .execucao import Execucao
from .normalizacao import para_data
from .referencias import Referencias


def coletar(cliente, id_legislatura):
    caminho = f"legislaturas/{id_legislatura}/lideres"
    with Execucao(cliente, "liderancas", "completa", f"/{caminho}") as execucao:
        referencias = Referencias(execucao)
        for item in list(cliente.paginar(caminho, {"itens": 100})):
            id_deputado = referencias.deputado((item.get("parlamentar") or {}).get("id"))
            if id_deputado is None:
                continue
            bancada = item.get("bancada") or {}
            # O id e gerado pelo banco: o upsert usa a chave natural
            chave = {
                "deputado_id": id_deputado,
                "bancada_nome": bancada.get("nome"),
                "titulo": item.get("titulo"),
                "data_inicio": para_data(item.get("dataInicio")),
            }
            execucao.principal(
                Lideranca,
                chave,
                {
                    **chave,
                    "bancada_tipo": bancada.get("tipo"),
                    "data_fim": para_data(item.get("dataFim")),
                },
            )
            execucao.concluir_item()
