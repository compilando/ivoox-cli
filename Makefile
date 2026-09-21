.DEFAULT_GOAL := help
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

PREFIX ?= $(HOME)/.local
IVX_DIR ?= $(HOME)/Podcasts/ivoox
CFG ?= $(HOME)/.config/ivx
INTERVAL ?= 6h
PYTHON ?= /usr/bin/python
UV ?= uv
export PREFIX IVX_DIR CFG INTERVAL
export URL N J Q
export IVX_CFG := $(CFG)
export UV_CACHE_DIR := $(CFG)/uv-cache
export UV_TOOL_DIR := $(CFG)/uv-tools
export UV_PYTHON := $(PYTHON)
export UV_PYTHON_DOWNLOADS := never
export UV_NO_MANAGED_PYTHON := 1
IVX = "$(PREFIX)/bin/ivx"

.PHONY: help deps install uninstall get add sync sources ls play tui cookies timer-install timer-enable timer-disable timer-status logs test test-tui lint clean

help: ## Lista los objetivos y sus descripciones
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

deps: ## Instala dependencias oficiales de Arch (idempotente)
	sudo pacman -S --needed mpv fzf uv python file

install: ## Instala ivx y precalienta su entorno uv
	install -Dm755 ivx "$(PREFIX)/bin/ivx"
	install -dm700 "$(CFG)"
	$(IVX) --help

uninstall: ## Pide confirmación y retira binario y unidades; conserva biblioteca/config
	@$(PYTHON) scripts/manage.py uninstall

get: ## Descarga URL=...; opcional N=... y J=...
	@test -n "$${URL:-}" || { echo 'Falta URL. Uso: make get URL=https://www.ivoox.com/...' >&2; exit 2; }
	args=(); [[ -z "$${N:-}" ]] || args+=(-n "$$N"); [[ -z "$${J:-}" ]] || args+=(-j "$$J")
	$(IVX) get "$$URL" "$${args[@]}"

add: ## Añade URL=... a las fuentes de sincronización
	@test -n "$${URL:-}" || { echo 'Falta URL. Uso: make add URL=https://www.ivoox.com/...' >&2; exit 2; }
	$(IVX) add "$$URL"

sync: ## Sincroniza las fuentes; opcional N=... por fuente
	@args=(); [[ -z "$${N:-}" ]] || args+=(-n "$$N")
	$(IVX) sync "$${args[@]}"

sources: ## Muestra las fuentes configuradas
	@if [[ -f "$(CFG)/sources.txt" ]]; then cat "$(CFG)/sources.txt"; else echo 'Sin fuentes; usa make add URL=...'; fi

ls: ## Lista los audios descargados
	@$(IVX) ls

play: ## Selecciona con fzf y reproduce con mpv; filtro opcional Q=...
	@$(IVX) play "$${Q:-}"

tui: ## Abre la biblioteca interactiva con controles de reproducción
	@$(IVX) tui

cookies: ## Valida cookies Netscape de iVoox, ajusta permisos y avisa de caducadas
	@$(PYTHON) scripts/manage.py cookies

timer-install: ## Genera las unidades de usuario; intervalo INTERVAL=6h
	@$(PYTHON) scripts/manage.py timer-install

timer-enable: timer-install ## Activa el temporizador y lo arranca
	systemctl --user enable --now ivx-sync.timer

timer-disable: ## Desactiva y detiene el temporizador
	systemctl --user disable --now ivx-sync.timer

timer-status: ## Muestra el estado del temporizador y del servicio
	@status=0
	systemctl --user status ivx-sync.timer ivx-sync.service || status=$$?
	# systemctl devuelve 3 para un oneshot que ya terminó (inactive).
	[[ $$status -eq 0 || $$status -eq 3 ]] || exit "$$status"

logs: ## Sigue el diario del servicio de sincronización
	journalctl --user -u ivx-sync -f

test: ## Verificación REAL aislada; URLs en test.env (sin versionar)
	@$(PYTHON) scripts/smoke.py

test-tui: ## Prueba navegación y controles con mpv real, sin red ni sonido
	@$(UV) run --script scripts/test_tui.py

lint: ## Ruff y compilación sintáctica del script
	uvx ruff check ivx scripts
	$(PYTHON) -m py_compile ivx scripts/manage.py scripts/smoke.py scripts/test_tui.py

clean: ## Confirma antes de borrar .part inactivos y temporales de test
	@$(PYTHON) scripts/manage.py clean
