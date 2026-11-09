"""Cliente minimo de Sonic Pi 4.x y 5.x (sin ventana); la version se detecta sola. Lanza su propio servidor y habla con el por OSC.
Basado en lo que hace /usr/lib/sonic-pi/server/ruby/bin/repl.rb. Solo libreria estandar."""
import html, os, re, socket, struct, subprocess, threading, time

RUBY = os.environ.get("SONICPI_RUBY", "/usr/bin/ruby")                 # el Ruby del sistema (no el de asdf/rbenv)
# Copia aislada de Sonic Pi 4.x (la crea tools/aislar-sonicpi.sh): independiente del que haya instalado en el sistema.
AISLADO = os.environ.get("SONICPI_TUI_DIR", os.path.expanduser("~/.local/share/sonicpi-tui"))
AISLADO_DAEMON = f"{AISLADO}/sonic-pi-4.6/lib/server/ruby/bin/daemon.rb"
# Sitios habituales de daemon.rb en el sistema: 4.x (paquete de Arch) y 5.x (arbol app/server/...).
DAEMONS = ["/usr/lib/sonic-pi/server/ruby/bin/daemon.rb", "/usr/lib/sonic-pi/app/server/ruby/bin/daemon.rb",
           "/usr/share/sonic-pi/app/server/ruby/bin/daemon.rb", "/opt/sonic-pi/app/server/ruby/bin/daemon.rb"]

def buscar_daemon(env=None, existe=os.path.exists):
    """Orden: SONICPI_DAEMON > copia aislada de la 4.x (si existe y no pides SONICPI_USAR=sistema) > Sonic Pi del sistema."""
    env = os.environ if env is None else env
    if env.get("SONICPI_DAEMON"): return env["SONICPI_DAEMON"]
    if env.get("SONICPI_USAR") != "sistema" and existe(AISLADO_DAEMON): return AISLADO_DAEMON
    return next((d for d in DAEMONS if existe(d)), DAEMONS[0])

DAEMON = buscar_daemon()

def version_probable(daemon=None):
    """Version de Sonic Pi que se va a usar, deducida de la ruta del daemon (el arbol app/server/... es el de la 5.x)."""
    return 5 if "/app/server/ruby/bin/daemon.rb" in (daemon or DAEMON) else 4


# ---------- OSC minimo ----------
def _pad(b):
    return b + b"\x00" * (-len(b) % 4)

def osc_pack(direccion, *args):
    tags, datos = ",", b""
    for a in args:
        if isinstance(a, bool):
            a = int(a)
        if isinstance(a, int):
            tags += "i"; datos += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"; datos += struct.pack(">f", a)
        else:
            tags += "s"; datos += _pad(str(a).encode("utf-8") + b"\x00")
    return _pad(direccion.encode() + b"\x00") + _pad(tags.encode() + b"\x00") + datos

def _leer_str(d, i):
    j = d.index(b"\x00", i)
    s = d[i:j].decode("utf-8", "replace")
    return s, (j + 4) // 4 * 4 if (j + 1) % 4 else j + 1

def osc_parse(d):
    direccion, i = _leer_str(d, 0)
    tags, i = _leer_str(d, i)
    args = []
    for t in tags[1:]:
        if t == "i": args.append(struct.unpack(">i", d[i:i + 4])[0]); i += 4
        elif t == "f": args.append(struct.unpack(">f", d[i:i + 4])[0]); i += 4
        elif t == "d": args.append(struct.unpack(">d", d[i:i + 8])[0]); i += 8
        elif t == "h": args.append(struct.unpack(">q", d[i:i + 8])[0]); i += 8
        elif t == "s":
            s, i = _leer_str(d, i); args.append(s)
        elif t == "b":
            n = struct.unpack(">i", d[i:i + 4])[0]; args.append(d[i + 4:i + 4 + n]); i += 4 + (n + 3) // 4 * 4
        elif t in "TF": args.append(t == "T")
        elif t == "N": args.append(None)
    return direccion, args


