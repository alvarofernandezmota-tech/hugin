"""Agenda de citas de un inquilino — no de un negocio.

Portado de `diario/agenda/agenda.py` de midgaror (fase 4, ADR-024). Se
llama **`citas`**, no `agenda`: ya existe `hugin/negocio/agenda.py`, la
agenda de reserva de un negocio (huecos contra un horario), y un nombre que
no puede colisionar por accidente no se funde por descuido. Son módulos
distintos a propósito — ver `hugin/personal/__init__.py`.

Mismas cuatro costuras que `apuntes.py`, `personal/habitos.py` y
`personal/tareas.py`: `ruta=` → `inq=`, `BACKEND` → `_en_postgres(inq)`,
`postgres` desde `hugin.guardado` (ya tiene `cargar_citas`/`guardar_citas`
con `inq`), `fechas` desde `hugin.personal`.

**La dirección se escribe en los cinco sitios que resuelven, nunca se
hereda del default**: `agregar()` y `mover()` llaman `interpretar()`;
`del_dia()`, `de_la_semana()` y `resumen()` llaman `normalizar()`. Los
cinco con `hacia_atras=False` explícito — una cita habla de algo por
venir, nunca de algo que ya pasó.

Cada cita:
    {"id": 1, "texto": "médico", "fecha": "2026-09-06", "hora": "10:00",
     "duracion": 60, "creada": "2026-09-05 17:10"}

Una cita **siempre tiene fecha**: es lo que la separa de una tarea. La hora
es opcional: sin ella la cita es de todo el día. `duracion` está en minutos
y solo sirve para avisar de choques de horario; las canceladas se quedan
con `cancelada: true`.

`diario/agenda/` no se toca: sigue siendo lo que usa bifrost en Madre
hasta la fase 5.
"""

import os
from datetime import date, datetime, timedelta
from pathlib import Path

from hugin.guardado import almacen
from hugin.personal import fechas
from hugin.personal.fechas import interpretar, normalizar

FORMATO_FECHA = "%Y-%m-%d %H:%M"
DURACION_POR_DEFECTO = 60  # minutos

# v0: lista de citas a pelo. v1: la misma lista, dentro del envoltorio. La
# cita no cambia de forma entre versiones; se conserva por si algún fichero
# viejo llega sin envolver.
VERSION = 1
FICHERO = "citas.json"
MIGRACIONES = {0: lambda citas: citas}


def _en_postgres(inq) -> bool:
    from hugin.guardado import postgres as _p
    return bool(getattr(inq, "base", None)) or bool(os.environ.get(_p.VARIABLE, "").strip())


def _ruta(inq) -> Path:
    if inq is None:
        raise ValueError("no sé de quién son estas citas: falta el inquilino")
    return inq.ruta / FICHERO


def cargar(inq=None) -> list[dict]:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        return postgres.cargar_citas(inq)
    return almacen.cargar(_ruta(inq), VERSION, vacio=[], migraciones=MIGRACIONES)


def guardar(citas: list[dict], inq=None) -> None:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        postgres.guardar_citas(citas, inq)
        return
    almacen.guardar(_ruta(inq), citas, VERSION)


def activas(citas: list[dict]) -> list[dict]:
    return [c for c in citas if not c.get("cancelada")]


def _buscar(citas: list[dict], id_cita: int) -> dict:
    for c in citas:
        if c["id"] == id_cita and not c.get("cancelada"):
            return c
    raise ValueError(f"no hay ninguna cita con id {id_cita}")


