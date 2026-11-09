"""Editor de codigo para Sonic Pi en la terminal, solo teclado. Lanza su propio servidor de Sonic Pi (sin ventana).
Uso: ./editor.sh [archivo.rb]"""
import json, os, re, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, RichLog, Static, TextArea
from textual.widgets.text_area import Selection, TextAreaTheme
from rich.style import Style
import tree_sitter_ruby, tree_sitter
from cliente import SonicPi, procesos_sonicpi
import autocompletar

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "codigo")
os.makedirs(CARPETA, exist_ok=True)

PLANTILLA = """use_bpm 100

live_loop :bombo do
  sample :bd_haus, amp: 1
  sleep 1
end

live_loop :melodia do
  use_synth :prophet
  play scale(:e3, :minor_pentatonic).choose, release: 0.3, amp: 0.6
  sleep 0.25
end
"""

# Menu de la tecla lider (Espacio): letra -> (etiqueta, accion | submenu). Las acciones llaman a Editor.action_<nombre>.
MENU = {
    "r": ("ejecutar", "ejecutar"), "e": ("bloque", "ejecutar_bloque"), "l": ("linea", "ejecutar_linea"),
    "s": ("parar", "parar"), "w": ("guardar", "guardar"), "n": ("nuevo", "nuevo"),
    "f": ("archivo", {"f": ("abrir", "abrir"), "n": ("nuevo", "nuevo"), "s": ("guardar", "guardar")}),
    "v": ("volumen", {"u": ("subir", "volumen_subir"), "d": ("bajar", "volumen_bajar")}),
    "o": ("opciones", {"l": ("mostrar/ocultar log", "log")}),
    "t": ("tema", "tema"), "p": ("paleta", "paleta"), "?": ("ayuda", "ayuda_completa"), "q": ("salir", "salir"),
}
COMPLETA = [
    "NORMAL   h j k l  w b  0 ^ $  gg G  { }  (con numero: 5j, 3w)",
    "         i a I A o O insertar · x borra letra · dd/dw/d$/D borra · yy/yw copia · cc/cw/C cambia · p P pega",
    "         u deshacer · U rehacer · >> << sangrar · v / V visual (elige y luego Espacio r)",
    "ESPACIO  r ejecutar todo (o la seleccion) · e bloque (hasta linea en blanco) · l linea · s parar",
    "         w guardar · n nuevo · f f abrir · v u / v d volumen · o l log (mostrar/ocultar) · t tema · p paleta · q salir",
]
FLECHAS = {"left": "h", "right": "l", "up": "k", "down": "j", "home": "0", "end": "$"}

_LENG = tree_sitter.Language(tree_sitter_ruby.language())
_CONSULTA = open(os.path.join(os.path.dirname(tree_sitter_ruby.__file__), "queries", "highlights.scm")).read()

def _paleta(bg, panel, barra, fg, dim, acento, borde, linea, sel, modos, ok, err, aviso, info, syn):
    return dict(bg=bg, panel=panel, barra=barra, fg=fg, dim=dim, acento=acento, borde=borde, linea=linea, sel=sel,
                modos=modos, ok=ok, err=err, aviso=aviso, info=info, syn=syn)

def _sintaxis(kw, st, sym, const, num, com, fn, prop, op):
    return {"keyword": (kw, True), "string": (st, False), "string.special.symbol": (sym, False), "constant": (const, False),
            "number": (num, False), "comment": (com, False), "function.method": (fn, False), "function.method.call": (fn, False),
            "function": (fn, False), "property": (prop, False), "operator": (op, False), "constant.builtin": (num, False), "type": (const, False)}

# Cada tema: fondo, paneles, colores de modo (normal, insertar, visual), colores del log y de la sintaxis.
TEMAS = {
    "sonicpi": _paleta("#14161c", "#1a1d27", "#232838", "#d8dee9", "#7f8aa3", "#f5c542", "#2a2f3d", "#1d212b", "#3a4766",
                       ("#f5c542", "#a6e3a1", "#cba6f7"), "#a6e3a1", "#f38ba8", "#f9e2af", "#89dceb",
                       _sintaxis("#ff7ab2", "#a6e3a1", "#f5c542", "#f5c542", "#fab387", "#6c7086", "#89dceb", "#cba6f7", "#94e2d5")),
    "matrix": _paleta("#000000", "#000000", "#031a08", "#00ff41", "#00a62b", "#39ff14", "#0a4d16", "#04140a", "#0b4d1e",
                      ("#39ff14", "#00ffaa", "#b6ff00"), "#00ff41", "#ff1744", "#d6ff00", "#00e5ff",
                      _sintaxis("#39ff14", "#00ffd5", "#00e5ff", "#00e5ff", "#fff200", "#0a7a28", "#00ff41", "#b6ff00", "#00c853")),
    "neon": _paleta("#000000", "#050508", "#120a1f", "#e6e6ff", "#7a7aa8", "#ff2bd6", "#2b1055", "#0d0618", "#3a0f66",
                    ("#ff2bd6", "#00fff2", "#fff200"), "#00ff9c", "#ff2d55", "#fff200", "#00d0ff",
                    _sintaxis("#ff2bd6", "#00ff9c", "#fff200", "#00d0ff", "#ff9100", "#5a4a8a", "#00fff2", "#b388ff", "#ff2bd6")),
    "ambar": _paleta("#000000", "#0a0600", "#1f1200", "#ffb000", "#8a5f00", "#ffd24a", "#4a3000", "#140c00", "#4a3200",
                     ("#ffd24a", "#ffb000", "#ff7a00"), "#ffd24a", "#ff4000", "#ffe08a", "#ffb000",
                     _sintaxis("#ff7a00", "#ffe08a", "#ffd24a", "#ffd24a", "#ff9a30", "#7a5200", "#ffc940", "#ffa000", "#ff7a00")),
}
TEMAS["matrix"]["marco"] = "#39ff14"        # borde de la pantalla (solo los temas que lo definen)
MODOS = {"normal": "NORMAL", "insertar": "INSERTAR", "visual": "VISUAL"}
ARCHIVO_TEMA = os.path.join(RAIZ, "tema.json")

