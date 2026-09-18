"""Handlers de /habito y /habitos.

Interfaz de midgaror/diario/habitos/habitos.py, igual que /tarea con tareas.
"""

import asyncio
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from utils.midgaror import modulo
from utils.respuestas import breve, responder, responder_si_puedo

fechas = modulo("fechas")
habitos = modulo("habitos")
sincronizar = modulo("sincronizar").sincronizar

logger = logging.getLogger(__name__)

AYUDA = (
    "❌ Uso:\n"
    "/habito deporte — apúntalo como hecho hoy\n"
    "/habito Leer Libro — el nombre puede llevar espacios\n"
    "/habito no meditar — apúntalo como no hecho\n"
    "/habito energia 7 — apunta un valor del 1 al 10\n"
    "/habito deporte ayer — en otro día, dicho en español\n"
    "/habito deporte 2026-09-03 — o con la fecha entera\n"
    "/habito Beber agua 3 2026-09-03 — todo junto\n"
    "/habitos — los de hoy\n"
    "/habitos semana — la semana"
)

# Lo que tiene pinta de fecha escrita con números. Si además fechas.py no la
# entiende, es una fecha mal escrita, no un hábito llamado «2026-13-45».
PINTA_DE_FECHA = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$|^\d{1,2}/\d{1,2}(/\d{2,4})?$")


def _partir(args: list[str]) -> tuple[str, str | None, str | None]:
    """(nombre, valor, fecha) a partir de los argumentos de /habito.

    El nombre puede llevar espacios («Leer Libro»), así que se reconoce por
    descarte: del final se quita la fecha si lo es —«ayer», «antes de ayer»,
    «el lunes», `AAAA-MM-DD`— y el valor si es un entero; lo que queda es el
    nombre. La fecha se resuelve hacia atrás: un hábito se apunta después de
    hacerlo, así que «el lunes» es el que ya pasó.

    Antes el último argumento se tomaba SIEMPRE como fecha, y por eso
    «/habito Leer Libro» moría con «fecha no válida: 'Libro'». Un hábito de
    dos palabras es de lo más normal y no había manera de apuntarlo.
    """
    restantes = list(args)
    fecha = None
    # La fecha puede ser varias palabras: se prueba primero el trozo más
    # largo, y siempre dejando al menos una palabra para el nombre.
    for n in range(min(fechas.MAX_PALABRAS, len(restantes) - 1), 0, -1):
        candidata = fechas.como_fecha(" ".join(restantes[-n:]), hacia_atras=True)
        if candidata:
            fecha, restantes = candidata, restantes[:-n]
            break
    if fecha is None and len(restantes) > 1 and PINTA_DE_FECHA.match(restantes[-1]):
        raise ValueError(f"fecha no válida: {restantes[-1]!r} (ayer, el lunes, 2026-09-05…)")
    # El valor solo se reconoce si detrás queda algo que sea el nombre: en
    # «/habito 7», el 7 es el nombre del hábito, por raro que sea, y no un
    # valor suelto sin hábito al que pegarse.
    valor = restantes.pop() if len(restantes) > 1 and restantes[-1].isdigit() else None
    return " ".join(restantes), valor, fecha


async def comando_habito(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/habito [no] <nombre con espacios> [valor 1-10] [ayer | AAAA-MM-DD]"""
    args = list(context.args)
    if not args:
        await responder(update, AYUDA)
        return
    hecho = True
    if args[0] == "no":
        hecho, args = False, args[1:]
    if not args:
        await responder(update, AYUDA)
        return
    try:
        nombre, valor, fecha = _partir(args)
        fecha, nombre, marca = habitos.marcar(nombre, hecho=hecho, fecha=fecha, valor=valor)
        # sincronizar() hace git commit y git push: hasta 90 s con mala red.
        # Dentro de una corrutina eso congela el bot entero para todos los
        # chats, no solo para quien mando el mensaje. to_thread lo saca del
        # hilo del bucle de eventos, que sigue atendiendo lo demas.
        subido = breve(await asyncio.to_thread(
            sincronizar, habitos.RUTA_DATOS, "diario: hábitos desde bifrost"))
        await responder(update, f"{habitos.formato(marca)} {nombre} — {fecha} · {subido}")
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /habito")
        await responder_si_puedo(update, f"❌ Error: {e}")


async def comando_habitos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/habitos [semana] [ayer | el lunes | AAAA-MM-DD]"""
    args = list(context.args)
    try:
        # El día puede ser varias palabras («antes de ayer»); lo entiende habitos.
        if args and args[0] == "semana":
            texto = habitos.resumen_semana(" ".join(args[1:]) or None)
        else:
            texto = habitos.resumen_dia(" ".join(args) or None)
        await responder(update, texto)
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /habitos")
        await responder_si_puedo(update, f"❌ Error: {e}")
