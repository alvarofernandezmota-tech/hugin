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

pruebas: $(PY)  ## TODAS las pruebas, el lint y la auditoria estructural
	@# Sigue hasta el final en vez de parar en el primer fallo: es mas util
	@# ver los tres problemas de una vez que descubrirlos de uno en uno.
	@# El interprete se llama por ruta ABSOLUTA: con `../$(PY)` desde dentro
	@# de una puerta, Python avisa en cada ejecucion de que sys.prefix lleva
	@# un ".." dentro, y ese ruido tapa los avisos que si importan.
	@# Se usa el python del venv y no el del sistema: con el de fuera el
	@# paquete no esta instalado y las pruebas dicen cosas que no son.
	@# Desde que la fase 5 del ADR-024 se cerro (entender/conversar al
	@# cerebro), telegram/ ya no importa nada de midgaror: corre sin
	@# MIDGAROR_RAIZ, igual que cerebro y telefono.
	@fallos=0; \
	echo "── cerebro ──"; \
	$(PY) -m unittest discover -s tests || fallos=$$((fallos+1)); \
	echo "── telefono ──"; \
	( cd telefono && $(CURDIR)/$(PY) -m unittest discover -s tests ) || fallos=$$((fallos+1)); \
	echo "── telegram ──"; \
	( cd telegram && $(CURDIR)/$(PY) -m unittest discover -s tests ) || fallos=$$((fallos+1)); \
	echo "── lint ──"; \
	if [ -x $(RUFF) ]; then $(RUFF) check . || fallos=$$((fallos+1)); \
	else echo "⚠️  SIN RUFF: el lint NO se ha corrido."; fi; \
	echo "── estructura ──"; \
	$(PY) herramientas/auditoria.py || fallos=$$((fallos+1)); \
	echo; \
	if [ $$fallos -ne 0 ]; then \
	  echo "❌ $$fallos comprobacion(es) en rojo. No subas esto."; exit 1; \
	else echo "✅ Todo en verde."; fi

auditar: $(PY)  ## solo la auditoria estructural (paquetes, workflows) — rapido
	$(PY) herramientas/auditoria.py

estado: $(PY)  ## mide las pruebas y reescribe estado-pruebas.json (el badge)
	@# El badge dice "local" a proposito: no hay CI (Actions no coge runner
	@# por un cobro de la cuenta), y un badge verde que insinue lo contrario
	@# es mentir en el escaparate. Lo que promete es lo que es: alguien lo
	@# corrio en su maquina, este dia, y salio esto.
	@#
	@# Y no puede envejecer en silencio: tests/test_estado.py se cae si el
	@# numero commiteado ya no es el de verdad.
	$(PY) herramientas/estado.py

.PHONY: ayuda instalar pruebas auditar estado
