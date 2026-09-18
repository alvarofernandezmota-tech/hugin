"""Los registros de un inquilino, en su propia base de Postgres.

Esto es a las tablas lo que `almacen.py` es a los JSON: el unico sitio que
habla con la base. El esquema y los adaptadores vienen del ADR-023, donde ya
corren en produccion contra PostgreSQL 18.6; lo que cambia aqui es **de donde
sale la conexion**.

## Una base por inquilino, y no una columna

La separacion entre inquilinos no es un `WHERE` que alguien pueda olvidar: es
una base distinta, elegida por el inquilino (ADR-024). Leer lo de otro pasa de
ser un descuido posible a ser imposible.

    conectar(inq)     # la base que dice su inquilino.toml
    conectar()        # la del entorno: lo que hay hoy

Sin `base` en su fichero se usa `DIARIO_DATABASE_URL`, que es como funciona el
bot ahora mismo. Por eso esto no rompe nada mientras no se le de a nadie su
fichero.

## Por que se reescribe la tabla entera al guardar

`guardar_*` vacia su tabla y la vuelve a escribir dentro de una transaccion,
en vez de hacer UPSERT fila a fila. No es descuido: el contrato de `guardar()`
es «esta lista es toda la verdad», igual que cuando se escribia el fichero
completo. Un UPSERT obligaria a decidir aqui que significa que una fila ya no
este en la lista, y esa decision es del modelo —`tareas.borrar()` marca
`borrada`, no quita la tarea—, no de esta capa.
"""

from contextlib import contextmanager
from datetime import date, datetime, time
import os

VARIABLE = "DIARIO_DATABASE_URL"
FORMATO_FECHA = "%Y-%m-%d %H:%M"


def _psycopg():
    """psycopg, importado bajo demanda — no al cargar este módulo.

    Antes `import psycopg` estaba a la cabeza del fichero, así que
    `_en_postgres(inq)` de `tareas.py`/`citas.py`/`habitos.py`/`apuntes.py`
    —que solo necesita leer `VARIABLE`, la constante de arriba, para saber
    si hay que mirar Postgres— tumbaba la importación **entera** del módulo
    en cualquier inquilino de fichero sin psycopg instalado. Medido en
    Madre el 2026-09-18: el venv de `telegram/` no lleva el extra
    `[postgres]` a propósito (un inquilino de fichero no lo necesita), y
    `tareas.cargar()` de ese inquilino reventaba igual, sin haber tocado
    Postgres para nada.
    """
    try:
        import psycopg
        from psycopg.rows import dict_row
        # Explícito a propósito: `psycopg.types.json` se carga de rebote al
        # registrar los adaptadores por defecto, pero depender de eso es
        # depender de un detalle interno de psycopg que puede cambiar de
        # versión.
        from psycopg.types.json import Json
    except ImportError as error:  # pragma: no cover - depende del entorno
        raise ImportError(
            "los registros en Postgres necesitan psycopg, que no esta "
            "instalado: pip install -e \".[postgres]\""
        ) from error
    return psycopg, dict_row, Json

TABLAS = (
    """
    CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY,
        texto TEXT NOT NULL,
        estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'en_proceso', 'hecha')),
        fecha DATE,
        hora TIME,
        creada TIMESTAMP NOT NULL,
        hecha_el TIMESTAMP,
        borrada BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS citas (
        id INTEGER PRIMARY KEY,
        texto TEXT NOT NULL,
        fecha DATE NOT NULL,
        hora TIME,
        duracion INTEGER NOT NULL DEFAULT 60,
        creada TIMESTAMP NOT NULL,
        cancelada BOOLEAN NOT NULL DEFAULT FALSE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS habitos_registro (
        fecha DATE NOT NULL,
        habito TEXT NOT NULL,
        valor JSONB NOT NULL,
        PRIMARY KEY (fecha, habito)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS apuntes (
        id BIGSERIAL PRIMARY KEY,
        fecha DATE NOT NULL,
        que TEXT NOT NULL,
        valor NUMERIC,
        unidad TEXT,
        hora TEXT
    )
    """,
)


def url(inq=None) -> str:
    """La base de ese inquilino. Sin inquilino o sin `base`, la del entorno.

    El orden es el que no rompe nada: manda el inquilino cuando lo dice, y si
    no, sigue valiendo la variable de siempre.
    """
    del_inquilino = getattr(inq, "base", None)
    if del_inquilino:
        return del_inquilino
    valor = os.environ.get(VARIABLE, "").strip()
    if not valor:
        quien = f" para {inq.nombre}" if inq is not None else ""
        raise RuntimeError(
            f"no se de que base leer{quien}: ni su inquilino.toml dice `base` "
            f"ni hay {VARIABLE} en el entorno")
    return valor


@contextmanager
def conectar(inq=None):
    psycopg, dict_row, _ = _psycopg()
    with psycopg.connect(url(inq), row_factory=dict_row) as conn:
        yield conn


def inicializar_esquema(inq=None) -> None:
    """Crea las tablas si no existen. Idempotente: se puede llamar en cada arranque."""
    with conectar(inq) as conn:
        for tabla in TABLAS:
            conn.execute(tabla)
        conn.commit()


# ---- helpers de fecha/hora -------------------------------------------------
#
# En los JSON, fecha y hora son strings ("2026-09-06", "10:00"); en Postgres
# son columnas DATE/TIME de verdad. Estas funciones son el único sitio que
# convierte entre las dos formas, en los dos sentidos.


