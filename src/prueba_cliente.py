"""Prueba de la lectura de puertos del daemon (sin Sonic Pi). Uso: .venv/bin/python -I src/prueba_cliente.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cliente import leer_puertos
def check(n, ok): print(("OK    " if ok else "FALLA ") + n); return bool(ok)
def falla(linea):
    try: leer_puertos(linea)
    except RuntimeError as e: return str(e)
    return None
r = []
r.append(check("4.x: 8 valores se leen bien", leer_puertos("1 2 3 4 5 6 7 -123\n") == [1, 2, 3, 4, 5, 6, 7, -123]))
m = falla("1 2 3 4 5 99\n")
r.append(check("5.0: 6 valores dan un error claro que nombra la rama sonic-pi-5", m and "Sonic Pi 5" in m and "sonic-pi-5" in m))
r.append(check("salida basura da error legible", "no imprimio los puertos" in (falla("Warning: algo\n") or "")))
r.append(check("linea vacia da error legible", falla("") is not None))
print(f"\n{sum(r)}/{len(r)} comprobaciones correctas")
