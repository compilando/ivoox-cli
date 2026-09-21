# ivx

CLI de Python para descargar episodios, listas públicas y programas de iVoox,
mantener una biblioteca y reproducirla con `fzf` y `mpv`. Es un script ejecutable
con metadatos PEP 723: `uv` prepara `requests`, `beautifulsoup4` y `textual` en un entorno
aislado. La interfaz de terminal usa Textual. No utiliza pip global ni necesita AUR.

## Biblioteca interactiva

```sh
make install                 # actualizar el ejecutable y su entorno
make tui
```

Una interfaz de teclado con colecciones a la izquierda, episodios a la derecha
y estado/progreso de reproducción abajo. Con `cookies.txt` válido carga
automáticamente Mis listas, Escuchar más tarde, Episodios favoritos y todas las
suscripciones de la cuenta. También incorpora las fuentes de `sources.txt` y
los audios descargados en `IVX_DIR`.

La lista de colecciones se guarda 15 minutos en
`$(CFG)/account-collections.json` para no consultar iVoox en cada arranque.
Pulsa `r` para actualizarla. Al abrir una colección se cargan sus 20 episodios
visibles más recientes. `☁` identifica contenido de la cuenta, `⌂` una fuente
local, `↓` un episodio para streaming y `●` uno descargado.

| Tecla | Acción |
| --- | --- |
| `Tab` / `Shift+Tab` | Cambiar de panel |
| `↑` / `↓`, `j` / `k` | Navegar |
| `Enter` | Cargar/abrir colección o reproducir episodio |
| `Espacio` | Pausar/reanudar; tras stop, reinicia el episodio |
| `s` | Detener reproducción |
| `←` / `→` | Retroceder/avanzar 10 segundos |
| `+` / `-` | Subir/bajar volumen |
| `n` / `p` | Siguiente/anterior en la lista seleccionada al empezar a reproducir |
| `/` | Buscar títulos en la colección actual |
| `o` | Alternar orden: más nuevos, más antiguos y título A–Z |
| `Esc` | Limpiar búsqueda o volver a colecciones |
| `a` | Añadir URL de episodio, lista o programa |
| `u` | Descargar hasta 10 episodios de la colección seleccionada |
| `r` | Actualizar Mis listas y Mis suscripciones desde iVoox |
| `?` | Mostrar ayuda de teclas |
| `q` | Salir y detener el mpv de esta interfaz |

La búsqueda conserva el filtro al pulsar Enter; Esc lo quita. Los controles
por letras no interfieren cuando escribes en un campo de texto. También
puedes seleccionar con ratón. Se recomienda una terminal de al menos 80×24.

La TUI controla una instancia propia de mpv mediante un socket privado en un
temporal; no modifica otros reproductores ni la configuración de mpv. Un
episodio remoto se reproduce en streaming con las cookies de iVoox. `u` lo
descarga a la biblioteca usando el CLI en segundo plano, con los mismos
bloqueos y reanudación. Salir durante una descarga la interrumpe y conserva los
parciales. Puedes usar otra biblioteca con
`make tui IVX_DIR=/ruta/a/biblioteca`. Para trabajar sin consultar la cuenta:

```sh
ivx tui --local
```

```sh
make test-tui                # navegación, búsqueda, alta de fuente y mpv real
```

Estas pruebas no acceden a iVoox ni a tus cookies: generan páginas y audio de
prueba en temporales y verifican parseo de cuenta, navegación, play, pausa,
seek, volumen, stop y cierre de mpv con salida de audio nula. `make test`
mantiene la verificación real de descargas.

## Makefile (Arch)

```sh
make                         # ayuda; no instala ni descarga nada
make deps                    # sudo pacman -S --needed mpv fzf uv python file
make install                 # ~/.local/bin/ivx; configuración privada y entorno uv
make get URL='https://www.ivoox.com/…_rf_123456_1.html' N=2 J=1
make archive URL='https://www.ivoox.com/…_sq_f112345_1.html' PLAN=1
make archive URL='https://www.ivoox.com/…_sq_f112345_1.html' J=2
make add URL='https://www.ivoox.com/…_sq_f112345_1.html'
make sync N=2
make sources
make ls
make play Q='ciencia'         # selección múltiple con Tab; Enter reproduce
```

Sustituye las URLs de ejemplo por URLs reales. `make help` lista todos los
objetivos. Los identificadores `_rf_`, `_bk_list_` y `_sq_f1` distinguen episodio,
lista y programa. Se admiten las páginas completas, no enlaces cortos `go.ivoox.com`.

