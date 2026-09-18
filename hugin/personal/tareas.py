"""Gestor de tareas de un inquilino.

Portado de `diario/tareas/tareas.py` de midgaror (fase 4, ADR-024), con
las mismas cuatro costuras que ya usó `hugin/apuntes.py` y
`hugin/personal/habitos.py`:

- `ruta=` pasa a ser `inq=`. `diario/ubicacion.py` NO viaja; los datos
  son del inquilino, `inq.ruta`.
- `os.environ[BACKEND]` pasa a ser `_en_postgres(inq)`.
- `import postgres` pasa a ser `from hugin.guardado import postgres`, que
  ya tiene `cargar_tareas`/`guardar_tareas` con `inq`.
- `import fechas` pasa a ser `from hugin.personal import fechas` — es el
  mismo parser, copiado literal.

**La dirección se escribe, nunca se hereda del default.** `_cuando()` y
`aplazar()` llaman a `interpretar()`, que ya vale `hacia_atras=False` por
defecto — pero se pasa igual, explícito, porque una tarea habla de algo
por hacer: «médico mañana a las 10» tiene que resolver hacia delante, y
que quede escrito evita que cambiar el default de `interpretar()` el día
de mañana mueva esto sin que nadie se entere.

`_v0_a_v1` migra el fichero de tareas que hoy está en producción (bifrost,
Madre) — no es higiene, es la migración real. Va con `almacen.cargar(...,
migraciones=MIGRACIONES)` de la fase anterior.

Cada tarea:
    {"id": 1, "texto": "llamar al médico", "estado": "pendiente",
     "fecha": "2026-09-06", "hora": "10:00",
     "creada": "2026-09-05 17:10", "hecha_el": null}

`estado` es pendiente, en_proceso o hecha. Las borradas se quedan con
`borrada: true` y no se muestran; los ids no se reutilizan nunca.

`diario/tareas/` no se toca: sigue siendo lo que usa bifrost en Madre
hasta la fase 5.
"""

import os
from datetime import datetime
from pathlib import Path

from hugin.guardado import almacen
from hugin.personal import fechas
from hugin.personal.fechas import interpretar

FORMATO_FECHA = "%Y-%m-%d %H:%M"
ESTADOS = ("pendiente", "en_proceso", "hecha")
ICONO = {"pendiente": "○", "en_proceso": "◐", "hecha": "●"}

# v0: lista de tareas a pelo, algunas con "hecha": true/false y sin fecha.
# v1: lista de tareas con "estado", "fecha" y "hora", dentro del envoltorio
#     {"schemaVersion": 1, "datos": [...]}.
VERSION = 1
FICHERO = "tareas.json"


def _v0_a_v1(tareas: list[dict]) -> list[dict]:
    """El formato anterior a los estados, al de ahora.

    Las tareas escritas antes de los estados siguen en el fichero de
    producción y el bot las lee: se traducen al vuelo, sin tocar el disco
    hasta la siguiente escritura.
    """
    for t in tareas:
        if "estado" not in t:
            t["estado"] = "hecha" if t.pop("hecha", False) else "pendiente"
        t.setdefault("fecha", None)
        t.setdefault("hora", None)
    return tareas


MIGRACIONES = {0: _v0_a_v1}


def _en_postgres(inq) -> bool:
    from hugin.guardado import postgres as _p
    return bool(getattr(inq, "base", None)) or bool(os.environ.get(_p.VARIABLE, "").strip())


def _ruta(inq) -> Path:
    if inq is None:
        raise ValueError("no sé de quién son estas tareas: falta el inquilino")
    return inq.ruta / FICHERO


def cargar(inq=None) -> list[dict]:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        return postgres.cargar_tareas(inq)
    return almacen.cargar(_ruta(inq), VERSION, vacio=[], migraciones=MIGRACIONES)


def guardar(tareas: list[dict], inq=None) -> None:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        postgres.guardar_tareas(tareas, inq)
        return
    almacen.guardar(_ruta(inq), tareas, VERSION)


def _buscar(tareas: list[dict], id_tarea: int) -> dict:
    for t in tareas:
        if t["id"] == id_tarea and not t.get("borrada"):
            return t
    raise ValueError(f"no hay ninguna tarea con id {id_tarea}")


def activas(tareas: list[dict]) -> list[dict]:
    return [t for t in tareas if not t.get("borrada")]


def _cuando(texto: str, ahora: datetime | None) -> tuple[str, str | None, str | None]:
    """(texto sin la expresión temporal, fecha, hora). Sin expresión, todo queda como está."""
    encontrado = interpretar(texto, ahora, hacia_atras=False)
    if not encontrado:
        return texto.strip(), None, None
    fecha, hora, resto = encontrado
    return (resto.strip() or texto.strip()), fecha, hora


# ---- contrato con el bot ------------------------------------------------


