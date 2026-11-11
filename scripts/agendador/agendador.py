"""
Agendador das rotinas do coletor com timers de usuario do systemd (decisao 23.8, item 2).

Cada timer chama `flask coletar agendada <rotina>`, que roda a coleta e, sob a mesma trava,
indexa o que mudou e escreve os rascunhos novos. Os caminhos vem da pasta do projeto e do
Python que rodou este script, para funcionar igual no PC e no servidor (decisao 21.4).

Uso (de preferencia pelo invoke):
    python scripts/agendador/agendador.py mostrar    # so mostra os arquivos, sem instalar
    python scripts/agendador/agendador.py instalar   # grava em ~/.config/systemd/user e liga os timers
    python scripts/agendador/agendador.py remover    # desliga os timers e apaga os arquivos
    python scripts/agendador/agendador.py situacao   # proximas execucoes
"""

import os
import subprocess
import sys

PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICO = "desperta-coleta@.service"

# Calendario do RF02 (decisoes 12.1 e 13.1 a 13.3). A horaria fica no minuto 5 para nao
# coincidir com as outras; diaria, semanal e mensal esperam a coleta em andamento terminar.
# Persistent=true: se o PC estava desligado na hora marcada, a rotina roda quando ele ligar.
TIMERS = {
    "horaria": ("*-*-* *:05:00", False),
    "diaria": ("*-*-* 03:30:00", True),
    "semanal": ("Sun *-*-* 04:30:00", True),
    "mensal": ("*-*-01 05:30:00", True),
}


def pasta_systemd():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "systemd", "user")


def nome_timer(rotina):
    return f"desperta-{rotina}.timer"


def unidades(projeto=PROJETO, flask=None):
    """Devolve {nome do arquivo: conteudo} das unidades do systemd."""
    flask = flask or os.path.join(os.path.dirname(sys.executable), "flask")
    log = os.path.join(projeto, "instance", "agendador.log")
    arquivos = {
        SERVICO: (
            "[Unit]\n"
            "Description=Desperta Brasil: rotina %i do coletor, indexacao e rascunhos\n"
            "\n"
            "[Service]\n"
            "Type=oneshot\n"
            f"WorkingDirectory={projeto}\n"
            f"ExecStart={flask} --app app.py coletar agendada %i\n"
            f"StandardOutput=append:{log}\n"
            f"StandardError=append:{log}\n"
            "Nice=10\n"
            # A diaria pode esperar ate 3 horas pela trava e rodar mais 3; acima disso algo travou
            "TimeoutStartSec=8h\n"
            # A coleta fecha o registro e libera a trava ao receber SIGTERM (decisao 13.6)
            "KillSignal=SIGTERM\n"
        )
    }
    for rotina, (calendario, persistente) in TIMERS.items():
        arquivos[nome_timer(rotina)] = (
            "[Unit]\n"
            f"Description=Desperta Brasil: rotina {rotina} do coletor\n"
            "\n"
            "[Timer]\n"
            f"OnCalendar={calendario}\n"
            f"Persistent={'true' if persistente else 'false'}\n"
            f"Unit=desperta-coleta@{rotina}.service\n"
            "\n"
            "[Install]\n"
            "WantedBy=timers.target\n"
        )
    return arquivos


def _systemctl(*args, rodar=subprocess.run):
    return rodar(["systemctl", "--user", *args], check=True)


def instalar(destino=None, rodar=subprocess.run):
    destino = destino or pasta_systemd()
    os.makedirs(destino, exist_ok=True)
    os.makedirs(os.path.join(PROJETO, "instance"), exist_ok=True)
    for nome, conteudo in unidades().items():
        with open(os.path.join(destino, nome), "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
        print(f"gravado {os.path.join(destino, nome)}")
    _systemctl("daemon-reload", rodar=rodar)
    _systemctl("enable", "--now", *(nome_timer(rotina) for rotina in TIMERS), rodar=rodar)


def remover(destino=None, rodar=subprocess.run):
    destino = destino or pasta_systemd()
    timers = [nome_timer(rotina) for rotina in TIMERS]
    # Desligar um timer nao interrompe uma coleta que ja esta rodando
    _systemctl("disable", "--now", *timers, rodar=rodar)
    for nome in [SERVICO, *timers]:
        caminho = os.path.join(destino, nome)
        if os.path.exists(caminho):
            os.remove(caminho)
            print(f"apagado {caminho}")
    _systemctl("daemon-reload", rodar=rodar)


def situacao(rodar=subprocess.run):
    rodar(["systemctl", "--user", "list-timers", "--all", "desperta-*"], check=False)


def main(argv):
    acao = argv[1] if len(argv) > 1 else "mostrar"
    if acao == "mostrar":
        for nome, conteudo in unidades().items():
            print(f"# {nome}\n{conteudo}")
    elif acao == "instalar":
        instalar()
        situacao()
    elif acao == "remover":
        remover()
    elif acao == "situacao":
        situacao()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
