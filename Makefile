# Operar el producto con un comando. `make` a secas lista lo que hay.
#
# Un cerebro (`hugin/`) y dos puertas (`telegram/`, `telefono/`), ADR-024.
# El cerebro es una libreria: no se arranca ni escucha en ningun puerto. Las
# puertas se arrancan desde su carpeta, cada una con su Makefile.

VENV := .venv
PY   := $(VENV)/bin/python
RUFF := $(VENV)/bin/ruff

.DEFAULT_GOAL := ayuda

ayuda:  ## esta lista
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## */\t/' | column -t -s "$$(printf '\t')"

$(PY):
	@# Nada de >/dev/null aqui: con una conexion lenta, pip tarda minutos en
	@# bajar los paquetes y sin salida esto parece un cuelgue. Alguien acaba
	@# matandolo a Ctrl+C a medias y dejando el venv incompleto.
	@#
	@# Y `python -m pip`, nunca `$(VENV)/bin/pip`: ese script lleva el
	@# interprete escrito en el shebang, asi que si el venv se creo en otra
	@# ruta instala en el venv de ALLI diciendo "Successfully installed".
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	@# Editable, no solo ruff: sin esto `import hugin` depende de que cada
	@# fichero se apane el sys.path, que es justo lo que el ADR-024 quita.
	$(PY) -m pip install -e ".[dev,test,postgres]" || \
	  { echo "⚠️  no he podido instalar el paquete entero. Reintenta, o instala"; \
	    echo "   sin los extras:  $(PY) -m pip install -e ."; exit 1; }

instalar: $(PY)  ## venv + el paquete en editable + ruff

pruebas: $(PY)  ## TODAS las pruebas y el lint: cerebro, telegram y telefono
	@# Sigue hasta el final en vez de parar en el primer fallo: es mas util
	@# ver los tres problemas de una vez que descubrirlos de uno en uno.
	@# Se usa el python del venv y no el del sistema: con el de fuera el
	@# paquete no esta instalado y las pruebas dicen cosas que no son.
	@# telegram todavia importa el diario de midgaror (fases 4 y 5 del
	@# ADR-024): sin MIDGAROR_RAIZ no se puede correr, y eso se DICE en vez
	@# de saltarselo en silencio. Una comprobacion saltada no es una pasada.
	@fallos=0; saltadas=0; \
	echo "── cerebro ──"; \
	$(PY) -m unittest discover -s tests || fallos=$$((fallos+1)); \
	echo "── telefono ──"; \
	( cd telefono && ../$(PY) -m unittest discover -s tests ) || fallos=$$((fallos+1)); \
	echo "── telegram ──"; \
	if [ -n "$$MIDGAROR_RAIZ" ]; then \
	  ( cd telegram && ../$(PY) -m unittest discover -s tests ) || fallos=$$((fallos+1)); \
	else \
	  echo "⚠️  SALTADA: falta MIDGAROR_RAIZ. Las pruebas de telegram NO se han corrido."; \
	  echo "   export MIDGAROR_RAIZ=/ruta/a/midgaror"; \
	  saltadas=$$((saltadas+1)); \
	fi; \
	echo "── lint ──"; \
	if [ -x $(RUFF) ]; then $(RUFF) check . || fallos=$$((fallos+1)); \
	else echo "⚠️  SIN RUFF: el lint NO se ha corrido."; fi; \
	echo; \
	if [ $$fallos -ne 0 ]; then \
	  echo "❌ $$fallos comprobacion(es) en rojo. No subas esto."; exit 1; \
	elif [ $$saltadas -ne 0 ]; then \
	  echo "🟡 En verde lo que se ha corrido, pero $$saltadas comprobacion(es) SALTADA(s)."; \
	  echo "   Una comprobacion saltada no es una comprobacion pasada."; \
	else echo "✅ Todo en verde."; fi

.PHONY: ayuda instalar pruebas
