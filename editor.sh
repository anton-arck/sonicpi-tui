#!/bin/sh
# Editor de codigo para Sonic Pi (cierra antes la ventana de Sonic Pi si la tienes abierta)
cd "$(dirname "$0")" && exec .venv/bin/python -I src/editor.py "$@"