def procesos_sonicpi():
    """Procesos de Sonic Pi vivos (ventana, daemon, spider, scsynth). Se identifican por el NOMBRE del ejecutable,
    no por el texto de la linea de comandos (que daria falsos positivos, p. ej. con este mismo comando)."""
    salida = subprocess.run(["ps", "-eo", "comm=,args="], capture_output=True, text=True).stdout.splitlines()
    vivos = []
    for linea in salida:
        comm, _, args = linea.strip().partition(" ")
        args = args.strip()
        if comm in ("sonic-pi", "scsynth", "beam.smp") or "supersonic" in comm.lower() or (
                comm.startswith("ruby") and ("server/ruby/bin/daemon.rb" in args or "server/ruby/bin/spider-server.rb" in args)):
            vivos.append(linea.strip()[:100])
    return vivos


def leer_puertos(linea):
    """Interpreta la linea de puertos que imprime daemon.rb y deduce la version por su formato:
    4.x -> 8 numeros (daemon, escucha, envio, scsynth, cues, tau, tau-phx, token); 5.x -> 6 (sin tau: daemon, escucha, envio, motor, cues, token)."""
    try:
        v = [int(x) for x in linea.split()]
    except ValueError:
        raise RuntimeError(f"el daemon no imprimio los puertos como se esperaba: {linea!r}")
    if len(v) == 8: return {"version": 4, "daemon": v[0], "escucha": v[1], "envio": v[2], "motor": v[3], "cues": v[4], "token": v[7]}
    if len(v) == 6: return {"version": 5, "daemon": v[0], "escucha": v[1], "envio": v[2], "motor": v[3], "cues": v[4], "token": v[5]}
    raise RuntimeError(f"linea de puertos inesperada del daemon ({len(v)} valores, se esperaban 8 en Sonic Pi 4 o 6 en Sonic Pi 5): {linea!r}")


