"""La prosa del diario: el único camino de escritura sin abrir editor.

Portado de `diario/organizar_diario.py` y `diario/bifrost_bridge.py` de
midgaror (ADR-009, ADR-024 fase 5), fundidos en un módulo: `bifrost_bridge`
era un envoltorio fino sobre `organizar_texto`/`ruta_de_fecha`/`ruta_de_hoy`
—dos funciones, sin lógica propia—, así que no hacía falta un segundo
fichero aparte del que ya tiene la lógica de verdad.

## Por qué esto no lleva `inq=`

Los otros modelos personales (`tareas`, `citas`, `habitos`, `apuntes`)
convirtieron su `ruta=` (una carpeta base) en `inq=` (un `Inquilino`, que
sabe además si toca Postgres). Aquí `ruta=` ya significaba otra cosa —el
fichero EXACTO de una entrada, para las pruebas y para `/entrada --output`—
y nunca hubo una carpeta base que renombrar: en midgaror este módulo no
sabía que existían varios inquilinos, tenía UNA carpeta fija a nivel de
módulo (`CARPETA_PERSONAL`). Eso sigue igual aquí, a propósito: sin
Postgres para la prosa (ADR-024 dice que el texto se queda siempre en
Markdown) no hay nada que `inq.base` fuera a decidir, y forzarle un `inq=`
solo por seguir el patrón de los otros cuatro sería inventar una costura
que no hace ninguna falta — es justo la trampa que ADR-024 pide evitar.

La carpeta la dice `MIDGAROR_DATOS`, la misma variable que ya usa midgaror
(y que la unidad de systemd del bot en Madre ya tiene puesta): así el porte
no le cambia a nadie el sitio donde caen sus entradas. Mover la prosa a
`inquilinos/<nombre>/diario/` (lo que sugiere el esquema del ADR-024) es una
migración de datos aparte — años de entradas — y no algo que este porte
decida de rebote.
"""

import os
import re
from pathlib import Path

from hugin.guardado.almacen import escribir as _escribir
from hugin.personal import fechas

VARIABLE = "MIDGAROR_DATOS"


def _raiz() -> Path:
    """La raíz de los datos del diario. La variable manda; si no, aquí."""
    valor = os.environ.get(VARIABLE, "").strip()
    return Path(valor).expanduser().resolve() if valor else Path.cwd()


# Módulo, no función, a propósito: es justo lo que permite a las pruebas
# monkeypatchear `diario.CARPETA_PERSONAL` para apuntar a un temporal, igual
# que hacía `diario/tests/test_bridge.py` con `organizar_diario.CARPETA_PERSONAL`.
CARPETA_PERSONAL = _raiz() / "diario" / "personal"

SECCION = "## Qué ha pasado hoy"  # el nombre lo usan otros módulos
FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}

# Dónde puede escribir el bot, y cómo se ve cada sitio.
#   "hora"  -> la hora delante, para lo que es un momento del día
#   "lista" -> una viñeta, para lo que es un elemento suelto
SECCIONES = {
    "hoy": (SECCION, "hora"),
    "siento": ("## Cómo me siento", "hora"),
    "aprendo": ("## Avances / aprendizajes", "lista"),
    "plan": ("## Para mañana", "lista"),
}

# La plantilla es igual para cualquier entrada, nunca cambia por inquilino
# ni por fecha (solo {{FECHA}}) — va como constante, no como fichero en
# disco. Un fichero pedía resolver su ruta con `__file__`, prohibido en todo
# el cerebro (ver el docstring de arriba): apuntaría dentro de `hugin/`, que
# es de la aplicación, no de un inquilino.
PLANTILLA = """---
tipo: diario
fecha: {{FECHA}}
repo: midgaror
etiquetas: [personal]
---

# {{FECHA}}

## Qué ha pasado hoy


## Cómo me siento


## Avances / aprendizajes


## Para mañana
"""


def ruta_de_hoy(crear: bool = True) -> Path:
    """Ruta de la entrada de hoy. Con `crear=False` no toca el disco."""
    return ruta_de_fecha(fechas.hoy(), crear=crear)


def ruta_de_fecha(fecha: str, crear: bool = True) -> Path:
    """Ruta de la entrada de una fecha AAAA-MM-DD, creando su carpeta de mes.

    Con `crear=False` solo calcula la ruta y no toca el disco, que es lo que
    necesita quien viene a leer: `leer_entrada` promete que "leer nunca
    escribe".
    """
    if not FECHA_RE.match(fecha):
        raise ValueError(f"Fecha invalida: {fecha!r}. Formato esperado: AAAA-MM-DD")
    anio, mes, _ = fecha.split("-")
    carpeta = CARPETA_PERSONAL / anio / f"{mes}-{MESES[int(mes)]}"
    if crear:
        carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / f"{fecha}.md"


