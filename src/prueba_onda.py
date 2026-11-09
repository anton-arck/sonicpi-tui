"""Prueba de la onda por bucle (Sonic Pi 5): lector de memoria compartida con un segmento falso, y dibujo en el editor. Sin Sonic Pi ni audio."""
import asyncio, math, os, struct, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import editor, osciloscopio as O
from editor import Editor, Codigo
editor.ARCHIVO_TEMA = os.path.join(tempfile.mkdtemp(), "tema.json")

def check(n, ok): print(("OK    " if ok else "FALLA ") + n); return bool(ok)
CAP, CH, MAX = 64, 2, 4

def segmento(ruta, magic=O.MAGIC, slot=1, wp=100, amp=0.5):
    """Archivo con el formato de SuperSonic: cabecera de 26 campos u32, y MAX slots con su cabecera de 32 bytes y un anillo estereo."""
    h = dict.fromkeys(O.CAMPOS, 0)
    h.update(magic=magic, blob_offset=128, scope_offset=200, scope_max=MAX, scope_header_bytes=32, scope_slot_bytes=32 + CAP * CH * 4, scope_slot_header=32, scope_ring_frames=CAP, scope_channels=CH)
    buf = bytearray(128 + 200 + 32 + MAX * h["scope_slot_bytes"])
    struct.pack_into("<" + "I" * len(O.CAMPOS), buf, 0, *(h[k] for k in O.CAMPOS))
    o = 128 + 200 + 32 + slot * h["scope_slot_bytes"]
    struct.pack_into("<IIIIQQ", buf, o, 1, CH, CAP, 0, wp, 0)
    for i in range(CAP): struct.pack_into("<ff", buf, o + 32 + i * 8, amp * (i / CAP), -1.0)      # izquierdo = rampa, derecho = -1 (no debe leerse)
    open(ruta, "wb").write(buf)

async def main():
    r = []; d = tempfile.mkdtemp(); ruta = os.path.join(d, "SuperSonic_1")
    r.append(check("sin segmento: no abre ni da muestras", not O.Osciloscopio(ruta).abrir() and O.Osciloscopio(ruta).muestras(1) is None))
    segmento(ruta, magic=1234)
    r.append(check("magic incorrecto: se rechaza", not O.Osciloscopio(ruta).abrir()))
    open(ruta, "wb").write(b"corto")
    r.append(check("archivo truncado: se rechaza", not O.Osciloscopio(ruta).abrir()))
    segmento(ruta, wp=100)
    o = O.Osciloscopio(ruta)
    m = o.muestras(1)
    r.append(check("slot en uso: devuelve todo el anillo del canal izquierdo", m is not None and len(m) == CAP and all(v >= 0 for v in m)))
    r.append(check("ordenado de la mas antigua a la mas reciente (wp=100, cap=64 -> empieza en el indice 36)", abs(m[0] - 0.5 * 36 / CAP) < 1e-6 and abs(m[-1] - 0.5 * 35 / CAP) < 1e-6))
    r.append(check("slot sin usar o fuera de rango: None", o.muestras(2) is None and o.muestras(99) is None and o.muestras(-1) is None))
    env = O.envolvente([0.0] * 32 + [0.8] * 32, 4)
    r.append(check("envolvente: pico por tramo", env == [0.0, 0.0, 0.8, 0.8]))
    n = O.niveles_texto([0.0, 0.002, 0.05, 0.5, 1.0])
    r.append(check("niveles: silencio=0, creciente y maximo=8", n[0] == 0 and n[1] == 0 and n[2] < n[3] < n[4] == 8))
    o.cerrar()
    # ---- editor
    app = Editor(con_servidor=False)
    async with app.run_test(size=(100, 30)) as p:
        cod = app.query_one("#cod", Codigo)
        class SP:
            p_scsynth = 1; version = 5
            def ejecutar(self, c): pass
            def parar(self): pass
            def volumen(self, v): pass
        app.sp = SP(); app._poner("live_loop :a do\n  sample :bd_haus\n  sleep 1\nend\n"); await p.pause()
        app._osc = O.Osciloscopio(ruta)
        app._mensaje("bucle", ("a", 1, 1)); app._tick_bucles(); await p.pause()
        b = app.bucles["a"]
        r.append(check("el bucle guarda su slot y su onda se lee", b["slot"] == 1 and b["onda"] and len(b["onda"]) == O.COLUMNAS))
        linea = "".join(s.text for s in cod.render_line(0))
        r.append(check("la cabecera dibuja onda y 16 pasos", any(c in linea for c in O.NIVELES) and linea.count("■") == 16))
        app._mensaje("bucle", ("a", 1, 7)); app._tick_bucles()
        r.append(check("slot sin datos: la onda se omite y quedan los pasos", app.bucles["a"]["onda"] is None and "".join(s.text for s in cod.render_line(0)).count("■") == 16))
        app._mensaje("bucle", ("a", 1))
        r.append(check("el mensaje sin slot (compatibilidad) no falla", app.bucles["a"]["slot"] is None))
    print(f"\n{sum(r)}/{len(r)} OK"); return all(r)

sys.exit(0 if asyncio.run(main()) else 1)