class SonicPi:
    def __init__(self, al_mensaje=None):
        self.al_mensaje = al_mensaje or (lambda tipo, texto: print(f"[{tipo}] {texto}", flush=True))
        self.listo = threading.Event()
        self.scsynth_listo = threading.Event()      # el motor de audio esta listo (scsynth en 4.x, SuperSonic en 5.x)
        self.version = None                         # 4 o 5, segun el daemon
        self._vivo = False
        self.vistos = {}        # direccion OSC -> veces recibida (para diagnostico)

    def iniciar(self, timeout=90):
        entorno = {k: v for k, v in os.environ.items() if k not in ("GEM_PATH", "GEM_HOME")}      # como hace repl.rb de 5.0: los gems del usuario ensucian la salida del daemon
        if DAEMON == AISLADO_DAEMON:                                                           # la copia aislada tiene su propia configuracion y logs, sin tocar ~/.sonic-pi
            entorno.setdefault("SONIC_PI_HOME", f"{AISLADO}/home")
        self.proc = subprocess.Popen([RUBY, DAEMON], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=entorno)
        linea = self.proc.stdout.readline()
        try:
            v = leer_puertos(linea)
        except RuntimeError:
            self.proc.kill()                    # no dejar el daemon colgado si no lo entendemos
            raise
        self.version = v["version"]
        self.p_daemon, self.p_escucha, self.p_envio, self.p_scsynth, self.p_cues, self.token = (
            v["daemon"], v["escucha"], v["envio"], v["motor"], v["cues"], v["token"])
        self._vivo = True
        threading.Thread(target=self._drenar_daemon, daemon=True).start()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_in.bind(("127.0.0.1", self.p_escucha))
        threading.Thread(target=self._escuchar, daemon=True).start()
        threading.Thread(target=self._keepalive, daemon=True).start()
        t0 = time.time()
        while not (self.listo.is_set() and self.scsynth_listo.is_set()):
            self._enviar_spider("/ping", self.token, "hola desde sonicpi-remake")
            time.sleep(0.5)
            if time.time() - t0 > timeout:
                estado = f"ack={self.listo.is_set()} scsynth_info={self.scsynth_listo.is_set()} recibido={self.vistos}"
                self.cerrar()
                raise TimeoutError(f"Sonic Pi no arranco a tiempo ({estado})")
        self.volumen(0.3)

    def _drenar_daemon(self):
        for linea in self.proc.stdout:          # evita que el daemon se bloquee si su salida se llena
            pass

    def _enviar_spider(self, d, *a):
        try:
            self.sock.sendto(osc_pack(d, *a), ("127.0.0.1", self.p_envio))
        except OSError:
            pass

    def _keepalive(self):
        while self._vivo:
            self.sock.sendto(osc_pack("/daemon/keep-alive", self.token), ("127.0.0.1", self.p_daemon))
            time.sleep(5)

    def _escuchar(self):
        self.sock_in.settimeout(0.5)
        while self._vivo:
            try:
                datos, _ = self.sock_in.recvfrom(65535)
            except (socket.timeout, OSError):
                continue
            try:
                d, a = osc_parse(datos)
            except Exception as e:
                self.al_mensaje("aviso", f"mensaje OSC ilegible: {e}"); continue
            self.vistos[d] = self.vistos.get(d, 0) + 1
            if d == "/ack": self.listo.set()
            elif d in ("/scsynth/info", "/clockwork/info"): self.scsynth_listo.set()
            elif d == "/log/info" and len(a) >= 2:
                if self.version == 5 and "Live Coding begin" in str(a[1]):      # 5.x ya no manda /clockwork/info solo: su arranque sin ventana oficial da el motor por listo con este mensaje
                    self.scsynth_listo.set()
                self.al_mensaje("log", a[1])
            elif d == "/log/multi_message" and len(a) > 4:
                for texto in a[4:]:                  # pares (color:int, texto:str); nos quedamos con los textos
                    if isinstance(texto, str):
                        self.al_mensaje("log", texto)
            elif d == "/error" and len(a) >= 4:
                m = re.search(r"eval:(\d+)", html.unescape(str(a[2])))      # la linea real esta en el backtrace
                linea = m.group(1) if m else a[3]
                self.al_mensaje("error", f"linea {linea}: " + " ".join(html.unescape(a[1]).replace("[eval] - Thread death!", "").split()))
            elif d == "/flash" and len(a) >= 3 and a[1] == "eval": self.al_mensaje("flash", int(a[2]))              # solo 5.x: linea (1..) que acaba de sonar
            elif d == "/live_loop/scope" and len(a) >= 4 and a[2] == "eval": self.al_mensaje("bucle", (str(a[1]), int(a[3])))   # solo 5.x: bucle vivo y su linea
            elif d == "/live_loop/scope-ended" and len(a) >= 2: self.al_mensaje("bucle_fin", str(a[1]))
            elif d == "/syntax_error" and len(a) >= 4: self.al_mensaje("sintaxis", f"linea {a[3]}: {a[1]} -> {a[2]}")
            elif d == "/exited": self.al_mensaje("log", "Sonic Pi se ha cerrado")

    # ---------- API ----------
    def ejecutar(self, codigo): self._enviar_spider("/run-code", self.token, codigo)
    def parar(self): self._enviar_spider("/stop-all-jobs", self.token)
    def volumen(self, v):
        """0..1. En 4.x es /mixer-amp (amplitud); en 5.x /mixer-output-volume (fader tras el limitador)."""
        self._enviar_spider("/mixer-output-volume" if self.version == 5 else "/mixer-amp", self.token, float(v), 1)
    def grabar_iniciar(self): self._enviar_spider("/start-recording", self.token)
    def grabar_parar(self): self._enviar_spider("/stop-recording", self.token)
    def grabar_guardar(self, ruta): self._enviar_spider("/save-recording", self.token, ruta)

    def cerrar(self):
        if not self._vivo:
            return
        self._vivo = False
        try:
            self.sock.sendto(osc_pack("/daemon/exit", self.token), ("127.0.0.1", self.p_daemon))
            self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()


if __name__ == "__main__":      # prueba silenciosa: solo escribe texto, no suena nada
    sp = SonicPi()
    print("arrancando servidor (puede tardar)...", flush=True)
    t = time.time(); sp.iniciar()
    print(f"Sonic Pi {sp.version}.x | servidor listo en {time.time()-t:.1f}s | puertos: daemon={sp.p_daemon} envio={sp.p_envio} escucha={sp.p_escucha}", flush=True)
    sp.ejecutar('puts "hola desde Sonic Pi (sin sonido)"\nputs 6 * 7')
    time.sleep(3)
    sp.cerrar()
    print("servidor cerrado", flush=True)
