#!/usr/bin/env python3
"""Bot de Telegram para escribir en el diario personal."""

import logging
import os
import time
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

# Importar handlers
from handlers.apunte import comando_apunte, comando_dia, comando_semana
from handlers.cita import comando_agenda, comando_cita
from handlers.diario import comando_diario
from handlers.entrada import comando_entrada
from handlers.habito import comando_habito, comando_habitos
from handlers.hoy import comando_hoy
from handlers.menu import boton, comando_menu, respuesta_al_menu
from handlers.recordatorios import arrancar as arrancar_recordatorios
from handlers.recordatorios import parar as parar_recordatorios
from handlers.secciones import comando_aprendo, comando_plan, comando_siento
from handlers.tarea import comando_tarea, comando_tareas
from handlers.texto import mensaje_libre
from handlers.voz import mensaje_voz
from utils.auth import filtro_autorizado
from utils.respuestas import responder, responder_si_puedo

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Configurar logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# httpx registra la URL completa de cada peticion a la API de Telegram, y esa
# URL lleva el token dentro. A nivel INFO eso escupe el token en cada sondeo,
# unas seis veces por minuto, a la terminal y a cualquier log que se guarde o
# se pegue en un chat. Silenciado a WARNING: los errores se siguen viendo.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# El menú de comandos de Telegram: lo que sale al pulsar el botón "/" en el
# chat. Se registra al arrancar con setMyCommands, así que la lista de aquí es
# la única fuente: si se añade un comando, se añade aquí y aparece solo.
MENU = [
    ("menu", "Botones: apunta sin escribir el comando"),
    ("hoy", "El día de un vistazo"),
    ("diario", "Apunta algo en el diario de hoy"),
    ("siento", "Cómo te sientes ahora mismo"),
    ("aprendo", "Algo que has aprendido o avanzado"),
    ("plan", "Algo para mañana"),
    ("entrada", "Apunta algo en otro día: /entrada 2026-09-03 texto"),
    ("tarea", "Apunta o cambia una tarea"),
    ("tareas", "Tus tareas abiertas"),
    ("cita", "Apunta una cita: /cita médico mañana a las 10"),
    ("agenda", "Tus citas de hoy o de la semana"),
    ("habito", "Apunta un hábito, o su valor del 1 al 10"),
    ("habitos", "Tus hábitos de hoy o de la semana"),
    ("apunte", "Apunta cuánto de algo: /apunte tele 3h"),
    ("dia", "Lo apuntado hoy, contra tus objetivos"),
    ("semana", "La semana entera, de lunes a domingo"),
    ("help", "Cómo se usa cada comando"),
]


async def registrar_menu(app: Application) -> None:
    """Publica MENU en Telegram al arrancar (el botón «/» del chat).

    Si Telegram no contesta, el bot arranca igual: el menú es comodidad, y
    quedarse sin bot por no poder pintar una lista sería peor.
    """
    try:
        await app.bot.set_my_commands([BotCommand(c, d) for c, d in MENU])
        logger.info("✅ Menú de comandos registrado (%d comandos)", len(MENU))
    except Exception:
        logger.exception("No se pudo registrar el menú de comandos; el bot sigue")


async def al_arrancar(app: Application) -> None:
    """Lo que se hace una vez, al levantar el bot.

    El menú y el bucle de recordatorios (handlers/recordatorios.py), que es
    lo único que habla sin que le hablen. Los dos van envueltos para que un
    fallo aquí no impida arrancar: un bot sin menú o sin avisos sigue siendo
    un bot; un bot que no arranca, no.
    """
    await registrar_menu(app)
    try:
        arrancar_recordatorios(app)
    except Exception:
        logger.exception("No se pudieron arrancar los recordatorios; el bot sigue")


async def al_parar(app: Application) -> None:
    """Lo que hay que recoger al apagar: el bucle de recordatorios.

    Sin esto, la tarea se queda a medio `sleep` y asyncio lo grita al
    cerrarse con un ERROR en el log de cada reinicio.
    """
    await parar_recordatorios(app)


