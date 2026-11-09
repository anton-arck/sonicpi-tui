"""Daemon FALSO de Sonic Pi para probar el cliente sin Sonic Pi ni audio. Imita el protocolo de daemon.rb:
imprime la linea de puertos (formato de 4.x o de 5.x) y responde a /ping con /ack y la senal de motor listo.
Variables: FALSO_VERSION=4|5|otro (otro = formato invalido), FALSO_SENAL_5=log|clockwork, FALSO_REGISTRO=ruta donde anota lo recibido."""
import json, os, select, socket, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cliente import osc_pack, osc_parse

version = os.environ.get("FALSO_VERSION", "4"); registro = os.environ.get("FALSO_REGISTRO"); senal5 = os.environ.get("FALSO_SENAL_5", "log")
TOKEN = 123456

def libre():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

p_daemon, p_escucha, p_envio, p_motor, p_cues = (libre() for _ in range(5))
s_daemon = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_daemon.bind(("127.0.0.1", p_daemon))
s_envio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s_envio.bind(("127.0.0.1", p_envio))
salida = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

if version == "4": print(p_daemon, p_escucha, p_envio, p_motor, p_cues, libre(), libre(), TOKEN, flush=True)
elif version == "5": print(p_daemon, p_escucha, p_envio, p_motor, p_cues, TOKEN, flush=True)
else: print(p_daemon, p_escucha, p_envio, flush=True)

def decir(direccion, *a): salida.sendto(osc_pack(direccion, *a), ("127.0.0.1", p_escucha))
def anota(d, a, origen):
    if registro:
        with open(registro, "a") as f: f.write(json.dumps({"dir": d, "args": a, "en": origen}) + "\n")

while True:
    for s in select.select([s_daemon, s_envio], [], [], 1)[0]:
        d, a = osc_parse(s.recv(65535)); anota(d, a, "daemon" if s is s_daemon else "spider")
        if d == "/daemon/exit": sys.exit(0)
        if d == "/ping":
            decir("/ack", "id")
            if version == "4": decir("/scsynth/info", "x")
            elif senal5 == "clockwork": decir("/clockwork/info", "x")
            else: decir("/log/info", 0, "Live Coding begins.")
        elif d == "/run-code":
            if "BOOM" in a[1]: decir("/error", 1, "RuntimeError: boom", "eval:7:in `x'", 7, 0, 0, "BOOM")
            else: decir("/log/multi_message", 1, '"live_loop"', "0.0", 2, 0, "hola desde el falso daemon")