def _tema_textarea(nombre, T, modo):
    cur = T["modos"][list(MODOS).index(modo)]
    syn = {k: Style(color=c, bold=b, italic=(k == "comment")) for k, (c, b) in T["syn"].items()}
    syn["variable"] = Style(color=T["fg"]); syn["embedded"] = Style(color=T["fg"])
    # normal/visual: bloque. insertar: solo una raya fina bajo la letra (sin relleno)
    cursor = Style(color=cur, bgcolor=T["bg"], underline=True, bold=True) if modo == "insertar" else Style(color=T["bg"], bgcolor=cur)
    return TextAreaTheme(name=f"{nombre}-{modo}", base_style=Style(color=T["fg"], bgcolor=T["bg"]),
                         cursor_style=cursor, cursor_line_style=Style(bgcolor=T["linea"]),
                         selection_style=Style(bgcolor=T["sel"]), gutter_style=Style(color=T["dim"], bgcolor=T["bg"]), syntax_styles=syn)

def cargar_config():
    try: return json.load(open(ARCHIVO_TEMA))
    except Exception: return {}

def _cls(ch):
    return 0 if ch.isspace() else (1 if ch.isalnum() or ch == "_" else 2)

def _sig_palabra(t, i):
    n = len(t)
    if i >= n: return n
    c = _cls(t[i])
    while i < n and c != 0 and _cls(t[i]) == c: i += 1
    while i < n and _cls(t[i]) == 0: i += 1
    return i

def _ant_palabra(t, i):
    i = max(0, i - 1)
    while i > 0 and _cls(t[i]) == 0: i -= 1
    c = _cls(t[i])
    while i > 0 and _cls(t[i - 1]) == c: i -= 1
    return i

def sangria_tras(antes):
    """Sangria de la linea siguiente: la de `antes` mas 2 espacios tras `do`, `|x|`, `{`..."""
    sangria = re.match(r"\s*", antes).group(0)
    if re.search(r"(\bdo(\s*\|[^|]*\|)?|\{(\s*\|[^|]*\|)?|\bthen|\bif\b.*|\belse|\bbegin)\s*$", antes):
        sangria += "  "
    return sangria