Variables sobreescribibles:

| Variable | Valor por defecto | Uso |
| --- | --- | --- |
| `PREFIX` | `$(HOME)/.local` | Instala en `$(PREFIX)/bin/ivx` |
| `IVX_DIR` | `$(HOME)/Podcasts/ivoox` | Biblioteca |
| `CFG` | `$(HOME)/.config/ivx` | Fuentes, cookies y cachés de uv |
| `INTERVAL` | `6h` | Intervalo del temporizador |
| `URL` | — | Obligatoria para `get`, `archive` y `add` |
| `N` | CLI: 10 | Máximo de episodios examinados por fuente |
| `J` | `get`: 1; `archive`: 2 | Descargas simultáneas |
| `PLAN` | vacío | Con `1`, `archive` cuenta todo sin descargar |
| `Q` | vacío | Filtro de título/ruta para reproducir |

`N` cuenta episodios seleccionados, incluidos los ya descargados: repetir
`get N=2` sobre una fuente sin cambios descarga cero, no los dos siguientes.
Los límites evitan descargar accidentalmente un programa entero. Para ampliar
el histórico, aumenta `N`. `archive` es la operación explícita para descargar
el programa completo: primero descubre todos los episodios y luego usa una cola
acotada (dos descargas simultáneas por defecto). Se pausa 1,5 segundos entre
páginas HTML. Antes de una descarga grande, usa `PLAN=1` para ver el total.

```sh
make install PREFIX="$HOME/.local" CFG="$HOME/.config/ivx"
make get URL='https://www.ivoox.com/…_bk_list_12345_1.html' N=20 J=2
make sync IVX_DIR="$HOME/Podcasts/ivoox" N=5
```

La biblioteca tiene una carpeta por fuente (`episode-ID`, `list-ID`,
`program-ID`), archivos `ID.mp3`, metadatos `ID.json` y `playlist.m3u` con rutas
relativas. Un episodio presente en dos fuentes puede ocupar dos archivos.
La playlist contiene todos los audios completados de esa carpeta, ordenados
por identificador. `make ls` muestra sus títulos y rutas.

El archivado guarda `archive-state.json` con tareas completadas y fallidas.
Es seguro relanzarlo: omite los MP3 terminados y reanuda los `.part`. Conserva
el MP3 original servido por iVoox, sin recodificar ni perder calidad; convertirlo
a otro códec solo aumentaría tiempo o degradaría el audio.

Solo `make deps` necesita sudo. La primera ejecución de uv/uvx necesita red.
El Makefile usa `/usr/bin/python`, evita descargas de intérpretes y mantiene
las cachés en `CFG`; `make test` usa una caché dentro del proyecto.
`ffprobe` es opcional: se usa si está disponible para confirmar el contenido
cuando `file` devuelve un MIME genérico.

## Cookies opcionales

Las pruebas públicas no necesitan iniciar sesión. Para contenido al que tu
cuenta tenga acceso, exporta manualmente cookies en formato Netscape a
`~/.config/ivx/cookies.txt` y ejecuta:

```sh
make cookies
```

Comprueba cabecera, estructura y dominios de iVoox; aplica permisos 600 y avisa
de cookies caducadas por su campo `expires` (0 significa sesión). No imprime
valores de cookies. La configuración tiene permisos 700. Las cookies no
permiten recuperar audios eliminados ni eludir restricciones de acceso.

## systemd de usuario

```sh
make timer-install INTERVAL=6h
make timer-enable             # instala las unidades y habilita el timer
make timer-status
make logs                     # Ctrl-C deja de seguir el diario
make timer-disable
```

Se generan `~/.config/systemd/user/ivx-sync.service` y `ivx-sync.timer`.
El servicio `oneshot` ejecuta `ivx sync` con `PATH`, `IVX_DIR`, `IVX_CFG` y
la caché de uv configurados. El temporizador usa `OnBootSec=5min`,
`OnUnitActiveSec=6h` y `Persistent=true`. Systemd solo aplica la recuperación
de eventos de `Persistent` a temporizadores `OnCalendar`; con estos intervalos
monotónicos no garantiza recuperar cada ejecución perdida durante el apagado.
El temporizador depende del gestor de usuario; no se activa linger ni se
cambia configuración global del sistema.