async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /start - Mensaje de bienvenida."""
    await responder(update, 
        "👋 ¡Hola! Soy Bifrost.\n\n"
        "Escríbeme el día según pasa:\n"
        "/diario hoy he dormido fatal\n"
        "/siento contento, he dormido bien\n"
        "/tarea comprar el pan\n"
        "/cita médico mañana a las 10\n"
        "/habito deporte\n"
        "/hoy — el día de un vistazo\n\n"
        "O escribe sin más: lo que mandes sin comando va al diario de hoy.\n"
        "También puedes mandar una nota de voz: la oigo y hago lo mismo.\n"
        "Y /menu te da botones, para no escribir ni el comando.\n"
        "Pulsa «/» para ver todos los comandos, o /help para el detalle."
    )


async def comando_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando /help - Muestra ayuda."""
    await responder(update, 
        "📖 Ayuda de Bifrost\n\n"
        "Los ejemplos son literales: escribe lo que ves, sin < ni >.\n\n"
        "BOTONES\n"
        "/menu                     un botón por cosa: tocas, te pregunta, escribes\n"
        "Es lo cómodo desde el móvil: el menú de «/» envía el comando solo,\n"
        "sin dejarte poner el texto detrás.\n\n"
        "DIARIO\n"
        "/diario hoy he dormido fatal\n"
        "   añade el texto a «Qué ha pasado hoy», con la hora delante\n"
        "/entrada ayer se me olvidó apuntar esto\n"
        "   lo mismo, en el día que digas: ayer, antes de ayer, el lunes,\n"
        "   hace 3 días o 2026-09-03\n"
        "/diario cené con mi hermana ayer\n"
        "   con «ayer» al final, va al día de ayer. Solo el pasado: «tengo\n"
        "   examen mañana» es una frase de hoy y se queda entera\n\n"
        "CADA COSA EN SU SECCIÓN\n"
        "La entrada del día tiene cuatro apartados. Estos escriben en los\n"
        "otros tres, para que el día se relea entero y no todo amontonado:\n"
        "/siento hoy estoy contento, he dormido bien   → Cómo me siento\n"
        "/aprendo lo de filters.COMMAND de Telegram    → Avances / aprendizajes\n"
        "/plan seguir con el portfolio                 → Para mañana\n\n"
        "TAREAS\n"
        "/tarea comprar el pan     apunta una tarea\n"
        "/tarea médico mañana a las 10  con fecha: la saca del texto\n"
        "/tarea empezar 3          la pone en proceso\n"
        "/tarea hecha 3            la marca hecha\n"
        "/tarea reabrir 3          la devuelve a pendiente\n"
        "/tarea editar 3 comprar pan y leche   le cambia el texto\n"
        "/tarea aplazar 3 el lunes por la tarde   le cambia la fecha\n"
        "/tarea borrar 3           la retira\n"
        "/tareas                   las abiertas y las últimas hechas\n\n"
        "CITAS\n"
        "Una cita siempre lleva cuándo; una tarea puede no llevarlo.\n"
        "/cita médico mañana a las 10   apunta una cita\n"
        "/cita dentista el 15 de octubre a las 17:30\n"
        "/cita mover 3 el lunes a las 17   la cambia de hora\n"
        "/cita cancelar 3          la retira\n"
        "/agenda                   las de hoy\n"
        "/agenda semana            los siete días desde hoy\n"
        "Si dos citas se pisan, se guarda igual y te avisa.\n\n"
        "HÁBITOS\n"
        "/habito deporte           hecho hoy\n"
        "/habito no meditar        no hecho hoy\n"
        "/habito energia 7         un valor del 1 al 10\n"
        "/habito deporte ayer      en otro día, dicho en español\n"
        "/habito deporte 2026-09-03  o con la fecha entera\n"
        "/habitos                  los de hoy\n"
        "/habitos semana           la semana, con totales y medias\n\n"
        "APUNTES (cuánto de algo)\n"
        "Un apunte es un evento, no una casilla: dos ratos de tele son dos\n"
        "apuntes y se suman al leer, no se pisan.\n"
        "/apunte deporte           hecho, sin más\n"
        "/apunte tele 3h           con cantidad y unidad\n"
        "/apunte agua 1,5 l        la unidad puede ir separada\n"
        "/apunte ver la tele 2h    el nombre puede llevar espacios\n"
        "/apunte tele 1h ayer      en otro día, dicho en español\n"
        "/dia                      lo apuntado hoy, contra tus objetivos\n"
        "/dia ayer                 el de otro día\n"
        "/semana                   la semana entera, de lunes a domingo\n"
        "Si algo tiene objetivo, sale comparado: «al menos 3» o «como mucho 7».\n"
        "La dirección la pone el objetivo, no el nombre de la cosa.\n\n"
        "SIN COMANDO\n"
        "Escribe y ya: cualquier mensaje suelto se apunta en el diario de hoy,\n"
        "igual que /diario.\n\n"
        "NOTA DE VOZ\n"
        "Mándala y ya: te digo lo que he oído y sigue el mismo camino que si\n"
        "lo hubieras escrito.\n\n"
        "EL DÍA\n"
        "/hoy                      diario, citas, tareas y hábitos juntos\n"
        "/hoy ayer                 el de otro día (o antes de ayer, el lunes, 2026-09-03)\n\n"
        "Todo lo que escribes se guarda en tu repo y se sube a GitHub."
    )


