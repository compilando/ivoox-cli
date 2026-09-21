# Publicar una versión

El nombre `ivoox-cli` estaba libre en PyPI al preparar la versión 0.1.0. El
workflow `publish.yml` construye una wheel universal y el sdist; no guarda
contraseñas ni tokens de larga duración.

## Configuración única en PyPI

1. Crea un *pending trusted publisher* para el proyecto `ivoox-cli`.
2. Usa propietario `compilando`, repositorio `ivoox-cli`, workflow
   `publish.yml` y environment `pypi`.
3. En GitHub, crea el environment `pypi` y, si quieres, exige aprobación.

## Cada versión

1. Actualiza `version` en `pyproject.toml` y `__version__` en
   `src/ivoox_cli/__init__.py` con el mismo valor.
2. Ejecuta `uv lock`, `make lint`, `uv build` y `make test-tui`.
3. Fusiona los cambios y publica una GitHub Release con tag `vX.Y.Z`.

El workflow rechaza un tag que no coincida con la versión del paquete. La
GitHub Release dispara la publicación en PyPI mediante OIDC.

## Homebrew y AUR

Este proyecto distribuye una aplicación Python pura, por lo que PyPI con
`pipx`/`uv tool` es el canal primario también en macOS y Arch. Una fórmula de
Homebrew correcta necesita una versión ya publicada, su SHA-256 y todos los
recursos Python fijados; un `PKGBUILD` estable también necesita la URL y el
checksum definitivos. Conviene crearlos después de publicar 0.1.0, no añadir
plantillas con hashes ficticios.
