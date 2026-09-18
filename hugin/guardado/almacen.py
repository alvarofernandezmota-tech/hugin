"""Leer y escribir los JSON de gjallarhorn. El único sitio que toca el disco.

Propio y no prestado: gjallarhorn no depende de nada. Son treinta líneas y el
precio de reimplementarlas es menor que el de arrastrar otro repo entero para
guardar una lista.

Dos cosas que no son adorno:

**Versión de esquema.** El documento en disco es
`{"schemaVersion": 1, "datos": [...]}`. El día que cambie el formato, el código
viejo lo verá y dirá que no lo entiende en vez de leerlo mal.

**Escritura atómica.** Se escribe a un temporal en la misma carpeta y se
renombra. `open(ruta, "w")` trunca el fichero antes de escribir: si el proceso
muere ahí —y esto va a correr atendiendo llamadas— el registro de llamadas se
queda en cero bytes. El rename es una operación sola: o está lo viejo o está
lo nuevo.
"""

import json
import os
import tempfile
from pathlib import Path

CLAVE_VERSION = "schemaVersion"
CLAVE_DATOS = "datos"


def escribir(ruta: Path, texto: str) -> None:
    """Deja `texto` en `ruta` de una pieza, o no lo deja."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # En la MISMA carpeta: un rename entre sistemas de archivos no es atómico.
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destino:
            destino.write(texto)
            destino.flush()
            os.fsync(destino.fileno())
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise


def cargar(ruta: Path, version: int, vacio, migraciones: dict | None = None):
    """Los datos del fichero. Sin fichero, una copia de `vacio`.

    `migraciones` es opcional y aditivo — de la fase 4 del ADR-024, portado
    de `diario/almacen.py` de midgaror. Sin él, el comportamiento de
    siempre: un fichero de una versión distinta se lee tal cual, sin
    intentar migrarlo. Con `{version_de_origen: función}`, se aplican en
    orden hasta llegar a `version`. Hace falta de verdad, no por higiene:
    `_v0_a_v1` de `diario/tareas/tareas.py` migra el fichero de tareas que
    hoy está en producción; sin esto, portar ese modelo aquí perdería la
    migración.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return json.loads(json.dumps(vacio))

    texto = ruta.read_text(encoding="utf-8")
    try:
        documento = json.loads(texto)
    except json.JSONDecodeError as error:
        # Un JSON roto tiene que decir cuál es y cómo recuperarlo, no salir
        # como un error críptico en mitad de una llamada.
        copia = ruta.with_name(ruta.name + ".corrupto")
        if not copia.exists():
            try:
                copia.write_text(texto, encoding="utf-8")
            except OSError:
                copia = None
        donde = f" Copia del roto en {copia.name}." if copia else ""
        raise ValueError(
            f"{ruta.name} no es JSON válido: {error.msg}, línea {error.lineno}, "
            f"columna {error.colno}.{donde}") from error

    if isinstance(documento, dict) and CLAVE_VERSION in documento:
        encontrada = int(documento[CLAVE_VERSION])
        datos = documento.get(CLAVE_DATOS, json.loads(json.dumps(vacio)))
    else:
        # Sin envoltorio: formato viejo (versión 0), se envolverá al guardar.
        encontrada, datos = 0, documento

    if encontrada > version:
        raise ValueError(
            f"{ruta.name}: el fichero es del esquema {encontrada} y este "
            f"código entiende hasta el {version}. Actualiza gjallarhorn.")

    if migraciones is None:
        # El comportamiento de siempre: nadie ha dicho cómo migrar, así que
        # no se intenta. Sin esto, portar `migraciones` rompería a todo
        # llamador existente que no lo conoce.
        return datos

    while encontrada < version:
        migrar = migraciones.get(encontrada)
        if migrar is None:
            raise ValueError(
                f"{ruta.name}: falta la migración del esquema {encontrada} al "
                f"{encontrada + 1}")
        datos = migrar(datos)
        encontrada += 1
    return datos


def guardar(ruta: Path, datos, version: int, ordenar_claves: bool = False) -> None:
    """Escribe `{"schemaVersion": version, "datos": datos}`, de una pieza.

    `ordenar_claves` existe por `habitos.json` (fase 4, ADR-024): va
    indexado por fecha, y sin orden estable cada escritura cambia el
    fichero entero, y el `git commit` que hace el bot en cada mensaje sale
    con un diff ilegible (ADR-013).
    """
    documento = {CLAVE_VERSION: version, CLAVE_DATOS: datos}
    texto = json.dumps(documento, ensure_ascii=False, indent=2, sort_keys=ordenar_claves)
    escribir(Path(ruta), texto + "\n")