def _a_fecha(valor: str | None) -> date | None:
    return date.fromisoformat(valor) if valor else None


def _de_fecha(valor: date | None) -> str | None:
    return valor.isoformat() if valor else None


def _a_hora(valor: str | None) -> time | None:
    return time.fromisoformat(valor) if valor else None


def _de_hora(valor: time | None) -> str | None:
    return valor.strftime("%H:%M") if valor else None


def _a_marca_temporal(valor: str | None) -> datetime | None:
    return datetime.strptime(valor, FORMATO_FECHA) if valor else None


def _de_marca_temporal(valor: datetime | None) -> str | None:
    return valor.strftime(FORMATO_FECHA) if valor else None


# ---- tareas -----------------------------------------------------------------


def cargar_tareas(inq=None) -> list[dict]:
    with conectar(inq) as conn:
        filas = conn.execute(
            "SELECT id, texto, estado, fecha, hora, creada, hecha_el, borrada "
            "FROM tareas ORDER BY id"
        ).fetchall()
    return [
        {
            "id": f["id"],
            "texto": f["texto"],
            "estado": f["estado"],
            "fecha": _de_fecha(f["fecha"]),
            "hora": _de_hora(f["hora"]),
            "creada": _de_marca_temporal(f["creada"]),
            "hecha_el": _de_marca_temporal(f["hecha_el"]),
            **({"borrada": True} if f["borrada"] else {}),
        }
        for f in filas
    ]


def guardar_tareas(tareas: list[dict], inq=None) -> None:
    with conectar(inq) as conn:
        conn.execute("TRUNCATE tareas")
        for t in tareas:
            conn.execute(
                "INSERT INTO tareas (id, texto, estado, fecha, hora, creada, hecha_el, borrada) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    t["id"], t["texto"], t["estado"],
                    _a_fecha(t.get("fecha")), _a_hora(t.get("hora")),
                    _a_marca_temporal(t["creada"]), _a_marca_temporal(t.get("hecha_el")),
                    bool(t.get("borrada", False)),
                ),
            )
        conn.commit()


# ---- agenda (citas) ----------------------------------------------------------


def cargar_citas(inq=None) -> list[dict]:
    with conectar(inq) as conn:
        filas = conn.execute(
            "SELECT id, texto, fecha, hora, duracion, creada, cancelada "
            "FROM citas ORDER BY id"
        ).fetchall()
    return [
        {
            "id": f["id"],
            "texto": f["texto"],
            "fecha": _de_fecha(f["fecha"]),
            "hora": _de_hora(f["hora"]),
            "duracion": f["duracion"],
            "creada": _de_marca_temporal(f["creada"]),
            **({"cancelada": True} if f["cancelada"] else {}),
        }
        for f in filas
    ]


def guardar_citas(citas: list[dict], inq=None) -> None:
    with conectar(inq) as conn:
        conn.execute("TRUNCATE citas")
        for c in citas:
            conn.execute(
                "INSERT INTO citas (id, texto, fecha, hora, duracion, creada, cancelada) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    c["id"], c["texto"], _a_fecha(c["fecha"]), _a_hora(c.get("hora")),
                    c["duracion"], _a_marca_temporal(c["creada"]),
                    bool(c.get("cancelada", False)),
                ),
            )
        conn.commit()


# ---- hábitos ------------------------------------------------------------------
#
# `habitos.cargar()`/`guardar()` trabajan con un dict {fecha: {habito: marca}},
# no con una lista: se reconstruye aquí desde las filas (fecha, habito, valor).


def cargar_habitos(inq=None) -> dict:
    with conectar(inq) as conn:
        filas = conn.execute("SELECT fecha, habito, valor FROM habitos_registro").fetchall()
    datos: dict = {}
    for f in filas:
        datos.setdefault(_de_fecha(f["fecha"]), {})[f["habito"]] = f["valor"]
    return datos


def guardar_habitos(datos: dict, inq=None) -> None:
    _, _, Json = _psycopg()
    with conectar(inq) as conn:
        conn.execute("TRUNCATE habitos_registro")
        for fecha, registro in datos.items():
            for habito, valor in registro.items():
                conn.execute(
                    "INSERT INTO habitos_registro (fecha, habito, valor) VALUES (%s, %s, %s)",
                    (_a_fecha(fecha), habito, Json(valor)),
                )
        conn.commit()


# ---- registro (apuntes) --------------------------------------------------------


def cargar_apuntes(inq=None) -> list[dict]:
    with conectar(inq) as conn:
        filas = conn.execute(
            "SELECT fecha, que, valor, unidad, hora FROM apuntes ORDER BY id"
        ).fetchall()
    apuntes = []
    for f in filas:
        apunte = {"fecha": _de_fecha(f["fecha"]), "que": f["que"]}
        if f["valor"] is not None:
            numero = float(f["valor"])
            apunte["valor"] = int(numero) if numero == int(numero) else numero
        if f["unidad"]:
            apunte["unidad"] = f["unidad"]
        if f["hora"]:
            apunte["hora"] = f["hora"]
        apuntes.append(apunte)
    return apuntes


def guardar_apuntes(apuntes: list[dict], inq=None) -> None:
    with conectar(inq) as conn:
        conn.execute("TRUNCATE apuntes")
        for a in apuntes:
            conn.execute(
                "INSERT INTO apuntes (fecha, que, valor, unidad, hora) VALUES (%s, %s, %s, %s, %s)",
                (_a_fecha(a["fecha"]), a["que"], a.get("valor"), a.get("unidad"), a.get("hora")),
            )
        conn.commit()