async def error_no_atrapado(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """La ultima red: lo que se escape de un handler acaba aqui, no en el vacio.

    Sin esto, una excepcion que sale de un handler se queda en un aviso de la
    libreria ("No error handlers are registered") y el usuario no se entera de
    nada. El caso real, comprobado con python-telegram-bot 22.8: el reply falla
    por red, el except del handler lo reintenta, falla otra vez y la excepcion
    sale; el texto ya estaba escrito Y subido a GitHub, y al chat no llegaba
    ni un error. Ahora al menos queda en el log con su traza y, si se puede,
    se avisa.

    El aviso va por responder_si_puedo: si lo que falla es justo mandar
    mensajes, intentarlo aqui otra vez solo repetiria el problema.

    No se dice QUE ha fallado: si es un fallo interno, el texto de la
    excepcion no le sirve al usuario y puede llevar rutas del servidor.
    """
    logger.error("Error sin atrapar procesando %r", update, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message is not None:
        await responder_si_puedo(
            update, "❌ Algo ha fallado por dentro. Ha quedado en el log; vuelve a intentarlo.")


def main() -> None:
    """Inicia el bot de Telegram."""
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN no encontrado en .env")
        raise ValueError("TELEGRAM_BOT_TOKEN no encontrado en .env")

    logger.info("✅ Iniciando bot de Telegram...")
    app = Application.builder().token(TOKEN).post_init(al_arrancar).post_shutdown(al_parar).build()

    # Nunca es None: sin ids validos en el .env, el filtro no deja pasar a
    # nadie y auth.py lo grita por el log. Cerrado por defecto a proposito.
    # `& UpdateType.MESSAGE` deja fuera las ediciones: editar un mensaje ya
    # enviado NO vuelve a disparar el handler. Sin esto, editar un /diario
    # para corregir una errata lo apuntaba DOS veces en el diario (y lo subia
    # a git), y editar un texto suelto reventaba el handler con update.message
    # None. Se pone aqui, en el filtro que ya comparten todos, para que ningun
    # handler tenga que acordarse.
    autorizado = filtro_autorizado() & filters.UpdateType.MESSAGE

    app.add_handler(CommandHandler("start", comando_start, filters=autorizado))
    app.add_handler(CommandHandler("help", comando_help, filters=autorizado))
    app.add_handler(CommandHandler("menu", comando_menu, filters=autorizado))
    app.add_handler(CommandHandler("diario", comando_diario, filters=autorizado))
    app.add_handler(CommandHandler("entrada", comando_entrada, filters=autorizado))
    app.add_handler(CommandHandler("siento", comando_siento, filters=autorizado))
    app.add_handler(CommandHandler("aprendo", comando_aprendo, filters=autorizado))
    app.add_handler(CommandHandler("plan", comando_plan, filters=autorizado))
    app.add_handler(CommandHandler("tarea", comando_tarea, filters=autorizado))
    app.add_handler(CommandHandler("tareas", comando_tareas, filters=autorizado))
    app.add_handler(CommandHandler("cita", comando_cita, filters=autorizado))
    app.add_handler(CommandHandler("agenda", comando_agenda, filters=autorizado))
    app.add_handler(CommandHandler("habito", comando_habito, filters=autorizado))
    app.add_handler(CommandHandler("habitos", comando_habitos, filters=autorizado))
    app.add_handler(CommandHandler("hoy", comando_hoy, filters=autorizado))
    app.add_handler(CommandHandler("apunte", comando_apunte, filters=autorizado))
    app.add_handler(CommandHandler("dia", comando_dia, filters=autorizado))
    app.add_handler(CommandHandler("semana", comando_semana, filters=autorizado))

    # Los botones de /menu. El filtro de chat no vale para un callback_query:
    # la autorizacion la comprueba el propio handler.
    app.add_handler(CallbackQueryHandler(boton))

    # Antes del texto libre: lo que responde a una pregunta del menu va al
    # handler de esa pregunta. Lo que responde a otra cosa, al diario.
    # `autorizado` ya lleva ~ediciones, asi que una respuesta editada tampoco
    # se reescribe.
    respuestas = filters.REPLY & filters.TEXT & ~filters.COMMAND & autorizado
    app.add_handler(MessageHandler(respuestas, respuesta_al_menu))

    # El ultimo: cualquier texto que no sea un comando va al diario de hoy.
    solo_texto = filters.TEXT & ~filters.COMMAND & autorizado
    app.add_handler(MessageHandler(solo_texto, mensaje_libre))

    # Una nota de voz: se transcribe y sigue el mismo camino que un texto
    # suelto (handlers/voz.py). No compite con los de arriba: un mensaje de
    # Telegram es voz O texto, nunca las dos cosas.
    nota_de_voz = filters.VOICE & autorizado
    app.add_handler(MessageHandler(nota_de_voz, mensaje_voz))

    # El ultimo de la cadena: lo que no atrape ningun handler.
    app.add_error_handler(error_no_atrapado)

    logger.info("🤖 Bot en marcha. Escuchando comandos...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


def arrancar(espera: int = 15, tope: int = 12) -> None:
    """Arranca el bot, reintentando si al conectar no hay red.

    Al reiniciar Madre, la red puede tardar un minuto en estar, y el bot
    moriria antes con un NetworkError. Aqui se reintenta con una espera fija
    hasta `tope` veces (unos tres minutos), que cubre de sobra el arranque de
    una maquina. Un InvalidToken NO se reintenta: eso es un error de
    configuracion, no un problema de red, y reintentar solo lo esconderia.
    Sale entonces, y systemd (sin tope de reinicios) lo volvera a intentar.
    """
    # Import local: arriba chocaria con el telegram falso que instalan las
    # pruebas (dobles.py) al importar este modulo con ast/import.
    from telegram.error import InvalidToken, NetworkError
    for intento in range(1, tope + 1):
        try:
            main()
            return
        except NetworkError as e:
            if intento == tope:
                logger.error("Sin red tras %d intentos; me rindo y que systemd reintente: %s",
                             tope, e)
                raise
            logger.warning("No hay red todavia (intento %d/%d): %s. Reintento en %d s.",
                           intento, tope, e, espera)
            time.sleep(espera)
        except InvalidToken:
            logger.error("El TELEGRAM_BOT_TOKEN no vale. Esto no es la red: revisa el .env.")
            raise


if __name__ == "__main__":
    arrancar()
