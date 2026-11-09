#!/bin/bash
# Copia el Sonic Pi 4.x INSTALADO (paquete de Arch) a una carpeta propia y lo parchea para que no dependa de /usr/lib/sonic-pi
# ni de /usr/share/sonic-pi. Asi puedes instalar Sonic Pi 5 en el sistema y este editor sigue usando tu 4.x.
# Uso: tools/aislar-sonicpi.sh [--forzar]       (ejecutalo ANTES de actualizar Sonic Pi)
set -euo pipefail
DEST="${SONICPI_TUI_DIR:-$HOME/.local/share/sonicpi-tui}/sonic-pi-4.6"
HOME_SP="${SONICPI_TUI_DIR:-$HOME/.local/share/sonicpi-tui}/home"
ver="$(pacman -Q sonic-pi 2>/dev/null | awk '{print $2}' || true)"
echo "Sonic Pi instalado: ${ver:-desconocido}"
if [[ "${1:-}" != "--forzar" && "$ver" != 4.* ]]; then
  echo "ERROR: lo instalado no es Sonic Pi 4.x. Este script solo copia la 4.x (usa --forzar si sabes lo que haces)." >&2; exit 1
fi
[[ -d /usr/lib/sonic-pi && -d /usr/share/sonic-pi ]] || { echo "ERROR: no encuentro /usr/lib/sonic-pi y /usr/share/sonic-pi" >&2; exit 1; }
if [[ -e "$DEST" ]]; then echo "Ya existe $DEST (borralo si quieres rehacerlo)." >&2; exit 1; fi
mkdir -p "$DEST" "$HOME_SP"
cp -a /usr/lib/sonic-pi "$DEST/lib"
cp -a /usr/share/sonic-pi "$DEST/share"
# rutas absolutas del paquete -> la copia (orden importante: la mas larga primero)
for f in $(grep -rIl -e "/usr/lib/sonic-pi" -e "/usr/share/sonic-pi" -e "/usr/share/doc/sonic-pi" "$DEST/lib" "$DEST/share"); do
  sed -i "s#/usr/share/doc/sonic-pi#$DEST/share/doc#g; s#/usr/share/sonic-pi#$DEST/share#g; s#/usr/lib/sonic-pi#$DEST/lib#g" "$f"
done
echo "Copia lista en $DEST ($(du -sh "$DEST" | cut -f1)). Configuracion propia en $HOME_SP"
echo
echo "IMPORTANTE antes de actualizar Sonic Pi: la copia sigue usando estos paquetes del sistema (motor de audio y librerias Ruby)."
echo "Marcalos como instalados a proposito para que pacman no los trate como huerfanos:"
echo "  sudo pacman -D --asexplicit supercollider sc3-plugins ruby-rugged ruby-i18n ruby-kramdown ruby-multi_json ruby-memoist ruby-tomlrb ruby-wavefile ruby-racc aubio"