def _minutos(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def _orden(c: dict) -> tuple:
    return (c["fecha"], c.get("hora") or "00:00", c["id"])


def choques(cita: dict, citas: list[dict]) -> list[dict]:
    """Citas del mismo día cuyo horario se solapa con `cita`.

    Sin hora la cita es de todo el día y no choca con nada: avisar de que
    "dentista (todo el día)" pisa al médico de las 10 sería ruido.
    """
    if not cita.get("hora"):
        return []
    inicio = _minutos(cita["hora"])
    fin = inicio + (cita.get("duracion") or DURACION_POR_DEFECTO)
    solapan = []
    for otra in activas(citas):
        if otra["id"] == cita["id"] or otra["fecha"] != cita["fecha"] or not otra.get("hora"):
            continue
        otro_inicio = _minutos(otra["hora"])
        otro_fin = otro_inicio + (otra.get("duracion") or DURACION_POR_DEFECTO)
        if inicio < otro_fin and otro_inicio < fin:
            solapan.append(otra)
    return sorted(solapan, key=_orden)


# ---- contrato con el bot ------------------------------------------------


def agregar(texto: str, inq=None, ahora: datetime | None = None,
            duracion: int | None = None) -> tuple[dict, list[dict]]:
    """Crea una cita a partir del texto. Devuelve (cita, choques de horario).

    El aviso de choque no impide guardarla: dos cosas a la misma hora
    pasan, y quien decide qué hacer es el inquilino, no el programa.
    """
    if not texto.strip():
        raise ValueError("la cita no puede estar vacía")
    encontrado = interpretar(texto, ahora, hacia_atras=False)
    if not encontrado:
        raise ValueError(
            "una cita necesita cuándo es: prueba «médico mañana a las 10», "
            "«dentista el 15 de octubre a las 17:30»")
    fecha, hora, acotada, resto = encontrado
    citas = cargar(inq)
    nueva = {
        "id": max((c["id"] for c in citas), default=0) + 1,
        "texto": resto.strip() or texto.strip(),
        "fecha": fecha,
        "hora": hora,
        # «a las cinco» sin mañana/tarde/noche: se guarda tal cual (nunca se
        # inventa una franja), pero se marca para que quien pregunte por ella
        # pueda pedir que se confirme, en vez de asumir que son las 05:00.
        "hora_sin_confirmar": fechas.hora_ambigua(hora, acotada),
        "duracion": duracion or DURACION_POR_DEFECTO,
        "creada": (ahora or fechas.ahora()).strftime(FORMATO_FECHA),
    }
    solapan = choques(nueva, citas)
    citas.append(nueva)
    guardar(citas, inq)
    return nueva, solapan


def mover(id_cita: int, cuando: str, inq=None, ahora: datetime | None = None) -> tuple[dict, list[dict]]:
    """Cambia la fecha o la hora: mover(3, "el lunes a las 17")."""
    encontrado = interpretar(cuando, ahora, hacia_atras=False)
    if not encontrado:
        raise ValueError(
            f"no entiendo cuándo es {cuando!r}: prueba «mañana a las 10», «el 15 de octubre»")
    fecha, hora, acotada, _ = encontrado
    citas = cargar(inq)
    cita = _buscar(citas, id_cita)
    cita["fecha"], cita["hora"] = fecha, hora
    cita["hora_sin_confirmar"] = fechas.hora_ambigua(hora, acotada)
    solapan = choques(cita, citas)
    guardar(citas, inq)
    return cita, solapan


def confirmar_hora(id_cita: int, franja: str, inq=None) -> dict:
    """Aplica la franja que faltaba a una cita con `hora_sin_confirmar`.

    Es la respuesta a «¿de la mañana o de la tarde?»: no se vuelve a
    interpretar la frase entera, solo se ajusta la hora que ya había con
    `fechas.acotar()`. `ValueError` si la cita no tenía nada pendiente —
    aplicar una franja a una hora ya confirmada sería adivinar por su cuenta,
    justo lo que esto existe para no hacer.
    """
    citas = cargar(inq)
    cita = _buscar(citas, id_cita)
    if not cita.get("hora_sin_confirmar"):
        raise ValueError(f"la cita {id_cita} no tiene ninguna hora por confirmar")
    cita["hora"] = fechas.acotar(cita["hora"], franja)
    cita["hora_sin_confirmar"] = False
    solapan = choques(cita, citas)
    guardar(citas, inq)
    return cita, solapan


def cancelar(id_cita: int, inq=None) -> dict:
    """Retira una cita. Como en tareas, no se borra: los ids no se reutilizan."""
    citas = cargar(inq)
    cita = _buscar(citas, id_cita)
    cita["cancelada"] = True
    guardar(citas, inq)
    return cita


def del_dia(fecha: str | None = None, inq=None) -> list[dict]:
    """Citas de ese día, por hora; las de todo el día primero. Para /hoy."""
    fecha = normalizar(fecha, hacia_atras=False)  # «mañana», «el lunes», «2026-09-07»
    return sorted((c for c in activas(cargar(inq)) if c["fecha"] == fecha), key=_orden)


def de_la_semana(fecha: str | None = None, inq=None) -> list[dict]:
    """Citas de los siete días que empiezan en `fecha` (hoy incluido)."""
    inicio = date.fromisoformat(normalizar(fecha, hacia_atras=False))
    fin = (inicio + timedelta(days=6)).isoformat()
    return sorted((c for c in activas(cargar(inq))
                   if inicio.isoformat() <= c["fecha"] <= fin), key=_orden)


def linea(c: dict, con_fecha: bool = False) -> str:
    cuando = f"{c['fecha']} " if con_fecha else ""
    cuando += c["hora"] if c.get("hora") else "todo el día"
    if c.get("hora_sin_confirmar"):
        cuando += " (¿mañana o tarde?)"
    return f"  📅 [{c['id']}] {cuando} · {c['texto']}"


def resumen(fecha: str | None = None, inq=None, semana: bool = False) -> str:
    """Texto con las citas del día o de la semana."""
    fecha = normalizar(fecha, hacia_atras=False)
    if not semana:
        citas = del_dia(fecha, inq)
        if not citas:
            return f"Sin citas el {fecha}. Apunta una con: /cita médico mañana a las 10"
        return "\n".join([f"Citas del {fecha}:"] + [linea(c) for c in citas])

    citas = de_la_semana(fecha, inq)
    fin = (date.fromisoformat(fecha) + timedelta(days=6)).isoformat()
    if not citas:
        return f"Sin citas entre el {fecha} y el {fin}."
    lineas = [f"Citas del {fecha} al {fin}:"]
    dia = None
    for c in citas:
        if c["fecha"] != dia:
            dia = c["fecha"]
            lineas.append(f"{dia}:")
        lineas.append(linea(c))
    return "\n".join(lineas)


def aviso_choques(solapan: list[dict]) -> str:
    """Una línea de aviso, o cadena vacía si no hay choque."""
    if not solapan:
        return ""
    cuales = ", ".join(f"[{c['id']}] {c['texto']} a las {c['hora']}" for c in solapan)
    return f"⚠️ Choca con {cuales}"
