"""Autocompletado de Ruby y Sonic Pi (logica pura, sin interfaz). candidatos(texto_antes_del_cursor) -> (prefijo, [Cand])."""
import os, re, sys
from collections import namedtuple
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_datos as D

VERSION = 4          # version de Sonic Pi conectada: con 5 tambien se ofrecen los nombres nuevos de la 5.0 (sp_datos.*_V5)

def usar_version(v):
    global VERSION
    VERSION = int(v)

def _dat(nombre):
    """Nombres de sp_datos (base 4.x) mas, si hay Sonic Pi 5, los que solo existen en la 5.0."""
    return getattr(D, nombre) + (getattr(D, nombre + "_V5", []) if VERSION >= 5 else [])

Cand = namedtuple("Cand", "nombre tipo ins snippet")     # ins: texto que se inserta; snippet: clave de SNIPPETS o None

RUBY = ["alias", "and", "begin", "break", "case", "class", "def", "do", "else", "elsif", "end", "ensure", "false", "for", "if",
        "in", "module", "next", "nil", "not", "or", "redo", "rescue", "retry", "return", "self", "then", "true", "undef",
        "unless", "until", "when", "while", "yield", "puts", "print", "each", "each_with_index", "map", "select", "reject",
        "times", "upto", "downto", "step", "reverse", "shuffle", "sort", "first", "last", "length", "include?", "zip", "inject"]

# opciones habituales (se ofrecen tras una coma): se insertan como `amp: `
OPCIONES = ["amp", "pan", "attack", "decay", "sustain", "release", "attack_level", "decay_level", "sustain_level", "env_curve",
            "cutoff", "res", "rate", "start", "finish", "beat_stretch", "pitch_stretch", "pitch", "window_size", "lpf", "hpf",
            "norm", "slide", "amp_slide", "pan_slide", "cutoff_slide", "mix", "room", "damp", "phase", "depth", "wave", "detune",
            "width", "note", "vel", "level", "pre_amp", "time", "feedback", "compress", "slicer", "probability", "decay_level",
            "cutoff_attack", "cutoff_release", "res_slide", "rpitch", "sustain_level", "lpf_min", "hpf_max", "rate_slide"]

# plantillas: (texto, trozo que queda seleccionado, filas hasta la siguiente parada con Tab | None)
SNIPPETS = {
    "live_loop": ("live_loop :nombre do\n  \nend", "nombre", 1),
    "with_fx": ("with_fx :reverb do\n  \nend", "reverb", 1),
    "with_synth": ("with_synth :beep do\n  \nend", "beep", 1),
    "define": ("define :nombre do\n  \nend", "nombre", 1),
    "in_thread": ("in_thread do\n  \nend", None, 1),
    "loop": ("loop do\n  \nend", None, 1),
    "density": ("density 2 do\n  \nend", "2", 1),
    "with_bpm": ("with_bpm 120 do\n  \nend", "120", 1),
    "use_bpm": ("use_bpm 100", "100", None),
    "use_synth": ("use_synth :beep", "beep", None),
    "sample": ("sample :bd_haus", "bd_haus", None),
}

def _norm(s): return s.replace("_", "").lower()

def _subsec(p, n):
    it = iter(n)
    return all(c in it for c in p)

def _puntua(nombre, pref):
    """0 = empieza igual, 1 = contiene, 2 = letras en orden (difuso); None = no coincide. Ignora los guiones bajos: liveloop -> live_loop."""
    if not pref: return 0
    n, p = _norm(nombre), _norm(pref)
    if n.startswith(p) or nombre.lower().startswith(pref.lower()): return 0
    if p in n: return 1
    if len(p) >= 3 and _subsec(p, n): return 2
    return None

def _filtra(pref, fuentes):
    """fuentes: [(nombres, tipo, rango, prefijo_ins, sufijo_ins, snippet_ok)] -> candidatos ordenados."""
    out = []
    for nombres, tipo, rango, suf in fuentes:
        for n in nombres:
            s = _puntua(n, pref)
            if s is not None:
                out.append(((s, rango, len(n), n), Cand(n, tipo, n + suf, n if (tipo == "snippet") else None)))
    out.sort(key=lambda x: x[0])
    vistos, res = set(), []
    for _, c in out:
        if c.nombre not in vistos:
            vistos.add(c.nombre); res.append(c)
    return res[:40]

def _contexto_simbolo(resto):
    if re.search(r"\b(sample|load_sample|sample_duration|sample_info|sample_buffer|sample_loaded\?)\b[^,]*$", resto): return "sample"
    if re.search(r"\b(use_synth|with_synth|synth|use_merged_synth_defaults)\b[^,]*$", resto): return "synth"
    if re.search(r"\b(with_fx|use_fx)\b[^,]*$", resto): return "fx"
    if re.search(r"\bscale\s*\(?\s*[^,()]*,\s*:$", resto): return "escala"
    if re.search(r"\bchord(_invert)?\s*\(?\s*[^,()]*,\s*:$", resto): return "acorde"
    return None

def candidatos(antes):
    """antes: texto de la linea hasta el cursor. Devuelve (prefijo, candidatos); lista vacia = no mostrar nada."""
    if "#" in antes or (antes.count('"') % 2) or (antes.count("'") % 2): return "", []     # comentario o cadena
    m = re.search(r"[A-Za-z_]\w*[?!]?$", antes)
    pref = m.group() if m else ""
    resto = antes[:len(antes) - len(pref)]
    simbolo = resto.endswith(":") and not resto.endswith("::") and (len(resto) < 2 or not resto[-2].isalnum())
    if re.match(r"\s*(live_loop|define|defonce)\s+:\w*$", antes):
        return pref, []                                                  # poniendo nombre a un bucle: no sugerir
    if simbolo:
        ctx = _contexto_simbolo(resto)
        fuentes = {"sample": [(_dat("SAMPLES"), "sample", 0, "")], "synth": [(_dat("SYNTHS"), "synth", 0, "")],
                   "fx": [(_dat("FX"), "fx", 0, "")], "escala": [(_dat("ESCALAS"), "escala", 0, "")], "acorde": [(_dat("ACORDES"), "acorde", 0, "")],
                   None: [(_dat("SAMPLES"), "sample", 1, ""), (_dat("SYNTHS"), "synth", 0, ""), (_dat("FX"), "fx", 2, ""),
                          (_dat("ESCALAS"), "escala", 3, ""), (_dat("ACORDES"), "acorde", 4, "")]}[ctx]
        res = _filtra(pref, fuentes)
        if ctx is None and not pref: return pref, []                    # `:` suelta sin contexto: demasiadas opciones
    else:
        if len(pref) < 2: return pref, []
        tras_coma = resto.rstrip().endswith(",") or resto.rstrip().endswith("(")
        fuentes = [(list(SNIPPETS), "snippet", 0, ""), (_dat("FUNCIONES"), "sonic pi", 1, ""), (RUBY, "ruby", 2, "")]
        if tras_coma: fuentes.insert(0, (OPCIONES, "opcion", -1, ": "))
        res = _filtra(pref, fuentes)
    if len(res) == 1 and res[0].nombre == pref and res[0].snippet is None: return pref, []    # ya esta escrito completo
    if res and all(c.nombre == pref and c.snippet is None for c in res): return pref, []
    return pref, res
