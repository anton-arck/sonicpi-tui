# sonicpi-tui

Un editor de código para [Sonic Pi](https://sonic-pi.net) que vive en la terminal y se maneja **solo con el teclado, sin Ctrl, Alt ni teclas F**.
Es modal (como Vim) y usa `Espacio` como tecla líder con un menú que aparece al pulsarlo. Lanza su propio servidor de Sonic Pi, sin ventana,
así que funciona bien dentro de tmux o zellij sin chocar con sus atajos.

Hecho con [Textual](https://textual.textualize.io). Probado en Linux (Arch) con Sonic Pi 4.6.

## Qué incluye

- Edición modal: normal, insertar y visual, con contadores y operadores (`5j`, `dd`, `cw`, `yy`, `p`, `u`...).
- Menú `Espacio` (which-key): ejecutar, parar, guardar, abrir, volumen, temas, paleta de comandos...
- **Autocompletado** de Ruby y Sonic Pi con conocimiento del contexto: samples tras `sample :`, synths tras `use_synth :`, efectos tras `with_fx :`,
  escalas, acordes y opciones (`amp:`, `release:`...). Tolera escribir sin guion bajo (`liveloop` → `live_loop`) y trae plantillas (`live_loop`, `with_fx`, `define`...).
- **Con Sonic Pi 5:** las líneas se tiñen un instante cuando suenan (como el destello de la app) y y, si la activas con `Espacio o p` (viene **desactivada**; la opción se recuerda), a la derecha de cada `live_loop` se dibuja una **línea de 16 pasos**, como un secuenciador: cada vuelta del bucle se divide en 16, los pasos donde suena un `sample` o un `play` (aprendidos de la vuelta anterior) se marcan en verde y un cursor ilumina el paso que va sonando. Debajo del código queda una fila con los nombres de los bucles en marcha. Sustituye al mini scope con la forma de onda, que el servidor no envía por OSC. Al ejecutar solo una selección, un bloque o una línea se rellena con líneas en blanco para que los números de línea del servidor coincidan con los del editor. Limitaciones: si insertas o borras líneas por encima de un bucle que sigue sonando, sus destellos se desplazan hasta que lo ejecutes de nuevo; los bucles con `sleep` aleatorio o con muchas variaciones muestran el patrón de la última vuelta; y la línea de pasos no se dibuja si la cabecera del bucle es tan larga que taparía código.
- Resaltado de sintaxis Ruby, sangría automática, log opcional y barra de volumen.
- Temas: `sonicpi`, `matrix` (negro puro, verde neón y marco), `neon` y `ambar`.
- Los errores se muestran en rojo y el cursor salta a la línea del fallo.

## Requisitos

- **Sonic Pi 4.x o 5.x** instalado (el paquete del sistema; usa su `daemon.rb`). La versión se detecta sola. **Probadas con la app real: 4.6 y 5.0.0** (arranque sin ventana, ejecución de código, logs, errores y cierre; la 5.0 arranca en ~2 s frente a ~6 s de la 4.6). Lo que no está verificado de forma automática es el sonido, ya que las pruebas corren en silencio. Si algo falla, abre una incidencia con el mensaje del log.
- Python 3.12 o superior y Ruby del sistema.
- Cierra la ventana de Sonic Pi antes de abrir el editor: no pueden convivir, porque el editor lanza su propio servidor.

```sh
git clone https://github.com/anton-arck/sonicpi-tui.git && cd sonicpi-tui
python -m venv .venv
.venv/bin/pip install -r requirements.txt
./editor.sh [archivo.rb]
```

Si Sonic Pi no está en una ruta habitual (`/usr/lib/sonic-pi`, `/opt/sonic-pi`...) o el Ruby no está en `/usr/bin/ruby`, indícalo con variables de entorno:

```sh
SONICPI_DAEMON=/ruta/a/sonic-pi/server/ruby/bin/daemon.rb SONICPI_RUBY=/ruta/a/ruby ./editor.sh
```

### Conservar tu Sonic Pi 4.x aunque instales la 5 (opcional)

`tools/aislar-sonicpi.sh` copia el Sonic Pi 4.x instalado a `~/.local/share/sonicpi-tui/sonic-pi-4.6` (unos 215 MB) y le cambia las rutas fijas del paquete
para que no dependa de `/usr/lib/sonic-pi` ni de `/usr/share/sonic-pi`. Ejecútalo **antes** de actualizar Sonic Pi. El editor usa esa copia automáticamente
(con su propia configuración y logs, sin tocar `~/.sonic-pi`) y puedes instalar la 5.0 en el sistema sin que le afecte. Para probar la 5.0 del sistema:

```sh
SONICPI_USAR=sistema ./editor.sh
```

La copia sigue usando el motor de audio (`supercollider`, `sc3-plugins`) y las librerías Ruby del sistema; el script imprime el comando de `pacman -D --asexplicit`
que evita que se traten como paquetes huérfanos al actualizar. Orden de búsqueda del servidor: `SONICPI_DAEMON` > copia aislada > Sonic Pi del sistema.

Los archivos se guardan en `codigo/`. El tema, el estado del log y el último archivo se recuerdan en `tema.json` (no se sube al repositorio).

## Cómo se maneja

Solo letras, `Espacio` y `Esc`. La barra inferior muestra el modo; la ayuda de teclas aparece únicamente al pulsar `Espacio`.

| Modo normal | |
|---|---|
| `h j k l`, `w b`, `0 ^ $`, `gg G`, `{ }` | moverse (con número: `5j`, `3w`) |
| `i a I A o O` | entrar en insertar (`Esc` vuelve) |
| `x`, `dd`, `dw`, `d$`, `D`, `yy`, `yw`, `cc`, `cw`, `C`, `p`, `P` | borrar / copiar / cambiar / pegar |
| `u` / `U` | deshacer / rehacer |
| `>>` / `<<` | sangrar / quitar sangría |
| `v` / `V` | visual (luego `y d c`, o `Espacio r` para ejecutar lo elegido) |

| `Espacio` + | |
|---|---|
| `r` | ejecutar todo (o la selección) |
| `e` / `l` | ejecutar el bloque (hasta línea en blanco) / la línea |
| `s` | parar |
| `w` / `n` | guardar / nuevo |
| `f f` | abrir archivo (`j k` mueven, Enter abre) |
| `v u` / `v d` | volumen + / - |
| `o l` | mostrar / ocultar el log (un error lo abre solo) |
| `o p` | mostrar / ocultar la línea de 16 pasos de los bucles (Sonic Pi 5) |
| `t` | elegir tema (`j k` previsualiza, Enter lo guarda) |
| `p` | paleta de comandos |
| `?` | hoja de atajos en el log |
| `q` | salir (con cambios pide repetirlo) |

### Autocompletado

En modo insertar aparece una lista junto al cursor. `Tab` acepta, `↑`/`↓` eligen. Las plantillas dejan el nombre seleccionado para escribirlo
y otro `Tab` salta al cuerpo del bloque. Los nombres de samples, synths, efectos, funciones, escalas y acordes salen del Sonic Pi instalado:
`.venv/bin/python -I src/generar_datos.py [--v5 RAIZ_DEL_CODIGO_DE_SONIC_PI_5]` regenera `src/sp_datos.py` (ajusta las rutas del script si tu instalación es distinta). Lo que solo existe en la 5.0 se ofrece únicamente si el editor detecta Sonic Pi 5.

## Estructura

| | |
|---|---|
| `src/editor.py` | el editor (interfaz, modos, temas, popup) |
| `src/autocompletar.py` | lógica del autocompletado, sin interfaz |
| `src/sp_datos.py` | nombres de Sonic Pi 4.6 (generado) |
| `src/cliente.py` | servidor de Sonic Pi sin ventana y cliente OSC (4.x y 5.x): ejecutar, parar, volumen y logs |
| `tools/aislar-sonicpi.sh` | copia aislada del Sonic Pi 4.x |
| `src/falso_daemon.py` | daemon simulado de Sonic Pi 4/5 para probar el cliente sin audio |
| `src/generar_datos.py` | regenera `sp_datos.py` |
| `src/prueba_*.py` | pruebas automáticas, sin audio |

## Pruebas

```sh
for t in prueba_editor prueba_salir prueba_autocompletar prueba_popup prueba_cliente prueba_flash; do .venv/bin/python -I src/$t.py | tail -1; done
```

Las pruebas simulan teclas con el piloto de Textual y no necesitan Sonic Pi ni producen sonido.

## Cómo habla con Sonic Pi

El cliente lanza `daemon.rb`, lee de su salida los puertos y el token, envía OSC por UDP (`/run-code`, `/stop-all-jobs`, `/mixer-amp`, y `/daemon/keep-alive`
cada pocos segundos) y escucha los mensajes de log y error. Es el mismo protocolo que usa `bin/repl.rb` de Sonic Pi.

## Licencia y créditos

Licencia MIT (ver `LICENSE`).

Sonic Pi es de Sam Aaron y colaboradores (licencia MIT). Este proyecto no incluye su código: solo se comunica con una instalación existente
y extrae nombres de su documentación para el autocompletado.
