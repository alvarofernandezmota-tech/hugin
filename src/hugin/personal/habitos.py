"""Registro de hábitos diarios de un inquilino.

Portado de `diario/habitos/habitos.py` de midgaror (fase 4, ADR-024), con
las mismas cuatro costuras que ya usó `hugin/apuntes.py`:

- `ruta=` pasa a ser `inq=`: `_ruta(inq)` en vez de `_ruta(ruta)`.
  `diario/ubicacion.py` NO viaja (ancla los datos con `__file__`, y esta
  librería vive dentro de la aplicación que la usa); los datos son del
  inquilino, `inq.ruta`.
- `os.environ[BACKEND]` pasa a ser `_en_postgres(inq)`: manda `inq.base`,
  y si no lo tiene, la variable de entorno — que es como corre el bot hoy
  mientras nadie tenga todavía su `inquilino.toml`.
- `import postgres` pasa a ser `from hugin.guardado import postgres`, que
  ya tiene `cargar_habitos`/`guardar_habitos` con `inq`.
- `import fechas` pasa a ser `from hugin.personal import fechas`: es el
  mismo parser, copiado literal (ver `hugin/personal/__init__.py`).

La dirección se conserva tal cual, escrita y con su motivo: un hábito se
apunta DESPUÉS de haberlo hecho, así que «el lunes» es el lunes que ya
pasó.

Los datos viven en `apuntes.json`... no, en `habitos.json`
({"schemaVersion": 1, "datos": {...}}), con un registro por día:
    {"2026-09-04": {"deporte": true, "meditar": false, "energia": 7}}

Un hábito se apunta de dos maneras: **sí o no** (`deporte`, `meditar`) o con
un **valor del 1 al 10** (`energia`, `foco`, `animo`). El mismo hábito puede
pasar de una forma a otra sin romper nada: lo que hay escrito se lee tal
cual.

`diario/habitos/` no se toca: sigue siendo lo que usa bifrost en Madre
hasta la fase 5.
"""

import os
import re
from datetime import date, timedelta
from pathlib import Path

from hugin.guardado import almacen
from hugin.personal import fechas

VERSION = 1
FICHERO = "habitos.json"
NOMBRE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")
VALOR_MIN, VALOR_MAX = 1, 10

# v0: diccionario por fecha a pelo. v1: el mismo, dentro del envoltorio. El
# registro no cambia de forma entre versiones; se conserva por si algún
# fichero viejo llega sin envolver.
MIGRACIONES = {0: lambda datos: datos}


def _en_postgres(inq) -> bool:
    from hugin.guardado import postgres as _p
    return bool(getattr(inq, "base", None)) or bool(os.environ.get(_p.VARIABLE, "").strip())


def _ruta(inq) -> Path:
    if inq is None:
        raise ValueError("no sé de quién son estos hábitos: falta el inquilino")
    return inq.ruta / FICHERO


def cargar(inq=None) -> dict:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        return postgres.cargar_habitos(inq)
    return almacen.cargar(_ruta(inq), VERSION, vacio={}, migraciones=MIGRACIONES)


def guardar(datos: dict, inq=None) -> None:
    if _en_postgres(inq):
        from hugin.guardado import postgres
        postgres.guardar_habitos(datos, inq)
        return
    # ordenar_claves porque el registro va indexado por fecha: sin orden
    # estable, cada escritura cambia el fichero entero y el commit que hace
    # el bot en cada mensaje sale con un diff ilegible (ADR-013).
    almacen.guardar(_ruta(inq), datos, VERSION, ordenar_claves=True)


def normalizar_nombre(nombre: str) -> str:
    """Minúsculas, sin espacios: 'Deporte' y 'deporte' son el mismo hábito."""
    limpio = nombre.strip().lower().replace(" ", "-")
    if not NOMBRE_RE.match(limpio):
        raise ValueError(f"nombre de hábito no válido: {nombre!r} (letras, números, - o _)")
    return limpio


