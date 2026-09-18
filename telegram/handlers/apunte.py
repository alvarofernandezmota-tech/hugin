"""Handlers de /apunte, /dia y /semana.

Interfaz de midgaror/diario/registro/registro.py, el modelo del ADR-012.

Un **apunte** es un evento, no una casilla: `tele 3h`, `deporte`, `agua 1,5l`.
Varios del mismo día se suman al leer, y la dirección la pone el objetivo
(`al_menos` / `como_mucho`), no una etiqueta de bueno o malo.

Los totales no se guardan: `/dia` y `/semana` los calculan al mostrar
(apartado 6 del ADR). Este módulo solo pinta lo que devuelve `registro`.
"""

import asyncio
import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from utils.midgaror import modulo
from utils.respuestas import breve, responder, responder_si_puedo

fechas = modulo("fechas")
registro = modulo("registro")
sincronizar = modulo("sincronizar").sincronizar

logger = logging.getLogger(__name__)

AYUDA = (
    "❌ Uso:\n"
    "/apunte deporte — hecho, sin más\n"
    "/apunte tele 3h — con cantidad y unidad\n"
    "/apunte agua 1,5 l — la unidad puede ir separada\n"
    "/apunte ver la tele 2h — el nombre puede llevar espacios\n"
    "/apunte tele 1h ayer — en otro día, dicho en español\n"
    "/dia — lo apuntado hoy\n"
    "/dia ayer — o el día que digas\n"
    "/semana — la semana entera, de lunes a domingo"
)

# «3h», «1,5l», «30min», «2». El número delante y, pegada o no, la unidad.
CANTIDAD = re.compile(r"^(\d+(?:[.,]\d+)?)\s*([^\W\d_]*)$", re.UNICODE)
# Una unidad suelta detrás del número: el «h» de «tele 3 h».
UNIDAD_SOLA = re.compile(r"^[^\W\d_]+$", re.UNICODE)


def _partir(args: list[str]) -> tuple[str, str | None, str | None, str | None]:
    """(que, valor, unidad, fecha) a partir de los argumentos de /apunte.

    Se reconoce por descarte desde el final, como en /habito: primero la
    fecha, luego la cantidad, y lo que queda es el nombre —que puede llevar
    espacios, «ver la tele»—.

    Siempre se deja al menos una palabra para el nombre. Por eso «/apunte 7»
    apunta una cosa llamada «7», por raro que sea, y no un valor suelto sin
    nada a lo que pegarse.
    """
    restantes = list(args)
    fecha = None
    for n in range(min(fechas.MAX_PALABRAS, len(restantes) - 1), 0, -1):
        candidata = fechas.como_fecha(" ".join(restantes[-n:]), hacia_atras=True)
        if candidata:
            fecha, restantes = candidata, restantes[:-n]
            break

    valor = unidad = None
    # «tele 3 h»: la unidad va suelta detrás del número. Hacen falta tres
    # palabras para que quede alguna como nombre.
    if len(restantes) > 2 and UNIDAD_SOLA.match(restantes[-1]):
        m = CANTIDAD.match(restantes[-2])
        if m and not m.group(2):
            unidad = restantes.pop()
            valor = CANTIDAD.match(restantes.pop()).group(1)
    if valor is None and len(restantes) > 1:
        m = CANTIDAD.match(restantes[-1])
        if m:
            valor, unidad = m.group(1), m.group(2) or None
            restantes.pop()
    return " ".join(restantes), valor, unidad, fecha


def _cantidad(linea: dict) -> str:
    """«3 h», «1,5 l», o el número a secas si no hay unidad.

    Para una LÍNEA DE RESUMEN (`registro.resumen_dia`/`resumen_semana`), que
    trae el total ya sumado en `total`. Un apunte recién creado no tiene esa
    clave —tiene `valor`—: para ese caso está `cuanto()`, abajo.
    """
    unidad = f" {linea['unidad']}" if linea.get("unidad") else ""
    return f"{linea['total']}{unidad}"


