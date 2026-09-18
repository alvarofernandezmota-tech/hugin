"""Dónde está midgaror y cómo se importan sus módulos. En un solo sitio.

Bifrost es un submódulo dentro de midgaror y no se instala: los módulos del
diario se importan por ruta. Hasta ahora cada handler repetía las mismas
líneas para conseguirlo —subir cuatro niveles con `Path(__file__).resolve()`,
uno o dos `sys.path.insert`, y luego los imports con `# noqa: E402` porque
quedaban debajo de código—. Ocho ficheros con el mismo preámbulo y ningún
sitio donde arreglarlo una vez.

Aquí se hace una vez, al importar este módulo, y los handlers quedan así:

    from utils.midgaror import modulo

    agenda = modulo("agenda")
    sincronizar = modulo("sincronizar").sincronizar

Los nombres siguen siendo **de módulo**, no de dentro de una función: eso es
lo que permite que `tests/dobles.py` sustituya `sincronizar` handler por
handler para que las pruebas no hagan `git push` de verdad.

Si algún día bifrost se instala como paquete y midgaror se importa de verdad,
este es el único fichero que hay que tocar.
"""

import importlib
import os
import sys
from pathlib import Path

VARIABLE = "MIDGAROR_RAIZ"

# Cuenta de cuatro `.parent` heredada de cuando este fichero vivía en
# bifrost/utils/midgaror.py, con bifrost dentro de midgaror/proyectos/: ahí
# sí aterrizaba en midgaror. Desde que este fichero vive en
# hugin/telegram/utils/ (ADR-024, fase 1: "juntar el repo, sin refactorizar
# nada"), la cuenta ya no aterriza en ningún midgaror real — aterriza un
# nivel por encima de donde esté clonado hugin. No se ha corregido a
# propósito: no hay todavía un sitio "de verdad" que adivinar (la fase 6 no
# ha movido producción), y el fallback no falla en silencio — `DIARIO.is_dir()`
# más abajo lo revienta con un aviso claro. Hasta la fase 6, `MIDGAROR_RAIZ`
# es, en la práctica, obligatoria.
POR_DEFECTO = Path(__file__).resolve().parent.parent.parent.parent


def _raiz() -> Path:
    """La raíz de midgaror. `MIDGAROR_RAIZ` manda; si no, donde está hoy.

    Hasta ahora esto era una cuenta de cuatro `.parent`, que ata a bifrost a
    vivir exactamente donde vive. Mientras siga así no se puede mover ni
    probar desde un clon suelto, y las dos cosas hacen falta para llevarlo al
    repo del producto (ADR-024).

    Una variable vacía o con espacios cuenta como no definida, igual que en
    `diario/ubicacion.py`: en systemd es fácil dejar un `Environment=` a
    medias, y eso debe comportarse como no haberlo puesto.
    """
    valor = os.environ.get(VARIABLE, "").strip()
    if not valor:
        return POR_DEFECTO
    return Path(valor).expanduser().resolve()


MIDGAROR = _raiz()
DIARIO = MIDGAROR / "diario"

if not DIARIO.is_dir():
    raise ImportError(
        f"no encuentro el diario de midgaror en {DIARIO}. "
        f"Di dónde está con {VARIABLE}, por ejemplo: "
        f"export {VARIABLE}=~/GitHub/personal/midgaror-bot"
    )

# `diario/` para diario.py, organizar_diario, sincronizar, bifrost_bridge y
# almacen; las subcarpetas porque tareas.py, habitos.py, agenda.py y
# registro.py se importan por su nombre a secas.
CARPETAS = (DIARIO, DIARIO / "tareas", DIARIO / "habitos", DIARIO / "agenda",
            DIARIO / "registro")

for _carpeta in CARPETAS:
    _ruta = str(_carpeta)
    if _ruta not in sys.path:
        sys.path.insert(0, _ruta)


def modulo(nombre: str):
    """Un módulo de midgaror, por su nombre.

    Es `importlib.import_module` con las rutas ya puestas. Se usa como
    función y no como `import` para que el handler no tenga que arrastrar el
    `# noqa: E402`: el preámbulo ya no está debajo de código, está aquí.
    """
    return importlib.import_module(nombre)
