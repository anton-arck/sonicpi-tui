"""Prueba de osciloscopio.py con comandos simulados (no abre paneles ni usa audio)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osciloscopio as O
def check(n, ok): print(("OK    " if ok else "FALLA ") + n); return bool(ok)

def falso(respuestas):
    log = []
    def ej(cmd):
        log.append(cmd)
        for k, v in respuestas.items():
            if cmd[0] == k[0] and (len(k) == 1 or k[1] in cmd): return v
        return (0, "")
    return ej, log

hay = lambda _: "/usr/bin/scope-tui"
r = []
ej, log = falso({("pactl",): (0, "salida.analog")})
r.append(check("monitor = salida por defecto + .monitor", O.monitor(ej) == "salida.analog.monitor"))
r.append(check("sin pactl: sin fuente", O.monitor(falso({("pactl",): (1, "")})[0]) is None))
p, m = O.abrir({}, ej, lambda _: None)
r.append(check("sin scope-tui: avisa como instalarlo", p is None and "paru -S scope-tui" in m))
p, m = O.abrir({}, ej, hay)
r.append(check("sin zellij ni tmux: avisa", p is None and "zellij o tmux" in m))
ej, log = falso({("pactl",): (0, "salida"), ("zellij", "run"): (0, "terminal_7")})
p, m = O.abrir({"ZELLIJ": "0"}, ej, hay)
run = next(c for c in log if c[:2] == ["zellij", "run"])
r.append(check("zellij: panel a la derecha con scope-tui sobre el monitor", p == ("zellij", "terminal_7") and run[-3:] == ["scope-tui", "pulse", "salida.monitor"] and "right" in run and "-c" in run))
r.append(check("zellij: devuelve el foco al editor", ["zellij", "action", "move-focus", "left"] in log))
ej, log = falso({("pactl",): (0, "salida"), ("tmux",): (0, "%5")})
p, m = O.abrir({"TMUX": "x"}, ej, hay)
r.append(check("tmux: panel sin quitar el foco (-d) y con su id", p == ("tmux", "%5") and any(c[:2] == ["tmux", "split-window"] and "-d" in c for c in log)))
ej, log = falso({("zellij", "run"): (1, "")})
r.append(check("fallo de zellij: no hay panel", O.abrir({"ZELLIJ": "0"}, ej, hay)[0] is None))
ej, log = falso({})
r.append(check("cerrar zellij usa el id", O.cerrar(("zellij", "terminal_7"), ej) and log[-1][-1] == "terminal_7"))
r.append(check("cerrar tmux usa kill-pane", O.cerrar(("tmux", "%5"), ej) and log[-1][:2] == ["tmux", "kill-pane"]))
r.append(check("panel que ya no existe: False", not O.cerrar(("tmux", "%5"), falso({("tmux",): (1, "")})[0]) and not O.cerrar(None)))
print(f"\n{sum(r)}/{len(r)} OK"); sys.exit(0 if all(r) else 1)