def normalizar_fecha(fecha: str | None) -> str:
    """«ayer», «el lunes», «2026-09-05»: lo resuelve `hugin.personal.fechas`.

    Hacia atrás, porque un hábito se apunta después de hacerlo: «el lunes»
    es el lunes que ya pasó.
    """
    return fechas.normalizar(fecha, hacia_atras=True)


def normalizar_valor(valor) -> int:
    """Un valor de hábito es un entero del 1 al 10."""
    try:
        numero = int(str(valor).strip())
    except (TypeError, ValueError):
        raise ValueError(
            f"valor no válido: {valor!r} (un número del {VALOR_MIN} al {VALOR_MAX})") from None
    if not VALOR_MIN <= numero <= VALOR_MAX:
        raise ValueError(f"valor fuera de rango: {numero} (del {VALOR_MIN} al {VALOR_MAX})")
    return numero


def es_valor(marca) -> bool:
    """True si la marca es un número y no un sí/no. Ojo: en Python True es 1."""
    return isinstance(marca, int) and not isinstance(marca, bool)


def formato(marca) -> str:
    """Cómo se enseña una marca: ✅/❌ si es sí o no, el número si es valor."""
    return str(marca) if es_valor(marca) else ("✅" if marca else "❌")


# ---- contrato con el bot ------------------------------------------------


def marcar(nombre: str, hecho: bool = True, fecha: str | None = None,
           inq=None, valor=None) -> tuple[str, str, bool | int]:
    """Apunta un hábito en una fecha (hoy por defecto).

    Sin `valor`, se apunta como hecho o no hecho. Con `valor`, se guarda el
    número del 1 al 10 en su lugar: marcar("energia", valor=7).
    """
    nombre = normalizar_nombre(nombre)
    fecha = normalizar_fecha(fecha)
    marca = hecho if valor is None else normalizar_valor(valor)
    datos = cargar(inq)
    datos.setdefault(fecha, {})[nombre] = marca
    guardar(datos, inq)
    return fecha, nombre, marca


def habitos_conocidos(datos: dict) -> list[str]:
    """Todos los hábitos que se han apuntado alguna vez, ordenados."""
    return sorted({h for registro in datos.values() for h in registro})


def resumen_dia(fecha: str | None = None, inq=None) -> str:
    fecha = normalizar_fecha(fecha)
    registro = cargar(inq).get(fecha, {})
    if not registro:
        return f"Sin hábitos apuntados el {fecha}."
    lineas = [f"{fecha}:"] + [f"  {formato(v)} {h}" for h, v in sorted(registro.items())]
    return "\n".join(lineas)


def resumen_semana(fecha: str | None = None, inq=None) -> str:
    """Los siete días que terminan en `fecha`, y cuántas veces salió cada hábito."""
    fin = date.fromisoformat(normalizar_fecha(fecha))
    datos = cargar(inq)
    dias = [(fin - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    conocidos = habitos_conocidos({d: datos.get(d, {}) for d in dias})
    if not conocidos:
        return f"Sin hábitos apuntados entre el {dias[0]} y el {dias[-1]}."

    lineas = [f"Semana del {dias[0]} al {dias[-1]}:"]
    for d in dias:
        registro = datos.get(d, {})
        marcas = "  ".join(f"{h}:{formato(registro[h])}" for h in conocidos if h in registro)
        lineas.append(f"  {d}  {marcas or '—'}")
    lineas.append("Totales:")
    for h in conocidos:
        apuntadas = [datos[d][h] for d in dias if h in datos.get(d, {})]
        valores = [m for m in apuntadas if es_valor(m)]
        if valores:
            # Un hábito puede haber cambiado de sí/no a valor: manda el número.
            media = sum(valores) / len(valores)
            lineas.append(f"  {h}: media {media:.1f} en {len(valores)} de {len(dias)} días")
        else:
            cumplidos = sum(1 for m in apuntadas if m)
            lineas.append(f"  {h}: {cumplidos}/{len(apuntadas)} días apuntados")
    return "\n".join(lineas)
