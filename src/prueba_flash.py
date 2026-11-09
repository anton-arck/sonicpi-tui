"""Prueba de destellos de linea, lista de bucles y numeracion de lineas al ejecutar trozos (sin Sonic Pi ni audio).
Uso: .venv/bin/python -I src/prueba_flash.py [captura.svg]"""
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import editor, cliente
from editor import Editor, Codigo, TEMAS, fin_de_bucle, estado_pasos
from rich.color import Color
from textual.widgets.text_area import Selection
editor.ARCHIVO_TEMA = os.path.join(tempfile.mkdtemp(), "tema.json")          # no tocar la configuracion real

def check(n, ok): print(("OK    " if ok else "FALLA ") + n); return bool(ok)
SEQ = "live_loop :seq do\n  sample :bd_haus\n  sleep 0.5\n  sample :sn_dub\n  sleep 0.25\n  sample :drum_cymbal_closed\n  sleep 0.25\nend\n"
CODIGO = "live_loop :bombo do\n  sample :bd_haus\n  sleep 0.5\nend\n\nlive_loop :nota do\n  play 60\n  sleep 1\nend\n"

class FalsoSP:
    def __init__(self): self.enviado = []; self.paradas = 0
    def ejecutar(self, c): self.enviado.append(c)
    def parar(self): self.paradas += 1
    def volumen(self, v): pass

def fondos(cod, fila):
    return {s.style.bgcolor for s in cod.render_line(fila - cod.scroll_offset.y) if s.style and s.style.bgcolor}

