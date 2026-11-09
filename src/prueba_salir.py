"""Prueba: abrir y salir sin tocar nada no pregunta; con cambios si; reabre el ultimo archivo. Uso: .venv/bin/python -I src/prueba_salir.py"""
import asyncio, os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import editor
from editor import Editor, Codigo
def check(n, ok):
    print(("OK    " if ok else "FALLA ") + n); return bool(ok)
async def main():
    d = tempfile.mkdtemp(); editor.ARCHIVO_TEMA = os.path.join(d, "tema.json"); editor.CARPETA = d; editor.RAIZ = d
    r = []
    app = Editor(con_servidor=False)
    async with app.run_test(size=(100, 30)) as p:
        await p.pause(0.5)
        r.append(check("recien abierto no tiene cambios", not app.sucio))
        await p.press("space", "q"); await p.pause(0.5)
        r.append(check("Espacio q sale a la primera", not app.is_running))
    app = Editor(con_servidor=False)
    async with app.run_test(size=(100, 30)) as p:
        await p.press("i", "x", "escape"); await p.pause()
        r.append(check("al editar hay cambios", app.sucio))
        await p.press("space", "q"); await p.pause()
        r.append(check("con cambios pide confirmar", app.is_running))
        await p.press("space", "w"); await p.pause()
        await p.press(*"canc", "full_stop", "r", "b", "enter"); await p.pause()
        r.append(check("guardado: sin cambios", not app.sucio and app.ruta and app.ruta.endswith("canc.rb")))
        await p.press("u"); await p.pause()
        r.append(check("deshacer vuelve a limpio o sucio coherente", app.sucio == (app.query_one('#cod').text != app._base)))
        await p.press("U"); await p.pause()
        r.append(check("rehacer deja el texto guardado => sin cambios", not app.sucio))
        await p.press("space", "q"); await p.pause(0.5)
        r.append(check("salir tras guardar, sin preguntar", not app.is_running))
    app = Editor(con_servidor=False)
    async with app.run_test(size=(100, 30)) as p:
        await p.pause(0.5)
        r.append(check("reabre el ultimo archivo guardado", app.ruta and app.ruta.endswith("canc.rb") and "x" in app.query_one("#cod").text))
        r.append(check("y sin cambios", not app.sucio))
    print(f"\n{sum(r)}/{len(r)} comprobaciones correctas")
asyncio.run(main())
