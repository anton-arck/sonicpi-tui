"""Osciloscopio externo: abre `scope-tui` (https://github.com/alemidev/scope-tui) en un panel de zellij o tmux, junto al editor.
Muestra la mezcla de salida del sistema (monitor de PipeWire/PulseAudio), no cada bucle. Sin dependencias; `ejecutar` se inyecta para poder probarlo."""
import os, shutil, subprocess

PROGRAMA = "scope-tui"

def _ejecutar(cmd):
    """-> (codigo, salida). Un programa que no existe o no responde cuenta como fallo."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        return p.returncode, (p.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""

def monitor(ejecutar=_ejecutar):
    """Fuente de audio a vigilar: el monitor de la salida por defecto, o None si no se puede saber (scope-tui usara la suya)."""
    rc, sal = ejecutar(["pactl", "get-default-sink"])
    return sal + ".monitor" if rc == 0 and sal else None

def abrir(env=None, ejecutar=_ejecutar, hay=shutil.which):
    """Abre scope-tui en un panel nuevo a la derecha sin quitar el foco al editor. -> (panel | None, mensaje)."""
    env = os.environ if env is None else env
    if not hay(PROGRAMA): return None, f"falta {PROGRAMA}: instalalo (en Arch: paru -S scope-tui)"
    fuente = monitor(ejecutar)
    cmd = [PROGRAMA, "pulse"] + ([fuente] if fuente else [])
    if env.get("ZELLIJ"):
        rc, sal = ejecutar(["zellij", "run", "-c", "-n", "osciloscopio", "-d", "right", "--", *cmd])
        if rc: return None, "no se pudo abrir el panel de zellij"
        ejecutar(["zellij", "action", "move-focus", "left"])               # el panel nuevo toma el foco: se devuelve al editor
        return ("zellij", sal), "osciloscopio abierto (q dentro de el, o Espacio o o, lo cierra)"
    if env.get("TMUX"):
        rc, sal = ejecutar(["tmux", "split-window", "-h", "-d", "-P", "-F", "#{pane_id}", *cmd])
        if rc or not sal: return None, "no se pudo abrir el panel de tmux"
        return ("tmux", sal), "osciloscopio abierto (q dentro de el, o Espacio o o, lo cierra)"
    return None, "el osciloscopio necesita zellij o tmux (abre scope-tui pulse en otro panel)"

def cerrar(panel, ejecutar=_ejecutar):
    """True si el panel existia y se cerro; False si ya no estaba (por ejemplo, lo cerraste con q)."""
    if not panel: return False
    como, id_ = panel
    cmd = ["zellij", "action", "close-pane", "--pane-id", id_] if como == "zellij" else ["tmux", "kill-pane", "-t", id_]
    return ejecutar(cmd)[0] == 0