def cuanto(apunte: dict) -> str:
    """« 3h», « 1,5 l», o cadena vacía si el apunte no lleva valor.

    Para confirmar el apunte que se acaba de crear, no una línea de resumen:
    `registro.apuntar()` devuelve `valor`/`unidad`, nunca `total`. Usar
    `_cantidad()` aquí —como hacía este módulo hasta ahora— revienta con
    `KeyError: 'total'` en cuanto el apunte lleva un valor, que es el caso
    más normal («/apunte agua 1,5 l»): el dato se guardaba bien, pero la
    confirmación moría con «❌ Error: 'total'» en vez de decir lo que se
    apuntó. No lo cogía ninguna prueba porque `test_apunte.py` comprueba el
    JSON escrito, no el texto de la respuesta.
    """
    if "valor" not in apunte:
        return ""
    unidad = f" {apunte['unidad']}" if apunte.get("unidad") else ""
    return f" {apunte['valor']}{unidad}"


def pintar(resumen: dict, cabecera: str) -> str:
    """El resumen, en texto para el chat. Aquí se pinta; registro.py no imprime.

    El icono sale del objetivo, no del nombre: un `al_menos` sin cumplir es
    «te falta» (⏳), no «mal» — que es justo lo que dice el ADR-012 cuando
    insiste en que el programa no clasifica nada como bueno o malo.
    """
    if not resumen["lineas"]:
        return f"{cabecera}\n\n(nada apuntado)"
    filas = []
    for linea in resumen["lineas"]:
        objetivo = linea.get("objetivo")
        if objetivo is None:
            filas.append(f"· {linea['que']} {_cantidad(linea)}")
            continue
        if linea["cumple"]:
            icono = "✅"
        else:
            icono = "⏳" if objetivo["tipo"] == "al_menos" else "❌"
        meta = "al menos" if objetivo["tipo"] == "al_menos" else "como mucho"
        filas.append(f"{icono} {linea['que']} {_cantidad(linea)} "
                     f"({meta} {objetivo['valor']})")
    return cabecera + "\n\n" + "\n".join(filas)


async def comando_apunte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/apunte <qué> [cantidad][unidad] [ayer | AAAA-MM-DD]"""
    args = list(context.args or [])
    if not args:
        await responder(update, AYUDA)
        return
    try:
        que, valor, unidad, fecha = _partir(args)
        apunte = registro.apuntar(que, valor=valor, unidad=unidad, fecha=fecha)
        # sincronizar() hace git commit y git push: hasta 90 s con mala red.
        # Dentro de una corrutina eso congela el bot entero para todos los
        # chats, no solo para quien mando el mensaje. to_thread lo saca del
        # hilo del bucle de eventos, que sigue atendiendo lo demas.
        subido = breve(await asyncio.to_thread(
            sincronizar, registro.RUTA_DATOS, "diario: apuntes desde bifrost"))
        await responder(update, f"📝 {apunte['que']}{cuanto(apunte)} — {apunte['fecha']} · {subido}")
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /apunte")
        await responder_si_puedo(update, f"❌ Error: {e}")


async def comando_dia(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/dia [ayer | el lunes | AAAA-MM-DD]"""
    try:
        # El día puede ser varias palabras («antes de ayer»). Hacia atrás: se
        # mira lo que ya ha pasado.
        dicho = " ".join(context.args or [])
        fecha = fechas.normalizar(dicho, hacia_atras=True) if dicho else None
        resumen = registro.resumen_dia(fecha)
        await responder(update, pintar(resumen, f"📊 Apuntes del {resumen['fecha']}"))
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /dia")
        await responder_si_puedo(update, f"❌ Error: {e}")


async def comando_semana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/semana [ayer | el lunes | AAAA-MM-DD] — la semana natural de ese día."""
    try:
        dicho = " ".join(context.args or [])
        fecha = fechas.normalizar(dicho, hacia_atras=True) if dicho else None
        resumen = registro.resumen_semana(fecha)
        cabecera = f"📆 Semana del {resumen['desde']} al {resumen['hasta']}"
        await responder(update, pintar(resumen, cabecera))
    except ValueError as e:
        await responder(update, f"⚠️ {e}")
    except Exception as e:
        logger.exception("Error en /semana")
        await responder_si_puedo(update, f"❌ Error: {e}")
