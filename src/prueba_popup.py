"""Prueba del popup de autocompletado en el editor (sin audio). Uso: .venv/bin/python -I src/prueba_popup.py [captura.svg]"""
import asyncio, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import editor
from editor import Editor, Codigo
editor.ARCHIVO_TEMA = os.path.join(tempfile.mkdtemp(), "tema.json")     # no tocar la configuracion real
def check(n, ok):
    print(("OK    " if ok else "FALLA ") + n); return bool(ok)

async def main():
    app = Editor(con_servidor=False); r = []
    async with app.run_test(size=(100, 30)) as p:
        cod = app.query_one("#cod", Codigo); sugs = app.query_one("#sugs")
        async def t(*k): await p.press(*k); await p.pause()
        app._poner(""); await p.pause()
        await t("i")
        await t(*"liveloop")
        r.append(check("escribir 'liveloop' abre el popup con live_loop", sugs.display and cod.sugs and cod.sugs[0].nombre == "live_loop"))
        if len(sys.argv) > 1: open(sys.argv[1], "w").write(app.export_screenshot())
        await t("tab")
        r.append(check("Tab expande la plantilla live_loop", cod.text == "live_loop :nombre do\n  \nend" and cod.selected_text == "nombre"))
        await t(*"bombo")
        r.append(check("se escribe el nombre sobre el hueco y no hay popup", cod.text.startswith("live_loop :bombo do") and not sugs.display))
        await t("tab")
        r.append(check("Tab salta al cuerpo del bucle", cod.cursor_location == (1, 2)))
        await t(*"sample :bd_h")
        r.append(check("sample :bd_h sugiere bd_haus", sugs.display and cod.sugs[0].nombre == "bd_haus"))
        await t("down")
        r.append(check("flecha abajo mueve la seleccion (no el cursor)", cod.sug_i == 1 and cod.cursor_location[0] == 1))
        await t("up", "tab")
        r.append(check("Tab inserta el sample elegido", cod.document.get_line(1) == "  sample :bd_haus" and not sugs.display))
        await t("enter")
        r.append(check("Enter despues de aceptar es salto de linea normal", cod.cursor_location[0] == 2))
        await t(*"use_synth :pro")
        await t("tab")
        r.append(check("use_synth :pro -> prophet", cod.document.get_line(2).strip() == "use_synth :prophet"))
        await t("enter", *"sleep")
        r.append(check("palabra ya completa no deja popup colgado", not sugs.display or cod.sugs[0].nombre != "sleep"))
        await t("enter", "escape")
        r.append(check("Esc deja el modo insertar y oculta el popup", cod.modo == "normal" and not sugs.display))
        await t("i", *"wit")
        await t("escape")
        r.append(check("sin popup en modo normal", not sugs.display))
        # tab sin popup sigue indentando
        app._poner(""); await p.pause(); await t("i", "tab")
        r.append(check("Tab sin sugerencias sigue sangrando", cod.text == "  " or cod.text.startswith(" ") or cod.text == "\t"))
        await t(*"with_fx :re"); 
        r.append(check("with_fx :re ofrece reverb", sugs.display and any(c.nombre == "reverb" for c in cod.sugs)))
    print(f"\n{sum(r)}/{len(r)} comprobaciones correctas")
asyncio.run(main())
