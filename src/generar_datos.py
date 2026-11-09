"""Genera src/sp_datos.py (nombres de Sonic Pi para el autocompletado) leyendo Sonic Pi.
Base: el Sonic Pi 4.x instalado. Los nombres que solo existen en la 5.0 se guardan aparte (*_V5) y solo se ofrecen si el editor detecta Sonic Pi 5.
Uso: .venv/bin/python -I src/generar_datos.py [--v5 RAIZ_DEL_CODIGO_DE_SONIC_PI_5]     (RAIZ tiene app/ y etc/)"""
import glob, os, re, sys
INSTALADO = ("/usr/lib/sonic-pi/server/ruby/lib/sonicpi", "/usr/share/sonic-pi/samples")
SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sp_datos.py")
INTERNOS = ("basic_", "main_mixer", "mono_player", "stereo_player")          # sintetizadores internos, no se usan con `synth`

def leer(p): return open(p, encoding="utf-8", errors="replace").read()

def claves(p, var, patron):
    t = leer(p); i = t.index(var)
    return sorted(set(re.findall(patron, t[i:i + 20000], re.M)))

def extraer(ruby, muestras):
    info = leer(f"{ruby}/synths/synthinfo.rb")
    tabla = info[info.index("@@synth_infos ="):]; tabla = tabla[:tabla.index("}")]
    nombres = re.findall(r":(\w+)\s*=>", tabla)
    return {
        "SAMPLES": {os.path.splitext(f)[0] for f in os.listdir(muestras) if f.endswith((".flac", ".wav", ".aif"))},
        "SYNTHS": {n for n in nombres if not n.startswith("fx_") and not n.startswith(INTERNOS)},
        "FX": {n[3:] for n in nombres if n.startswith("fx_")},
        "FUNCIONES": {n for f in glob.glob(f"{ruby}/lang/*.rb") for n in re.findall(r"^\s*doc\s+name:\s*:(\w+)", leer(f), re.M)},
        "ESCALAS": {n for n in claves(f"{ruby}/scale.rb", "ionian:", r"^\s+(\w+):\s+\S") if not n.endswith("_sequence")},
        "ACORDES": {n for n in claves(f"{ruby}/chord.rb", "CHORD, CHORD_LOOKUP", r"^\s*:(\w+)\s*=>") if len(n) > 1},
    }

if __name__ == "__main__":
    base = extraer(*INSTALADO)
    solo5 = {k: set() for k in base}
    if "--v5" in sys.argv:
        raiz = sys.argv[sys.argv.index("--v5") + 1]
        v5 = extraer(f"{raiz}/app/server/ruby/lib/sonicpi", f"{raiz}/etc/samples")
        solo5 = {k: v5[k] - base[k] for k in base}
    sal = '"""Generado por generar_datos.py. No editar a mano. *_V5: nombres que solo existen en Sonic Pi 5."""\n'
    for k in base: sal += f"{k} = {sorted(base[k])!r}\n"
    for k in base: sal += f"{k}_V5 = {sorted(solo5[k])!r}\n"
    open(SALIDA, "w").write(sal)
    print(", ".join(f"{len(base[k])} {k.lower()}" for k in base), "| solo 5.0:", ", ".join(f"{len(solo5[k])} {k.lower()}" for k in base if solo5[k]) or "ninguno (no se uso --v5)")