def crear_entrada(ruta: Path, fecha: str | None = None) -> None:
    """Crea la entrada desde la plantilla con la fecha correcta."""
    fecha = fecha or fechas.hoy()
    _escribir(ruta, PLANTILLA.replace("{{FECHA}}", fecha))


def _bloque(texto: str, hora: str | None = None, estilo: str = "hora") -> str:
    """El texto tal y como se verá dentro de su sección."""
    texto = texto.strip()
    if estilo == "lista":
        # Una viñeta es una línea: un mensaje de varias líneas se junta, y
        # sin línea en blanco delante, las viñetas de una lista van seguidas.
        return "- " + " ".join(texto.split()) + "\n"
    marca = hora if hora is not None else fechas.ahora().strftime("%H:%M")
    return f"\n{marca}\n{texto}\n"


def organizar_texto(
    texto: str,
    ruta: Path = None,
    hora: str | None = None,
    fecha: str | None = None,
    seccion: str = "hoy",
) -> Path:
    """Añade texto al final de una sección de una entrada.

    `seccion` es una clave de SECCIONES: "hoy" (por defecto), "siento",
    "aprendo" o "plan". Sin `ruta` ni `fecha` escribe en la entrada de hoy;
    con `fecha` (AAAA-MM-DD) escribe en la de ese día. Crea la entrada desde
    la plantilla si no existe. Si la entrada no tiene esa sección (entradas
    antiguas escritas a mano), la crea al final del archivo en vez de pegar
    el texto suelto detrás.
    """
    if seccion not in SECCIONES:
        raise ValueError(f"seccion desconocida: {seccion!r} (hay {', '.join(SECCIONES)})")
    if not texto.strip():
        raise ValueError("no hay nada que escribir")
    titulo, estilo = SECCIONES[seccion]

    if ruta is None:
        ruta = ruta_de_fecha(fecha) if fecha else ruta_de_hoy()
    if not ruta.exists():
        crear_entrada(ruta, fecha)

    contenido = ruta.read_text(encoding="utf-8")
    bloque = _bloque(texto, hora, estilo)

    if titulo in contenido:
        antes, resto = contenido.split(titulo, 1)
        fin = resto.find("\n## ")
        if fin == -1:
            nuevo_resto = resto.rstrip("\n") + "\n" + bloque
        else:
            cuerpo = resto[:fin].rstrip("\n")
            nuevo_resto = cuerpo + "\n" + bloque + resto[fin:]
        contenido = antes + titulo + nuevo_resto
    else:
        contenido = contenido.rstrip("\n") + f"\n\n{titulo}\n{bloque}"

    # Atómico: si el proceso muere a mitad, la entrada del día se quedaría
    # vacía y no hay copia.
    _escribir(ruta, contenido)
    return ruta


# ---- el contrato con el canal (antes diario/bifrost_bridge.py, ADR-009) ---


def escribir_entrada(texto: str, fecha: str | None = None) -> Path:
    """Añade texto a una entrada sin borrar lo existente.

    Sin `fecha` escribe en la entrada de hoy. Con `fecha` (AAAA-MM-DD)
    escribe en la de ese día, creándola desde la plantilla si no existe.
    """
    return organizar_texto(texto, fecha=fecha)


def leer_entrada(fecha: str | None = None, ruta: Path | None = None) -> str:
    """Devuelve el texto de una entrada para enseñarlo en el chat.

    Sin frontmatter y sin las secciones que siguen vacías, que en un chat
    solo son ruido. Si no hay entrada ese día, lo dice en vez de crearla:
    leer nunca escribe.
    """
    if ruta is None:
        # crear=False: leer no deja rastro en disco, que es lo que promete
        # el docstring de arriba.
        ruta = ruta_de_fecha(fecha, crear=False) if fecha else ruta_de_hoy(crear=False)
    if not ruta.exists():
        return f"Sin entrada el {fecha or ruta.stem}."
    texto = ruta.read_text(encoding="utf-8")
    if texto.startswith("---\n"):
        fin = texto.find("\n---\n", 4)
        if fin != -1:
            texto = texto[fin + 5:]
    # Secciones "## X" sin nada hasta la siguiente cabecera o el final.
    texto = re.sub(r"^## [^\n]+\n(?:\s*\n)*(?=^#|\Z)", "", texto, flags=re.M)
    return texto.strip()
