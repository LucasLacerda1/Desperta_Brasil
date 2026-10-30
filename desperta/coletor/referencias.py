from desperta.ext.db import db
from desperta.orgaos.models import Evento, Orgao
from desperta.parlamentares.models import Deputado, Partido
from desperta.proposicoes.models import Proposicao

from .cliente import ErroAPI


# === Referencias (busca sob demanda o registro que a FK exige e ainda nao esta no banco) ===
class Referencias:
    def __init__(self, execucao):
        self.execucao = execucao
        self.cliente = execucao.cliente
        # Ids que a API nao devolveu: nao perguntar de novo nesta coleta
        self._ausentes = set()

    def _garantir(self, modelo, id_registro, caminho, gravar):
        """Devolve o id se o registro existe ou se conseguiu trazer da API; senao, None."""
        if id_registro is None:
            return None
        if db.session.get(modelo, id_registro) is not None:
            return id_registro
        marca = (modelo.__tablename__, id_registro)
        if marca in self._ausentes:
            return None
        try:
            item = self.cliente.obter(f"{caminho}/{id_registro}")
        except ErroAPI as erro:
            if erro.status != 404:
                raise
            item = None
        registro = gravar(self.execucao, item) if item else None
        if registro is None:
            self._ausentes.add(marca)
            self.execucao.log(
                "aviso",
                "referencia_ausente",
                f"{caminho}/{id_registro} nao foi encontrado na API",
                entidade=modelo.__tablename__,
                entidade_id=id_registro,
            )
            return None
        return id_registro

    def deputado(self, id_deputado):
        from .deputados import gravar_detalhe

        return self._garantir(Deputado, id_deputado, "deputados", gravar_detalhe)

    def orgao(self, id_orgao):
        from .orgaos import gravar_orgao

        return self._garantir(Orgao, id_orgao, "orgaos", gravar_orgao)

    def partido(self, id_partido):
        from .partidos import gravar_partido

        return self._garantir(Partido, id_partido, "partidos", gravar_partido)

    def proposicao(self, id_proposicao):
        """So o registro principal: filhos_sincronizados_em fica nulo e entra nos pendentes."""
        from .proposicoes import gravar_proposicao

        return self._garantir(
            Proposicao, id_proposicao, "proposicoes", lambda ex, item: gravar_proposicao(ex, item, self)
        )

    def evento(self, id_evento):
        """So o registro principal: a pauta entra nos pendentes."""
        from .eventos import gravar_evento

        return self._garantir(Evento, id_evento, "eventos", lambda ex, item: gravar_evento(ex, item, self))