async def main():
    app = Editor(con_servidor=False); r = []
    async with app.run_test(size=(100, 30)) as p:
        cod = app.query_one("#cod", Codigo); sp = FalsoSP(); app.sp = sp; app.listo = True
        app._poner(CODIGO); await p.pause()
        T = TEMAS[app.tema]; normales = {Color.parse(T["bg"]), Color.parse(T["linea"])}
        # ---- numeracion absoluta al ejecutar trozos
        app.action_ejecutar()
        r.append(check("ejecutar todo: se envia el texto tal cual", sp.enviado[-1] == CODIGO))
        cod.selection = Selection((5, 0), (8, 3)); app.action_ejecutar()
        r.append(check("ejecutar seleccion desde la fila 5: 5 lineas en blanco delante", sp.enviado[-1].startswith("\n" * 5 + "live_loop :nota") and sp.enviado[-1].count("\n") >= 5))
        cod.selection = Selection((0, 0), (0, 0)); cod.move_cursor((6, 0)); app.action_ejecutar_linea()
        r.append(check("ejecutar linea (fila 6): 6 lineas en blanco + la linea", sp.enviado[-1] == "\n" * 6 + "  play 60"))
        cod.move_cursor((7, 0)); app.action_ejecutar_bloque()
        r.append(check("ejecutar bloque: empieza en su primera fila (5)", sp.enviado[-1].startswith("\n" * 5 + "live_loop :nota") and sp.enviado[-1].rstrip().endswith("end")))
        app._mensaje("error", "linea 7: boom")
        r.append(check("el salto al error es absoluto tambien al ejecutar trozos", cod.cursor_location[0] == 6))
        # ---- destellos
        cod.move_cursor((0, 0)); await p.pause()
        base = fondos(cod, 4)
        app._mensaje("flash", 2)
        r.append(check("flash: la fila se registra (linea 2 -> fila 1)", 1 in cod.flashes))
        f = fondos(cod, 1)
        r.append(check("flash: la fila se tine (aparece un fondo que no es el normal)", any(c not in normales for c in f)))
        r.append(check("flash: una fila sin destello no cambia", fondos(cod, 4) == base))
        app._mensaje("flash", 1); await p.pause(0.05)
        r.append(check("flash en la fila del cursor: el cursor se sigue viendo", Color.parse(T["modos"][0]) in fondos(cod, 0)))
        await p.pause(0.9)
        r.append(check("el destello se apaga solo", not cod.flashes and all(c in normales for c in fondos(cod, 1))))
        app._mensaje("flash", 999); app._mensaje("flash", 0)
        r.append(check("flash fuera del documento se ignora", not cod.flashes))
        # ---- bucles: lista de nombres y linea de pasos
        r.append(check("sin bucles el panel esta oculto", not app.query_one("#bucles").display))
        app._poner(SEQ); await p.pause()
        app._mensaje("bucle", ("seq", 1))
        b = app.bucles["seq"]
        r.append(check("bucle: cabecera en la fila 0 y su end en la fila 7", b["fila"] == 0 and b["fin"] == 7))
        r.append(check("el panel aparece y lista el bucle", app.query_one("#bucles").display and "seq" in str(app.query_one("#bucles").render())))
        # Sonic Pi manda el golpe del instante 0 unas veces ANTES y otras DESPUES de la cabecera: las dos ordenes deben dar el mismo patron
        def vuelta(t, antes):
            ev = [(1, t), (8, t), (2, t)] if not antes else [(2, t), (1, t), (8, t)]
            for l, tt in ev: app._mensaje("flash", (l, tt))
            app._mensaje("flash", (4, t + 0.5)); app._mensaje("flash", (6, t + 0.75))
        vuelta(100.0, True)
        r.append(check("primera vuelta: aun no hay periodo ni patron", b["periodo"] is None and not b["patron"]))
        vuelta(101.0, False); vuelta(102.0, True); vuelta(103.0, False); vuelta(104.0, True)
        r.append(check("el periodo se mide entre cabeceras (1.0 s)", abs(b["periodo"] - 1.0) < 1e-9))
        r.append(check("patron: golpes en los pasos 0, 8 y 12 (0, 0.5 s y 0.75 s de 1 s)", b["patron"] == {0, 8, 12}))
        e = estado_pasos(b, 104.5)
        r.append(check("a mitad de vuelta el cursor esta en el paso 8 y ahi hay golpe", e[8] == (True, True) and sum(1 for _, c in e if c) == 1))
        r.append(check("cuarto de vuelta: cursor en el paso 4 (sin golpe)", estado_pasos(b, 104.25)[4] == (False, True)))
        r.append(check("el cursor da la vuelta (paso 15 casi al final)", estado_pasos(b, 104.99)[15] == (False, True)))
        r.append(check("si el bucle se para, el cursor desaparece", not any(c for _, c in estado_pasos(b, 120.0))))
        r.append(check("los golpes se marcan aunque el cursor no este", [i for i, (h, _) in enumerate(estado_pasos(b, 120.0)) if h] == [0, 8, 12]))
        # una cabecera duplicada no rompe el periodo
        app._mensaje("flash", (1, 104.0 + 0.001))
        r.append(check("destello duplicado de cabecera se ignora", abs(b["periodo"] - 1.0) < 1e-9))
        # se dibuja a la derecha de la cabecera
        import time as _t
        b["t0"] = _t.monotonic() - 0.5
        txt = lambda fila: "".join(sg.text for sg in cod.render_line(fila - cod.scroll_offset.y))
        r.append(check("la cabecera del bucle lleva 16 cuadros a la derecha", txt(0).count("■") == 16 and txt(0).rstrip().endswith("■")))
        r.append(check("el codigo de la cabecera sigue ahi, sin tapar", txt(0).lstrip().startswith("1") and "live_loop :seq do" in txt(0)))
        r.append(check("otras filas no llevan cuadros", all("■" not in txt(f) for f in range(1, 8))))
        r.append(check("el cursor de pasos tiene un estilo distinto (negrita)", sum(1 for sg in cod.render_line(0) if sg.text == "■" and sg.style.bold) in (1, 2)))
        app._poner("live_loop :largo do  " + "x" * 120 + "\n  sleep 1\nend\n"); await p.pause()
        app._mensaje("bucle", ("largo", 1)); app.bucles["largo"]["t0"] = _t.monotonic()
        r.append(check("si la cabecera es larga y no cabe, no se tapa codigo", "■" not in txt(0)))
        app._poner(SEQ); await p.pause()
        app._mensaje("bucle", ("otro", 1))
        app._mensaje("bucle_fin", "seq"); app._mensaje("bucle_fin", "largo"); app._mensaje("bucle_fin", "otro")
        r.append(check("scope-ended quita los bucles y sus cuadros", not app.bucles and "■" not in txt(0) and not app.query_one("#bucles").display))
        app._mensaje("bucle", ("seq", 1)); app._mensaje("bucle", ("b2", 6))
        app.action_parar()
        r.append(check("parar: se envia, vacia bucles y destellos y oculta el panel", sp.paradas == 1 and not app.bucles and not cod.flashes and not app.query_one("#bucles").display))
        if len(sys.argv) > 1:
            app._poner(SEQ + "\nlive_loop :melodia do\n  play :e4\n  sleep 1\n  play :g4\n  sleep 1\nend\n"); await p.pause()
            app._mensaje("bucle", ("seq", 1)); app._mensaje("bucle", ("melodia", 10)); ahora = _t.monotonic()
            for i in range(4):
                t = ahora - 3 + i
                for l, tt in ((2, t), (1, t), (8, t), (4, t + 0.5), (6, t + 0.75)): app._mensaje("flash", (l, tt))
                for l, tt in ((11, t * 1.0), (10, t), (17, t), (13, t + 1.0)): pass
            for i in range(3):
                t = ahora - 3.5 + 2 * i
                for l, tt in ((10, t), (11, t), (13, t + 1.0)): app._mensaje("flash", (l, tt))
            app.bucles["seq"]["t0"] = ahora - 0.5; app.bucles["melodia"]["t0"] = ahora - 1.0
            app._mensaje("flash", (4, ahora)); await p.pause(0.05)
            open(sys.argv[1], "w").write(app.export_screenshot())
    # ---- varios
    r.append(check("fin_de_bucle respeta el sangrado (bucle anidado)", fin_de_bucle(type("D", (), {"line_count": 6, "get_line": lambda s, i: ["a do", "  b do", "    x", "  end", "end", ""][i]})(), 0) == 4))
    r.append(check("version_probable: arbol app/server = 5", cliente.version_probable("/usr/lib/sonic-pi/app/server/ruby/bin/daemon.rb") == 5))
    r.append(check("version_probable: copia aislada y paquete 4.x = 4", cliente.version_probable(cliente.AISLADO_DAEMON) == 4 and cliente.version_probable("/usr/lib/sonic-pi/server/ruby/bin/daemon.rb") == 4))
    print(f"\n{sum(r)}/{len(r)} comprobaciones correctas")
asyncio.run(main())
