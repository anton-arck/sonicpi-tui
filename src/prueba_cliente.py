"""Prueba del cliente contra un daemon FALSO que imita Sonic Pi 4.x y 5.x (sin Sonic Pi, sin audio).
Uso: .venv/bin/python -I src/prueba_cliente.py"""
import json, os, sys, tempfile, time
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ["SONICPI_RUBY"] = sys.executable; os.environ["SONICPI_DAEMON"] = os.path.join(AQUI, "falso_daemon.py")
import cliente
from cliente import SonicPi, leer_puertos

def check(n, ok): print(("OK    " if ok else "FALLA ") + n); return bool(ok)
def falla(linea):
    try: leer_puertos(linea)
    except RuntimeError as e: return str(e)

def sesion(version, **env):
    """Arranca el cliente contra el falso daemon y devuelve (resultados, mensajes)."""
    reg = tempfile.mktemp(suffix=".jsonl"); os.environ.update({"FALSO_VERSION": version, "FALSO_REGISTRO": reg, **env})
    msgs = []; r = []; sp = SonicPi(al_mensaje=lambda t, x: msgs.append((t, x)))
    t0 = time.time(); sp.iniciar(timeout=20)
    r.append(check(f"[{version}] arranca y queda listo en {time.time() - t0:.1f}s", sp.listo.is_set() and sp.scsynth_listo.is_set()))
    r.append(check(f"[{version}] detecta la version {version}", sp.version == int(version)))
    def recibido(): return [json.loads(l) for l in open(reg)] if os.path.exists(reg) else []
    def espera(f, seg=5):
        t = time.time()
        while time.time() - t < seg:
            if f(recibido()): return True
            time.sleep(0.1)
        return False
    sp.volumen(0.5)
    dir_vol = "/mixer-output-volume" if version == "5" else "/mixer-amp"
    r.append(check(f"[{version}] volumen usa {dir_vol} con (token, 0.5, 1)", espera(lambda x: any(m["dir"] == dir_vol and m["args"] == [sp.token, 0.5, 1] for m in x))))
    r.append(check(f"[{version}] no usa el mensaje de volumen de la otra version", not any(m["dir"] == ("/mixer-amp" if version == "5" else "/mixer-output-volume") for m in recibido())))
    sp.ejecutar("play 60"); r.append(check(f"[{version}] ejecutar envia /run-code con el token", espera(lambda x: any(m["dir"] == "/run-code" and m["args"] == [sp.token, "play 60"] for m in x))))
    sp.parar(); r.append(check(f"[{version}] parar envia /stop-all-jobs", espera(lambda x: any(m["dir"] == "/stop-all-jobs" for m in x))))
    r.append(check(f"[{version}] manda keep-alive al daemon", espera(lambda x: any(m["dir"] == "/daemon/keep-alive" and m["en"] == "daemon" for m in x))))
    r.append(check(f"[{version}] recibe el log del programa", espera(lambda x: any(t == "log" and "hola desde el falso daemon" in s for t, s in msgs))))
    sp.ejecutar("BOOM"); r.append(check(f"[{version}] un error llega con su linea", espera(lambda x: any(t == "error" and s.startswith("linea 7:") for t, s in msgs))))
    sp.cerrar(); r.append(check(f"[{version}] cerrar envia /daemon/exit y el daemon termina", sp.proc.poll() is not None and any(m["dir"] == "/daemon/exit" for m in recibido())))
    os.remove(reg); return r

r = []
r.append(check("puertos 4.x: 8 valores -> version 4 y token en el octavo", leer_puertos("1 2 3 4 5 6 7 99\n") == {"version": 4, "daemon": 1, "escucha": 2, "envio": 3, "motor": 4, "cues": 5, "token": 99}))
r.append(check("puertos 5.x: 6 valores -> version 5 y token en el sexto", leer_puertos("1 2 3 4 5 99\n") == {"version": 5, "daemon": 1, "escucha": 2, "envio": 3, "motor": 4, "cues": 5, "token": 99}))
r.append(check("salida basura da error legible", "no imprimio los puertos" in (falla("Warning: algo\n") or "")))
r.append(check("numero de valores raro da error legible", "inesperada" in (falla("1 2 3\n") or "")))
r.append(check("buscar_daemon respeta SONICPI_DAEMON", cliente.buscar_daemon() == os.environ["SONICPI_DAEMON"]))
AIS, SIS = cliente.AISLADO_DAEMON, cliente.DAEMONS[0]
r.append(check("daemon: SONICPI_DAEMON manda sobre todo", cliente.buscar_daemon({"SONICPI_DAEMON": "/x"}, lambda p: True) == "/x"))
r.append(check("daemon: con copia aislada se prefiere a la del sistema", cliente.buscar_daemon({}, lambda p: True) == AIS))
r.append(check("daemon: SONICPI_USAR=sistema ignora la copia aislada", cliente.buscar_daemon({"SONICPI_USAR": "sistema"}, lambda p: True) == SIS))
r.append(check("daemon: sin copia aislada usa la del sistema", cliente.buscar_daemon({}, lambda p: p != AIS) == SIS))
r.append(check("daemon: Sonic Pi 5 en otra ruta del sistema", cliente.buscar_daemon({}, lambda p: p == cliente.DAEMONS[1]) == cliente.DAEMONS[1]))
r += sesion("4")
r += sesion("5")
r += sesion("5", FALSO_SENAL_5="clockwork")
os.environ.update({"FALSO_VERSION": "9"})
try: SonicPi().iniciar(timeout=5); r.append(check("formato invalido deberia fallar", False))
except RuntimeError as e: r.append(check("formato invalido: error claro", "inesperada" in str(e)))
print(f"\n{sum(r)}/{len(r)} comprobaciones correctas")
