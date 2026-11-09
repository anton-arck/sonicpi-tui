"""Prueba de destellos de linea, lista de bucles y numeracion de lineas al ejecutar trozos (sin Sonic Pi ni audio).
Uso: .venv/bin/python -I src/prueba_flash.py [captura.svg]"""
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import editor, cliente
from editor import Editor, Codigo, TEMAS, fin_de_bucle
from rich.color import Color
from textual.widgets.text_area import Selection
editor.ARCHIVO_TEMA = os.path.join(tempfile.mkdtemp(), "tema.json")          # no tocar la configuracion real

def check(n, ok): print(("OK    " if ok else "FALLA ") + n); return bool(ok)
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
        # ---- bucles
        r.append(check("sin bucles el panel esta oculto", not app.query_one("#bucles").display))
        app._mensaje("bucle", ("bombo", 1))
        b = app.bucles["bombo"]
        r.append(check("bucle: fila 0 y su end en la fila 3", b["fila"] == 0 and b["fin"] == 3))
        r.append(check("el panel aparece al haber bucles", app.query_one("#bucles").display))
        app._mensaje("flash", 1); app._mensaje("flash", 4)
        r.append(check("cabecera y end no cuentan como golpe", b["cur"] == 0))
        app._mensaje("flash", 2); app._mensaje("flash", 3)
        r.append(check("instrucciones internas = golpes (2)", b["cur"] == 2))
        app._tick_bucles()
        r.append(check("el tick pasa los golpes al historial", b["hist"][-1] == 2 and b["cur"] == 0))
        app._mensaje("bucle", ("nota", 6))
        panel = str(app.query_one("#bucles").render())
        r.append(check("el panel lista ambos bucles", "bombo" in panel and "nota" in panel))
        r.append(check("el panel muestra la actividad (barra con golpes)", "▆" in panel))
        app._mensaje("flash", 7)
        r.append(check("el golpe va al bucle cuya fila contiene la linea", app.bucles["nota"]["cur"] == 1 and app.bucles["bombo"]["cur"] == 0))
        app._mensaje("bucle", ("bombo", 1))
        r.append(check("redefinir un bucle conserva su historial", app.bucles["bombo"]["hist"][-1] == 2))
        app._mensaje("bucle_fin", "bombo")
        r.append(check("scope-ended quita el bucle", list(app.bucles) == ["nota"]))
        for i in range(8): app._mensaje("bucle", (f"b{i}", 1))
        r.append(check("con muchos bucles el panel no crece sin limite", "mas" in str(app.query_one("#bucles").render()) and str(app.query_one("#bucles").render()).count("\n") <= 5))
        app.action_parar()
        r.append(check("parar: se envia, vacia bucles y destellos y oculta el panel", sp.paradas == 1 and not app.bucles and not cod.flashes and not app.query_one("#bucles").display))
        if len(sys.argv) > 1:
            app._poner(CODIGO); await p.pause()
            app._mensaje("bucle", ("bombo", 1)); app._mensaje("bucle", ("nota", 6))
            for i in range(24):
                if i % 2 == 0: app._mensaje("flash", 2)
                if i % 5 == 0: app._mensaje("flash", 7)
                app._tick_bucles()
            app._mensaje("flash", 2); app._mensaje("flash", 1); app._mensaje("flash", 4); await p.pause(0.05)
            open(sys.argv[1], "w").write(app.export_screenshot())
    # ---- varios
    r.append(check("fin_de_bucle respeta el sangrado (bucle anidado)", fin_de_bucle(type("D", (), {"line_count": 6, "get_line": lambda s, i: ["a do", "  b do", "    x", "  end", "end", ""][i]})(), 0) == 4))
    r.append(check("version_probable: arbol app/server = 5", cliente.version_probable("/usr/lib/sonic-pi/app/server/ruby/bin/daemon.rb") == 5))
    r.append(check("version_probable: copia aislada y paquete 4.x = 4", cliente.version_probable(cliente.AISLADO_DAEMON) == 4 and cliente.version_probable("/usr/lib/sonic-pi/server/ruby/bin/daemon.rb") == 4))
    print(f"\n{sum(r)}/{len(r)} comprobaciones correctas")
asyncio.run(main())
