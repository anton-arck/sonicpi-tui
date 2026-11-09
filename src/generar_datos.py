"""Genera src/sp_datos.py (nombres de Sonic Pi para el autocompletado) leyendo el Sonic Pi instalado.
Uso: .venv/bin/python -I src/generar_datos.py"""
import glob, os, re
RUBY = "/usr/lib/sonic-pi/server/ruby/lib/sonicpi"
MUESTRAS = "/usr/share/sonic-pi/samples"
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp_datos.py")

def leer(p): return open(p, encoding="utf-8", errors="replace").read()

info = leer(f"{RUBY}/synths/synthinfo.rb")
tabla = info[info.index("@@synth_infos ="):]
tabla = tabla[:tabla.index("}")]
nombres = re.findall(r":(\w+)\s*=>", tabla)
fx = sorted({n[3:] for n in nombres if n.startswith("fx_")})
INTERNOS = ("basic_", "main_mixer", "mono_player", "stereo_player")          # sintetizadores internos de Sonic Pi, no se usan con `synth`
synths = sorted({n for n in nombres if not n.startswith("fx_") and not n.startswith(INTERNOS)})
muestras = sorted(os.path.splitext(f)[0] for f in os.listdir(MUESTRAS) if f.endswith((".flac", ".wav", ".aif")))
funciones = sorted({n for f in glob.glob(f"{RUBY}/lang/*.rb") for n in re.findall(r"^\s*doc\s+name:\s*:(\w+)", leer(f), re.M)})
def claves(p, var, patron):
    t = leer(p); i = t.index(var)
    return sorted(set(re.findall(patron, t[i:i + 20000], re.M)))
escalas = [n for n in claves(f"{RUBY}/scale.rb", "ionian:", r"^\s+(\w+):\s+\S") if not n.endswith("_sequence")]
acordes = [n for n in claves(f"{RUBY}/chord.rb", "CHORD, CHORD_LOOKUP", r"^\s*:(\w+)\s*=>") if len(n) > 1]

def lista(n, v): return f"{n} = {sorted(set(v))!r}\n"
open(SALIDA, "w").write('"""Generado por generar_datos.py a partir de Sonic Pi 4.6. No editar a mano."""\n'
    + lista("SAMPLES", muestras) + lista("SYNTHS", synths) + lista("FX", fx) + lista("FUNCIONES", funciones)
    + lista("ESCALAS", escalas) + lista("ACORDES", acordes))
print(len(muestras), "samples,", len(synths), "synths,", len(fx), "fx,", len(funciones), "funciones,", len(escalas), "escalas,", len(acordes), "acordes")