class Codigo(TextArea):
    """Editor modal (normal / insertar / visual) con tecla lider Espacio. Sin Ctrl ni F: solo letras, Espacio y Esc."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.modo = "normal"; self.pend = ""; self.cuenta = ""
        self.lider = None; self.ruta_lider = ""
        self.reg = ("", False); self.ancla = (0, 0)
        self.sugs = []; self.sug_i = 0; self.sug_pref = ""; self._sin_sugs = False; self.parada = None

    # ---------- utilidades ----------
    def _L(self, f): return len(self.document.get_line(f))
    def _ult(self): return self.document.line_count - 1
    def _fin_normal(self, f): return max(self._L(f) - 1, 0)
    def _no_blanco(self, f):
        l = self.document.get_line(f); return (f, len(l) - len(l.lstrip()))
    def _off(self, loc): return self.document.get_index_from_location(loc)
    def _loc(self, i): return self.document.get_location_from_index(i)

    def poner_modo(self, modo):
        self.modo = modo; self.pend = ""; self.cuenta = ""; self.lider = None; self.ruta_lider = ""
        self.parada = None; self._sin_sugs = False; self._cerrar_sugs()
        self.read_only = modo != "insertar"
        cur = self.cursor_location
        if modo == "visual": self.ancla = cur
        self.selection = Selection(cur, cur)
        self.theme = f"{self.app.tema}-{modo}"
        self.app.modo_cambiado()

    def _ir(self, loc):
        """Mueve el cursor; en visual extiende la seleccion desde el ancla."""
        if self.modo == "visual":
            self.selection = Selection(self.ancla, loc)
        else:
            self.move_cursor(loc)

    # ---------- teclas ----------
    async def _on_key(self, event):
        k = event.key
        if self.modo == "insertar":
            if self.sugs and k in ("down", "up"):                       # elegir sugerencia
                event.stop(); event.prevent_default()
                self.sug_i = (self.sug_i + (1 if k == "down" else -1)) % len(self.sugs); self._pintar_sugs(); return
            if k == "tab":
                if self.sugs:                                           # Tab acepta la sugerencia
                    event.stop(); event.prevent_default(); self._aceptar(); return
                if self.parada and self.parada[0] <= self._ult():       # o salta a la siguiente parada de la plantilla
                    event.stop(); event.prevent_default(); self.move_cursor(self.parada); self.parada = None; return
            self._sin_sugs = False
            if k == "escape":
                event.stop(); event.prevent_default()
                f, c = self.cursor_location
                self.poner_modo("normal")
                if c > 0: self.move_cursor((f, c - 1))
                return
            if k == "enter":
                fila, col = self.cursor_location
                event.stop(); event.prevent_default()
                self.insert("\n" + sangria_tras(self.document.get_line(fila)[:col]))
                return
            if k == "backspace" and self.selection.is_empty:      # borra de 2 en 2 dentro de la sangria
                fila, col = self.cursor_location
                antes = self.document.get_line(fila)[:col]
                if col >= 2 and antes.strip() == "" and col % 2 == 0:
                    event.stop(); event.prevent_default()
                    self.delete((fila, col - 2), (fila, col))
                    return
            await super()._on_key(event)
            return
        # normal / visual: ninguna tecla escribe texto
        if k == "escape":
            event.stop(); event.prevent_default(); self._cancelar(); return
        ch = FLECHAS.get(k) or (event.character if event.is_printable else None)
        if ch is None:
            if k in ("enter", "backspace", "tab", "delete"):
                event.stop(); event.prevent_default()
            else:
                await super()._on_key(event)
            return
        event.stop(); event.prevent_default()
        self._normal(ch)

    # ---------- autocompletado ----------
    def on_text_area_selection_changed(self, event):
        if self.modo == "insertar": self._sugerir()

    def _sugerir(self):
        if self._sin_sugs or not self.selection.is_empty:
            self._cerrar_sugs(); return
        f, c = self.cursor_location
        pref, lista = autocompletar.candidatos(self.document.get_line(f)[:c])
        if not lista:
            self._cerrar_sugs(); return
        previo = self.sugs[self.sug_i].nombre if self.sugs else None
        self.sugs = lista; self.sug_pref = pref
        self.sug_i = next((i for i, x in enumerate(lista) if x.nombre == previo), 0)
        self._pintar_sugs()

    def _pintar_sugs(self):
        w = self.app.query_one("#sugs", Static); T = TEMAS[self.app.tema]
        n = len(self.sugs); filas = min(8, n); ini = max(0, min(self.sug_i - 3, n - filas))
        vis = self.sugs[ini:ini + filas]
        anch = max(len(c.nombre) for c in vis) + 1; tw = max(len(c.tipo) for c in vis)
        texto = Text()
        for i, c in enumerate(vis):
            sel = ini + i == self.sug_i
            if i: texto.append("\n")
            texto.append(f" {c.nombre:<{anch}}", style=f"bold {T['bg']} on {T['acento']}" if sel else T["fg"])
            texto.append(f" {c.tipo:<{tw}} ", style=f"{T['bg']} on {T['acento']}" if sel else T["dim"])
        ancho = anch + tw + 3
        if n > filas:                                               # contador solo si hay mas de las que caben
            texto.append("\n" + f" {self.sug_i + 1}/{n}".ljust(ancho), style=T["dim"])
        alto = filas + (1 if n > filas else 0)
        off = self.cursor_screen_offset; tam = self.app.size
        bw = 1 if self.app.screen_stack[0].styles.border_top[0] else 0          # el marco de la pantalla desplaza el origen del popup
        x = max(0, min(off.x - len(self.sug_pref) - 1 - bw, tam.width - ancho - 2 * bw))
        y = off.y + 1 - bw
        if y + alto > tam.height - 1 - 2 * bw: y = max(0, off.y - alto - bw)
        w.styles.offset = (x, y); w.styles.width = ancho; w.styles.height = alto
        w.update(texto); w.display = True

    def _cerrar_sugs(self):
        self.sugs = []
        try: self.app.query_one("#sugs").display = False
        except Exception: pass

    def _aceptar(self):
        c = self.sugs[self.sug_i]; pref = self.sug_pref
        f, col = self.cursor_location; ini = (f, col - len(pref))
        self._sin_sugs = True; self._cerrar_sugs()
        if pref: self.delete(ini, (f, col))
        if c.snippet: self._expandir(c.snippet, ini)
        else:
            self.insert(c.ins, ini); self.move_cursor((f, ini[1] + len(c.ins)))

    def _expandir(self, clave, ini):
        texto, sel, salto = autocompletar.SNIPPETS[clave]
        f = ini[0]; sangria = re.match(r"\s*", self.document.get_line(f)).group(0)
        lineas = texto.split("\n")
        self.insert(("\n" + sangria).join(lineas), ini)
        if sel:
            a = (f, ini[1] + lineas[0].index(sel))
            self.selection = Selection(a, (f, a[1] + len(sel)))
            self.parada = (f + salto, len(sangria) + 2) if salto else None
        else:
            self.move_cursor((f + salto, len(sangria) + 2) if salto else (f, ini[1] + len(texto)))

    def _cancelar(self):
        if self.modo == "visual": self.poner_modo("normal")
        else:
            self.pend = ""; self.cuenta = ""; self.lider = None; self.ruta_lider = ""
            self.app.modo_cambiado()

    def _normal(self, ch):
        app = self.app
        if self.lider is not None:                                  # menu de la tecla lider
            entrada = self.lider.get(ch)
            if entrada is None:
                self.lider = None; self.ruta_lider = ""; app.modo_cambiado()
                app._log(f"sin atajo: Espacio {ch}", "yellow"); return
            _, destino = entrada
            if isinstance(destino, dict):
                self.lider = destino; self.ruta_lider += " " + ch; app.modo_cambiado(); return
            self.lider = None; self.ruta_lider = ""
            app.modo_cambiado()
            app.ejecutar_nombre(destino)
            return
        if ch == " " and not self.pend:
            self.lider = MENU; self.ruta_lider = ""; app.modo_cambiado(); return
        if ch.isdigit() and (ch != "0" or self.cuenta):
            self.cuenta += ch; app.modo_cambiado(); return
        cnt = self.cuenta; n = int(cnt or 1); pend = self.pend
        self.cuenta = ""; self.pend = ""
        if pend == "g":
            if ch == "g": self._ir(self._no_blanco(0 if not cnt else min(n - 1, self._ult())))
        elif pend in ("d", "y", "c"):
            self._operador(pend, ch, n, cnt)
        elif pend in (">", "<"):
            if ch == pend: self._sangrar(pend, n)
        elif self.modo == "visual":
            self._visual(ch, n, cnt)
        else:
            self._comando(ch, n, cnt)
        app.modo_cambiado()

    def _destino(self, ch, n, cnt):
        f, c = self.cursor_location; u = self._ult()
        if ch == "h": return (f, max(0, c - n))
        if ch == "l": return (f, min(self._fin_normal(f) if self.modo != "visual" else self._L(f), c + n))
        if ch in "jk":
            g = min(u, f + n) if ch == "j" else max(0, f - n)
            return (g, min(c, self._fin_normal(g)))
        if ch == "0": return (f, 0)
        if ch == "^": return self._no_blanco(f)
        if ch == "$": return (f, self._fin_normal(f) if self.modo != "visual" else self._L(f))
        if ch == "G": return self._no_blanco(u if not cnt else min(n - 1, u))
        if ch in "wb":
            t = self.text; i = self._off((f, c))
            for _ in range(n): i = _sig_palabra(t, i) if ch == "w" else _ant_palabra(t, i)
            return self._loc(min(i, len(t)))
        if ch in "{}":
            g = f
            for _ in range(n):
                g = g + 1 if ch == "}" else g - 1
                while 0 <= g <= u and self.document.get_line(g).strip(): g = g + 1 if ch == "}" else g - 1
                g = max(0, min(u, g))
            return (g, 0)
        return None

    def _comando(self, ch, n, cnt):
        f, c = self.cursor_location; u = self._ult(); L = self._L(f)
        d = self._destino(ch, n, cnt)
        if d is not None: self.move_cursor(d); return
        if ch in ("g", "d", "y", "c", ">", "<"): self.pend = ch; self.cuenta = cnt; return
        if ch == "i": self.poner_modo("insertar")
        elif ch == "a": self.move_cursor((f, min(L, c + 1))); self.poner_modo("insertar")
        elif ch == "A": self.move_cursor((f, L)); self.poner_modo("insertar")
        elif ch == "I": self.move_cursor(self._no_blanco(f)); self.poner_modo("insertar")
        elif ch == "o":
            self.insert("\n" + sangria_tras(self.document.get_line(f)), (f, L)); self.move_cursor((f + 1, 10 ** 6))
            self.poner_modo("insertar")
        elif ch == "O":
            sg = re.match(r"\s*", self.document.get_line(f)).group(0)
            self.insert(sg + "\n", (f, 0)); self.move_cursor((f, len(sg))); self.poner_modo("insertar")
        elif ch == "x":
            if L: self.reg = (self.get_text_range((f, c), (f, min(L, c + n))), False); self.delete((f, c), (f, min(L, c + n))); self.move_cursor((f, min(c, self._fin_normal(f))))
        elif ch in "DC":
            self.reg = (self.get_text_range((f, c), (f, L)), False); self.delete((f, c), (f, L))
            if ch == "C": self.poner_modo("insertar")
            else: self.move_cursor((f, self._fin_normal(f)))
        elif ch == "u": self.undo()
        elif ch == "U": self.redo()
        elif ch in "pP": self._pegar(ch == "P", n)
        elif ch == "v": self.poner_modo("visual")
        elif ch == "V":
            self.poner_modo("visual"); self.ancla = (f, 0); self.selection = Selection((f, 0), (f, L))
        elif ch == "?": self.app.ayuda_completa()

    def _visual(self, ch, n, cnt):
        d = self._destino(ch, n, cnt)
        if d is not None: self._ir(d); return
        if ch in ("g", ">", "<"): self.pend = ch; self.cuenta = cnt; return
        sel = self.selected_text
        if ch in ("v", "V"): self.poner_modo("normal")
        elif ch in ("y", "d", "x", "c") and sel:
            ini = min(self.selection.start, self.selection.end); fin = max(self.selection.start, self.selection.end)
            self.reg = (sel, False)
            self.poner_modo("normal")
            if ch != "y":
                self.delete(ini, fin)
                if ch == "c": self.poner_modo("insertar")
            self.move_cursor(ini)

    def _operador(self, op, ch, n, cnt):
        f, c = self.cursor_location; u = self._ult()
        if ch == op:                                              # dd yy cc
            self._por_lineas(op, f, min(u, f + n - 1)); return
        if ch in "jkG" or ch == "g":
            d = self._destino(ch, n, cnt) if ch != "g" else None
            if d is None: return
            self._por_lineas(op, min(f, d[0]), max(f, d[0])); return
        d = self._destino(ch, n, cnt)
        if d is None: return
        if op == "c" and ch == "w":                               # cw cambia solo la palabra (como Vim)
            t = self.text; i = self._off((f, c)); cl = _cls(t[i]) if i < len(t) else 0
            while cl and i < len(t) and _cls(t[i]) == cl: i += 1
            d = self._loc(i) if cl else d
        a, b = sorted(((f, c), d))
        if ch == "w" and b[0] != f: b = (f, self._L(f)) if a == (f, c) else b
        if ch == "$": b = (f, self._L(f))
        if ch == "l": b = (f, min(self._L(f), c + n))
        self.reg = (self.get_text_range(a, b), False)
        if op != "y": self.delete(a, b)
        self.move_cursor(a)
        if op == "c": self.poner_modo("insertar")

    def _por_lineas(self, op, f1, f2):
        u = self._ult()
        self.reg = ("\n".join(self.document.get_line(i) for i in range(f1, f2 + 1)), True)
        if op == "y":
            self.move_cursor((f1, self.cursor_location[1])); return
        if op == "c":
            sg = re.match(r"\s*", self.document.get_line(f1)).group(0)
            self.delete((f1, 0), (f2, self._L(f2))); self.insert(sg, (f1, 0)); self.move_cursor((f1, len(sg)))
            self.poner_modo("insertar"); return
        if f2 < u: self.delete((f1, 0), (f2 + 1, 0))
        elif f1 > 0: self.delete((f1 - 1, self._L(f1 - 1)), (f2, self._L(f2)))
        else: self.delete((0, 0), (f2, self._L(f2)))
        self.move_cursor(self._no_blanco(min(f1, self._ult())))

    def _pegar(self, antes, n):
        texto, lineas = self.reg
        if not texto: return
        f, c = self.cursor_location
        if lineas:
            if antes: self.insert((texto + "\n") * n, (f, 0)); self.move_cursor(self._no_blanco(f))
            else: self.insert(("\n" + texto) * n, (f, self._L(f))); self.move_cursor(self._no_blanco(f + 1))
        else:
            p = c if antes or self._L(f) == 0 else c + 1
            self.insert(texto * n, (f, p)); self.move_cursor((f, max(0, p + len(texto) * n - 1)))

    def _sangrar(self, signo, n):
        f, _ = self.cursor_location
        for g in range(f, min(self._ult(), f + n - 1) + 1):
            l = self.document.get_line(g)
            if signo == ">": self.insert("  ", (g, 0))
            else:
                q = min(2, len(l) - len(l.lstrip()))
                if q: self.delete((g, 0), (g, q))


class Selector(ModalScreen):
    BINDINGS = [Binding("escape", "cancelar", "cancelar"), Binding("j", "bajar", "bajar"), Binding("k", "subir", "subir"),
                Binding("q", "cancelar", "cancelar")]
    def action_bajar(self): self.query_one("#lista").action_cursor_down()
    def action_subir(self): self.query_one("#lista").action_cursor_up()
    def __init__(self, archivos, titulo="Abrir archivo  (j/k mueve, Enter abre, Esc cancela)", al_mover=None, inicial=None):
        super().__init__(); self.archivos = archivos; self.titulo = titulo; self.al_mover = al_mover; self.inicial = inicial
    def on_option_list_option_highlighted(self, e):
        if self.al_mover: self.al_mover(self.archivos[e.option_index])
    def compose(self):
        with Vertical(id="caja"):
            yield Label(self.titulo)
            yield OptionList(*self.archivos, id="lista")
    def on_mount(self):
        lista = self.query_one("#lista"); lista.focus()
        if self.inicial in self.archivos: lista.highlighted = self.archivos.index(self.inicial)
    def on_option_list_option_selected(self, e): self.dismiss(self.archivos[e.option_index])
    def action_cancelar(self): self.dismiss(None)


class Nombre(ModalScreen):
    BINDINGS = [Binding("escape", "cancelar", "cancelar")]
    def compose(self):
        with Vertical(id="caja"):
            yield Label("Guardar como (Enter confirma, Esc cancela)")
            yield Input(placeholder="nombre.rb", id="nombre")
    def on_mount(self): self.query_one("#nombre").focus()
    def on_input_submitted(self, e): self.dismiss(e.value.strip() or None)
    def action_cancelar(self): self.dismiss(None)


class Editor(App):
    CSS = """
    Screen { background: $bg; layers: base overlay; }
    #sugs { layer: overlay; position: absolute; display: none; background: $panel; color: $fg; border: none; padding: 0; }
    #cod { height: 1fr; border: none; background: $bg; }
    #log { display: none; height: 9; background: $bg; border-top: solid $borde; padding: 0 1; }
    #log.visible { display: block; }
    #barra { height: 1; background: $barra; color: $fg; padding: 0 1; }
    #ayuda { display: none; height: auto; min-height: 1; background: $panel; color: $dim; padding: 0 1; }
    Selector, Nombre { align: center middle; }
    #caja { width: 60; height: auto; max-height: 24; border: round $acento; background: $panel; color: $fg; padding: 1 2; }
    #lista { height: auto; max-height: 16; background: $panel; color: $fg; }
    """
    def get_css_variables(self):
        T = TEMAS[self.tema]
        return {**super().get_css_variables(), **{k: T[k] for k in ("bg", "panel", "barra", "fg", "dim", "acento", "borde")}}

    AUTO_FOCUS = "#cod"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [Binding("ctrl+q", "nada", show=False, priority=True)]     # Ctrl+Q de Textual cerraba la app: desactivado
    def action_nada(self): pass

    def __init__(self, archivo=None, con_servidor=True):
        cfg = cargar_config()
        self.tema = cfg.get("tema") if cfg.get("tema") in TEMAS else "sonicpi"
        self.log_visible = bool(cfg.get("log", False))
        self.ultimo_archivo = cfg.get("ultimo")
        self.ultimo = ("", "dim")
        super().__init__()
        self.con_servidor = con_servidor
        self.sp = None
        self.listo = False
        self.volumen = 0.3
        self.ruta = None
        self.sucio = False
        self._base = ""                      # texto al cargar/guardar: hay cambios solo si el texto difiere
        self._confirma_salir = False
        self._inicial = archivo

    def compose(self) -> ComposeResult:
        yield Codigo.code_editor("", language=None, id="cod", tab_behavior="indent", soft_wrap=False)
        yield RichLog(id="log", wrap=True, markup=False, highlight=False, auto_scroll=True)
        yield Static("", id="barra")
        yield Static("", id="ayuda")
        yield Static("", id="sugs")

    def on_mount(self):
        cod = self.query_one("#cod", Codigo)
        cod.can_focus = True
        cod.register_language("ruby", _LENG, _CONSULTA)
        for n, T in TEMAS.items():
            for m in MODOS: cod.register_theme(_tema_textarea(n, T, m))
        cod.language = "ruby"
        self.query_one("#log").can_focus = False
        previo = self.ultimo_archivo and os.path.join(RAIZ, self.ultimo_archivo)
        if self._inicial and os.path.exists(self._inicial):
            self._abrir(self._inicial)
        elif previo and os.path.exists(previo):                       # sin argumento: reabre el ultimo archivo
            self._abrir(previo)
        else:
            self._poner(PLANTILLA); self.sucio = False
        self.query_one("#log").set_class(self.log_visible, "visible")
        self._marco()
        cod.poner_modo("normal")
        self._barra()
        if self.con_servidor:
            self._log("Arrancando Sonic Pi (unos segundos)...", "dim")
            self._arrancar()
        else:
            self._log("(modo sin servidor)", "dim")

    # ---------- servidor ----------
    @work(thread=True)
    def _arrancar(self):
        viv = procesos_sonicpi()
        if viv:
            self.call_from_thread(self._log, "Hay Sonic Pi en marcha (cierralo antes): " + viv[0], "red")
            return
        sp = SonicPi(al_mensaje=lambda t, x: self.call_from_thread(self._mensaje, t, x))
        try:
            sp.iniciar()
        except Exception as e:
            self.call_from_thread(self._log, f"No arranco: {e}", "red"); return
        sp.volumen(self.volumen)
        self.sp = sp; self.listo = True
        autocompletar.usar_version(sp.version)
        self.call_from_thread(self._log, f"Sonic Pi {sp.version}.x listo. Espacio r para ejecutar.", "green")
        self.call_from_thread(self._barra)

    def _mensaje(self, tipo, texto):
        texto = texto.strip().strip('"')
        if tipo == "error":
            self._log(texto, "red"); self._saltar(texto)
        elif tipo == "sintaxis": self._log(texto, "red"); self._saltar(texto)
        elif tipo == "aviso": self._log(texto, "yellow")
        elif texto: self._log(texto, "white")

    def _saltar(self, texto):                       # lleva el cursor a la linea del error si se ejecuto todo el codigo
        m = re.match(r"linea (\d+)", texto)
        if m and not self._ejecutando_seleccion:
            self.query_one("#cod").move_cursor((max(0, int(m.group(1)) - 1), 0))

    _ejecutando_seleccion = False

    # ---------- acciones ----------
    def ejecutar_nombre(self, nombre):
        if nombre != "salir": self._confirma_salir = False
        getattr(self, "action_" + nombre)()

    def _correr(self, texto, que, parcial):
        if not self.listo:
            self._log("El servidor aun no esta listo.", "yellow"); return
        if not texto.strip():
            self._log("Nada que ejecutar.", "yellow"); return
        self._ejecutando_seleccion = parcial
        self.sp.ejecutar(texto)
        self._log("> ejecutando " + que, "cyan")

    def action_ejecutar(self):
        cod = self.query_one("#cod", Codigo)
        sel = cod.selected_text
        if sel.strip(): self._correr(sel, "la seleccion", True)
        else: self._correr(cod.text, "todo", False)
        if cod.modo == "visual": cod.poner_modo("normal")

    def action_ejecutar_linea(self):
        cod = self.query_one("#cod", Codigo)
        self._correr(cod.document.get_line(cod.cursor_location[0]), "la linea", True)

    def action_ejecutar_bloque(self):
        cod = self.query_one("#cod", Codigo)
        f = cod.cursor_location[0]; doc = cod.document; u = doc.line_count - 1
        a = f
        while a > 0 and doc.get_line(a - 1).strip(): a -= 1
        b = f
        while b < u and doc.get_line(b + 1).strip(): b += 1
        self._correr("\n".join(doc.get_line(i) for i in range(a, b + 1)), f"el bloque (lineas {a + 1}-{b + 1})", True)

    def action_parar(self):
        if self.listo:
            self.sp.parar(); self._log("> parado", "cyan")

    def action_volumen_subir(self): self._volumen(0.05)
    def action_volumen_bajar(self): self._volumen(-0.05)

    def _volumen(self, d: float):
        self.volumen = min(1.0, max(0.0, round(self.volumen + float(d), 2)))
        if self.listo: self.sp.volumen(self.volumen)
        self._barra()

    def action_ayuda_completa(self):
        self._mostrar_log(True)
        for l in COMPLETA: self._log(l, "cyan")

    def action_tema(self):
        previo = self.tema
        def elegido(n):
            self._poner_tema(n or previo)
            if n:
                self._guardar_config()
                self._log(f"tema: {n}", "ok")
        self.push_screen(Selector(list(TEMAS), "Tema  (j/k mueve y previsualiza, Enter elige, Esc cancela)", al_mover=self._poner_tema, inicial=previo), elegido)

    def _marco(self):
        base = self.screen_stack[0]
        c = TEMAS[self.tema].get("marco")
        base.styles.border = ("round", c) if c else ("none", "black")

    def _poner_tema(self, nombre):
        self.tema = nombre
        self.refresh_css()
        self._marco()
        cod = self.query_one("#cod", Codigo)
        cod.theme = f"{nombre}-{cod.modo}"
        self.query_one("#log", RichLog).styles.background = TEMAS[nombre]["bg"]
        self.modo_cambiado()

    def action_paleta(self):
        mapa = {}
        def recorre(menu, ruta):
            for k, (et, dest) in menu.items():
                if isinstance(dest, dict): recorre(dest, ruta + k + " ")
                elif dest != "paleta": mapa[f"Espacio {ruta}{k:<2} {et}"] = dest
        recorre(MENU, "")
        etiquetas = list(mapa)
        self.push_screen(Selector(etiquetas, "Paleta  (j/k mueve, Enter ejecuta, Esc cancela)"),
                         lambda e: e and self.ejecutar_nombre(mapa[e]))

    def action_log(self):
        self._mostrar_log(not self.log_visible); self._guardar_config()

    def _mostrar_log(self, v):
        self.log_visible = v
        self.query_one("#log").set_class(v, "visible")
        self._barra()

    def _guardar_config(self):
        try: json.dump({"tema": self.tema, "log": self.log_visible, "ultimo": self.ultimo_archivo}, open(ARCHIVO_TEMA, "w"))
        except OSError as e: self._log(f"no se pudo guardar la configuracion: {e}", "red")

    def action_guardar(self):
        if self.ruta: self._guardar(self.ruta)
        else: self.push_screen(Nombre(), self._nombre_elegido)

    def _nombre_elegido(self, nombre):
        if nombre:
            if not nombre.endswith(".rb"): nombre += ".rb"
            self._guardar(os.path.join(CARPETA, os.path.basename(nombre)))

    def _guardar(self, ruta):
        with open(ruta, "w") as f: f.write(self.query_one("#cod").text)
        self.ruta = ruta; self._base = self.query_one("#cod").text; self.sucio = False
        self.ultimo_archivo = os.path.relpath(ruta, RAIZ); self._guardar_config()
        self._log(f"guardado: {os.path.relpath(ruta, RAIZ)}", "green"); self._barra()

    def action_abrir(self):
        archivos = sorted(f for f in os.listdir(CARPETA) if f.endswith(".rb"))
        if not archivos:
            self._log("No hay archivos en codigo/ todavia (guarda uno con Espacio w).", "yellow"); return
        self.push_screen(Selector(archivos), lambda f: f and self._abrir(os.path.join(CARPETA, f)))

    def action_nuevo(self):
        self.ruta = None; self._poner(""); self.sucio = False; self._barra()
        self.query_one("#cod", Codigo).poner_modo("insertar")

    def _abrir(self, ruta):
        self.ruta = ruta
        self._poner(open(ruta).read()); self.sucio = False
        self.ultimo_archivo = os.path.relpath(ruta, RAIZ); self._guardar_config()
        self._log(f"abierto: {os.path.relpath(ruta, RAIZ)}", "green"); self._barra()

    def _poner(self, texto):
        cod = self.query_one("#cod", Codigo)
        cod.load_text(texto)
        self._base = cod.text; self.sucio = False
        cod.move_cursor((0, 0))
        if cod.modo != "normal": cod.poner_modo("normal")

    def on_text_area_changed(self, e):
        sucio = self.query_one("#cod").text != self._base
        if sucio != self.sucio:
            self.sucio = sucio; self._barra()

    def action_salir(self):
        if self.sucio and not self._confirma_salir:
            self._confirma_salir = True
            self._log("Cambios sin guardar: Espacio w guarda · Espacio q otra vez sale sin guardar.", "yellow"); return
        if self.sp:
            threading.Thread(target=self.sp.cerrar, daemon=True).start()
            import time; time.sleep(0.5)
        self.exit()

    # ---------- interfaz ----------
    def _log(self, texto, color="white"):
        T = TEMAS[self.tema]
        col = {"red": T["err"], "yellow": T["aviso"], "green": T["ok"], "ok": T["ok"], "cyan": T["info"], "white": T["fg"], "dim": T["dim"]}.get(color, color)
        self.query_one("#log", RichLog).write(Text(texto, style=col))
        self.ultimo = (texto.strip().splitlines()[0] if texto.strip() else "", col)
        if color == "red" and not self.log_visible: self._mostrar_log(True)      # un error siempre se ve
        else: self._barra()

    def modo_cambiado(self):
        self._barra()
        cod = self.query_one("#cod", Codigo)
        if cod.lider is not None:
            sub = " ".join(f"{k} {et}{'+' if isinstance(d, dict) else ''}" for k, (et, d) in cod.lider.items())
            self.query_one("#ayuda", Static).update(Text.assemble(("Espacio" + cod.ruta_lider + "  ", f"bold {TEMAS[self.tema]['acento']}"), sub))
        self.query_one("#ayuda").display = cod.lider is not None

    def _barra(self):
        nombre = os.path.basename(self.ruta) if self.ruta else "(sin nombre)"
        estado = "listo" if self.listo else ("sin servidor" if not self.con_servidor else "arrancando...")
        n = int(self.volumen * 20)
        cod = self.query_one("#cod", Codigo)
        T = TEMAS[self.tema]; etiqueta = MODOS[cod.modo]; color = T["modos"][list(MODOS).index(cod.modo)]
        pend = (cod.cuenta + cod.pend + (" Espacio" + cod.ruta_lider if cod.lider is not None else "")).strip()
        base = Text.assemble((f" {etiqueta} ", f"bold {T['bg']} on {color}"), (f" {pend} " if pend else " ", f"bold {color}"),
                          (f"{nombre}{' *' if self.sucio else ''}", f"bold {T['acento']}"), "   |   ", f"servidor: {estado}", "   |   ",
                          "vol ", ("█" * n, T["ok"]), ("░" * (20 - n), T["borde"]), f" {int(self.volumen * 100)}%")
        if not self.log_visible and self.ultimo[0]:                   # con el log oculto, el ultimo mensaje va en la barra
            libre = self.size.width - base.cell_len - 6
            if libre > 8:
                msg = self.ultimo[0] if len(self.ultimo[0]) <= libre else self.ultimo[0][:libre - 1] + "…"
                base.append("   |   ", style=T["dim"]); base.append(msg, style=self.ultimo[1])
        self.query_one("#barra", Static).update(base)


if __name__ == "__main__":
    app = Editor(sys.argv[1] if len(sys.argv) > 1 else None)
    try:
        app.run()
    finally:
        if app.sp: app.sp.cerrar()