def agregar(texto: str, inq=None, ahora: datetime | None = None) -> dict:
    """Crea una tarea. Si el texto dice cuándo ("mañana a las 10"), lo guarda como fecha."""
    if not texto.strip():
        raise ValueError("la tarea no puede estar vacía")
    limpio, fecha, hora = _cuando(texto, ahora)
    tareas = cargar(inq)
    nueva = {
        "id": max((t["id"] for t in tareas), default=0) + 1,
        "texto": limpio,
        "estado": "pendiente",
        "fecha": fecha,
        "hora": hora,
        "creada": (ahora or fechas.ahora()).strftime(FORMATO_FECHA),
        "hecha_el": None,
    }
    tareas.append(nueva)
    guardar(tareas, inq)
    return nueva


def _cambiar(id_tarea: int, inq, **cambios) -> dict:
    tareas = cargar(inq)
    tarea = _buscar(tareas, id_tarea)
    tarea.update(cambios)
    guardar(tareas, inq)
    return tarea


def empezar(id_tarea: int, inq=None) -> dict:
    """Marca una tarea como en proceso."""
    return _cambiar(id_tarea, inq, estado="en_proceso")


def hecha(id_tarea: int, inq=None, ahora: datetime | None = None) -> dict:
    """Marca una tarea como hecha. ValueError si el id no existe."""
    return _cambiar(id_tarea, inq, estado="hecha",
                    hecha_el=(ahora or fechas.ahora()).strftime(FORMATO_FECHA))


def reabrir(id_tarea: int, inq=None) -> dict:
    """Devuelve una tarea hecha o en proceso a pendiente."""
    return _cambiar(id_tarea, inq, estado="pendiente", hecha_el=None)


def editar(id_tarea: int, texto: str, inq=None, ahora: datetime | None = None) -> dict:
    """Cambia el texto. Si el texto nuevo dice cuándo, también la fecha."""
    if not texto.strip():
        raise ValueError("el texto no puede quedar vacío")
    limpio, fecha, hora = _cuando(texto, ahora)
    cambios = {"texto": limpio}
    if fecha:
        cambios.update(fecha=fecha, hora=hora)
    return _cambiar(id_tarea, inq, **cambios)


def aplazar(id_tarea: int, cuando: str, inq=None, ahora: datetime | None = None) -> dict:
    """Pone o cambia la fecha: aplazar(3, "al lunes por la tarde")."""
    encontrado = interpretar(cuando, ahora, hacia_atras=False)
    if not encontrado:
        raise ValueError(
            f"no entiendo cuándo es {cuando!r}: prueba «mañana», «el lunes», «el 15 de octubre»")
    fecha, hora, _ = encontrado
    return _cambiar(id_tarea, inq, fecha=fecha, hora=hora)


def borrar(id_tarea: int, inq=None) -> dict:
    """Retira una tarea de las listas. ValueError si el id no existe.

    No se elimina del fichero: se marca `borrada` y deja de salir. Así los
    ids no se reutilizan nunca y el historial queda entero, que para esto
    es un diario.
    """
    tareas = cargar(inq)
    tarea = _buscar(tareas, id_tarea)
    tarea["borrada"] = True
    guardar(tareas, inq)
    return tarea


def _linea(t: dict, hoy: str | None = None) -> str:
    cuando = ""
    if t.get("fecha"):
        etiqueta = "hoy" if t["fecha"] == hoy else t["fecha"]
        cuando = f" · {etiqueta}" + (f" {t['hora']}" if t.get("hora") else "")
        if hoy and t["fecha"] < hoy and t["estado"] != "hecha":
            cuando += " ⚠️ vencida"
    return f"  {ICONO[t['estado']]} [{t['id']}] {t['texto']}{cuando}"


def _orden(t: dict) -> tuple:
    return (t.get("fecha") or "9999-99-99", t.get("hora") or "99:99", t["id"])


def del_dia(fecha: str | None = None, inq=None) -> list[dict]:
    """Tareas abiertas con fecha ese día, o vencidas antes; para /hoy."""
    fecha = fecha or fechas.hoy()
    return sorted((t for t in activas(cargar(inq))
                   if t["estado"] != "hecha" and t.get("fecha") and t["fecha"] <= fecha), key=_orden)


def resumen(inq=None, hechas_recientes: int = 5, hoy: str | None = None) -> str:
    """Texto con lo abierto (en proceso primero, luego pendientes por fecha) y las últimas hechas."""
    hoy = hoy or fechas.hoy()
    tareas = activas(cargar(inq))
    if not tareas:
        return "No hay tareas. Apunta una con: /tarea comprar el pan"

    en_proceso = sorted((t for t in tareas if t["estado"] == "en_proceso"), key=_orden)
    pendientes = sorted((t for t in tareas if t["estado"] == "pendiente"), key=_orden)
    hechas = [t for t in tareas if t["estado"] == "hecha"]
    lineas = []
    if en_proceso:
        lineas.append(f"◐ En proceso ({len(en_proceso)}):")
        lineas += [_linea(t, hoy) for t in en_proceso]
    if pendientes:
        lineas.append(f"○ Pendientes ({len(pendientes)}):")
        lineas += [_linea(t, hoy) for t in pendientes]
    if not en_proceso and not pendientes:
        lineas.append("○ Sin tareas abiertas.")
    if hechas:
        lineas.append(f"● Hechas ({len(hechas)}), últimas:")
        lineas += [_linea(t) for t in hechas[-hechas_recientes:]]
    return "\n".join(lineas)