Después de cambiar `PREFIX`, `IVX_DIR`, `CFG` o `INTERVAL`, vuelve a ejecutar
`make timer-install` con las mismas variables. `sync` descarga como máximo
10 episodios por fuente por ejecución. Sin `sources.txt` termina correctamente
sin crear la biblioteca. Añade tus programas con `make add URL=...`.

## Verificación real

```sh
# test.env ya está preparado en esta instalación; para una copia nueva:
cp -n test.env.example test.env
make test
make lint
```

`test.env` contiene `TEST_EPISODE`, `TEST_LIST`, `TEST_PROGRAM`; está excluido
de Git y se lee como datos, sin ejecutar comandos de shell. También se pueden
sobreescribir con variables de entorno o de make. No pongas credenciales ahí.

Las fuentes elegidas son un episodio de 69 segundos de Feedback Ciencia,
la lista pública Unidad de vigilancia y el programa Feedback Ciencia con RSS.
La lista es larga, pero solo se descargan dos audios de su primera página y
uno de la segunda; la inspección se limita a dos páginas. Se prefirió una
lista con audios disponibles tras encontrar enlaces rotos en listas pequeñas.
Los episodios del programa duran unos 47 minutos: una prueba completa puede
transferir varios cientos de MB, ya que también comprueba el camino HTML.

Las pruebas ejecutan el `ivx` del proyecto con `-n 2`, comprueban audio real
con `file`/`ffprobe`, las playlists y que repetir no descargue ni modifique los
archivos. Después recorren dos páginas distintas de la lista, fuerzan
`--no-rss` y descargan por HTML. Finalmente interrumpen un proceso mientras
descarga y verifican que el siguiente continúa con HTTP 206, preservando los
bytes iniciales. Se guarda `report.json` y un registro de comandos.

Todo queda en directorios únicos `.test-runs/run-*`; no se usa tu biblioteca,
fuentes ni cookies personales. Los temporales se conservan para inspección y
se retiran con `make clean`, previa confirmación. Una URL retirada o un fallo
del servidor hace fallar la prueba explícitamente; no se sustituye por mocks.

## Descarga y recuperación

Los programas usan el RSS publicado en su página. Si falta o no se puede
leer, se recorre el HTML. Las listas usan los módulos de episodios clásicos;
los programas actuales usan enlaces de títulos en el contenedor que incluye `#tabs`. Se deduplican
IDs y se sigue el enlace a la siguiente página de la misma fuente.

Para episodios se obtiene la ruta `listen_mn` publicada en el HTML. El endpoint
`vcore-web.ivoox.com/v1/public/audios/ID/download-url` queda como último recurso:
en la inspección real devolvió un error incluso para contenido reproducible.
No se ejecuta JavaScript recibido del sitio.

La descarga escribe `.mp3.part` y conserva la URL final del CDN, tamaño y
validador HTTP en `.part.json`. Al repetir, usa `Range`/`If-Range` y verifica
4 KiB de solapamiento para evitar mezclar versiones con publicidad distinta.
Si el servidor ignora Range, empieza de nuevo; si cambia el audio o caduca la
URL del CDN, informa del error y conserva el parcial. Puedes decidir eliminarlo
con `make clean` para reiniciar. Solo se renombra a `.mp3` tras validar tamaño
y tipo de archivo. Un bloqueo por biblioteca impide descargas/limpiezas simultáneas.

Uso directo y diagnóstico:

```sh
UV_CACHE_DIR="$HOME/.config/ivx/uv-cache" UV_PYTHON=/usr/bin/python ivx --help
ivx --dir /ruta/temporal get 'URL' -n 2 --no-rss
ivx inspect 'URL' --pages 2        # solo metadatos, sin descargar audio
```

Fuera del Makefile, uv utiliza sus valores de entorno y caché habituales.
`IVX_DIR` y `IVX_CFG` permiten configurar el script directamente; también
existen `--dir` y `--config`, antes del subcomando.

## Limpieza y desinstalación

`make clean` muestra los `.part` y sus metadatos, y los directorios de prueba
marcados por ivx. Solo borra tras escribir `BORRAR`; rechaza una biblioteca o
una prueba activa. No borra MP3 completados de la biblioteca. Los parciales
son reanudables: limpiarlos descarta esa posibilidad.

`make uninstall` también pide `BORRAR`, detiene/retira las unidades y elimina
el binario instalado. Conserva la biblioteca y toda la configuración, incluidas
las cachés. No desinstala paquetes de pacman. Nada se publica ni se sube a Git.
