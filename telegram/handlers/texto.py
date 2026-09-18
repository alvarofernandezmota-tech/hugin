"""Un mensaje suelto, sin comando, va al diario de hoy — o a lo que sea.

Es lo que pasa en cuanto se usa el bot de verdad: se escribe «hoy he dormido
fatal» y se manda, sin acordarse de poner /diario delante. Antes el bot
callaba y el texto se perdía; ahora se apunta igual que con /diario.

Desde que existe `diario/entender.py`, antes de ir al diario se le pregunta
si en realidad es una tarea, un hábito, una cita o un apunte —«recuérdame
llamar al médico mañana», «he hecho deporte», «tele 3h»— y si está seguro, se
apunta donde toca en vez de quedarse como una línea suelta de texto. Es
**opcional y con red de seguridad**: sin `ANTHROPIC_API_KEY` en el `.env` de
Madre, `entender()` devuelve `None` antes de intentar nada y esto se
comporta exactamente igual que siempre. Con clave, solo actúa si está
seguro; con duda, con un fallo de red, o si la frase es de verdad un diario,
cae aquí abajo, al mismo sitio de siempre. La lógica de cuándo confiar vive
en `diario/entender.py`, con sus propias pruebas: aquí solo se traduce lo
que dice a la misma llamada y la misma confirmación que darían /tarea,
/habito, /cita o /apunte.

Los comandos siguen teniendo prioridad: este handler se registra el último y
solo recibe lo que Telegram no marca como comando. Ojo: eso no es lo mismo
que "no empieza por /". Un comando **pegado con formato de código** llega sin
la marca `bot_command`, cae aquí, y acabaría en el diario en vez de
ejecutarse. Pasó el 2026-09-05: treinta comandos seguidos al diario, sin un
solo aviso. Por eso este handler no escribe nada que empiece por «/».
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from handlers.apunte import cuanto
from utils.midgaror import modulo
from utils.respuestas import breve, dia, responder, responder_si_puedo

agenda = modulo("agenda")
conversar = modulo("conversar")
entender = modulo("entender")
fechas = modulo("fechas")
habitos = modulo("habitos")
organizar_texto = modulo("organizar_diario").organizar_texto
registro = modulo("registro")
sincronizar = modulo("sincronizar").sincronizar
tareas = modulo("tareas")

logger = logging.getLogger(__name__)


AVISO_COMANDO = (
    "⚠️ Esto parece un comando, pero no me ha llegado como tal, así que **no** "
    "lo he ejecutado ni lo he apuntado en el diario.\n\n"
    "Suele pasar al pegarlo con formato (por ejemplo copiado de un bloque de "
    "código). Escríbelo a mano, o pégalo como texto sin formato.\n\n"
    "Lo que me llegó:\n{texto}"
)

# Punto de inyección para las pruebas, igual que `modulo.sincronizar` en
# dobles.py: un `preguntar` falso para no llamar nunca a la API de verdad.
# En producción es `None`, y `entender()` usa el suyo si hay clave puesta.
_preguntar = None

# Lo mismo para el otro lado, el que lee y contesta (`conversar.responder`).
# Van separados porque son dos llamadas distintas con dos firmas distintas:
# `entender` recibe una frase, `conversar` recibe frase y contexto.
_responder_pregunta = None


async def _subir(ruta, mensaje: str) -> str:
    # sincronizar() hace git commit y git push: hasta 90 s con mala red.
    # Dentro de una corrutina eso congela el bot entero para todos los
    # chats, no solo para quien mando el mensaje. to_thread lo saca del
    # hilo del bucle de eventos, que sigue atendiendo lo demas.
    return breve(await asyncio.to_thread(sincronizar, ruta, mensaje))


async def _enrutar(update: Update, e) -> None:
    """Aplica lo que entendió `entender()` y contesta como el comando real.

    Puede lanzar `ValueError` —una «cita» sin una fecha que `fechas.py` sepa
    leer, un «hábito» sin nombre—: lo captura `mensaje_libre` y el mensaje
    cae al diario, igual que si `entender()` no hubiera dicho nada. No hay
    ninguna llamada aquí que el clasificador pueda forzar a escribir texto
    libre: cada intención va a la misma función de siempre, con los mismos
    datos que le pasaría su comando.
    """
    if e.intencion == "pregunta":
        # La única rama que no escribe nada: lee los resúmenes y contesta.
        # `conversar` no importa ni una función que escriba —lo vigila
        # `diario/tests/test_conversar.py` sobre el propio fichero—, así que
        # esta rama no puede tocar un JSON aunque el modelo se empeñe.
        #
        # `to_thread` porque `responder()` llama a la API y puede tardar
        # segundos: dentro de la corrutina congelaría el bot entero, igual
        # que pasaba con `sincronizar`.
        respuesta = await asyncio.to_thread(
            conversar.responder, e.texto or "", _responder_pregunta)
        if respuesta is None:
            # Sin clave, red caída o respuesta vacía. Al diario, como todo.
            raise ValueError("no se pudo contestar la pregunta")
        await responder(update, respuesta)
    elif e.intencion == "tarea":
        if not e.texto:
            raise ValueError("tarea sin texto")
        t = tareas.agregar(e.texto)
        subido = await _subir(tareas.RUTA_DATOS, "diario: tareas desde bifrost")
        cuando = ""
        if t.get("fecha"):
            cuando = f" · {t['fecha']}" + (f" {t['hora']}" if t.get("hora") else "")
        await responder(update, f"✅ [{t['id']}] {t['texto']}{cuando} · {subido}")
    elif e.intencion == "cita":
        if not e.texto:
            raise ValueError("cita sin texto")
        cita, solapan = agenda.agregar(e.texto)
        subido = await _subir(agenda.RUTA_DATOS, "diario: citas desde bifrost")
        cuando = f"{cita['fecha']} {cita['hora']}" if cita.get("hora") else f"{cita['fecha']} (todo el día)"
        texto_conf = f"📅 [{cita['id']}] {cita['texto']} · {cuando} · {subido}"
        aviso = agenda.aviso_choques(solapan)
        await responder(update, f"{texto_conf}\n{aviso}" if aviso else texto_conf)
    elif e.intencion == "habito":
        if not e.nombre:
            raise ValueError("hábito sin nombre")
        fecha, nombre, marca = habitos.marcar(e.nombre, hecho=e.hecho, fecha=e.cuando, valor=e.valor)
        subido = await _subir(habitos.RUTA_DATOS, "diario: hábitos desde bifrost")
        await responder(update, f"{habitos.formato(marca)} {nombre} — {fecha} · {subido}")
    elif e.intencion == "apunte":
        if not e.nombre:
            raise ValueError("apunte sin nombre")
        apunte = registro.apuntar(e.nombre, valor=e.valor, unidad=e.unidad, fecha=e.cuando)
        subido = await _subir(registro.RUTA_DATOS, "diario: apuntes desde bifrost")
        await responder(update, f"📝 {apunte['que']}{cuanto(apunte)} — {apunte['fecha']} · {subido}")
    else:
        # entender() nunca debería devolver otra cosa (solo alta confianza y
        # sin ser "diario"), pero si algún día cambia el esquema, esto cae al
        # diario en vez de intentar adivinar qué hacer con una intención que
        # no conoce.
        raise ValueError(f"intención sin manejar: {e.intencion!r}")


async def procesar(update: Update, texto: str) -> None:
    """Un texto ya en mano —escrito, o dictado y transcrito—: se entiende, o
    al diario de hoy.

    Esto es lo que comparten `mensaje_libre` (texto suelto) y `mensaje_voz`
    (una nota de voz ya pasada por Whisper, en `handlers/voz.py`): a partir
    de aquí da igual de dónde salió el texto, es el mismo mensaje suelto de
    siempre y pasa por el mismo camino. `mensaje_libre` sigue siendo quien
    filtra lo que empieza por «/» —una transcripción nunca puede empezar por
    ahí de casualidad, así que `mensaje_voz` no repite ese aviso.
    """
    # to_thread por el mismo motivo que en la rama "pregunta", más abajo:
    # con MIDGAROR_LLM=ollama la llamada corre en la CPU de Madre y puede
    # tardar varios segundos (TOPE_SEGUNDOS_OLLAMA en entender.py). Sin
    # sacarla del hilo del bucle de eventos, esos segundos congelan el bot
    # entero para todos los chats mientras clasifica uno solo.
    entendido = await asyncio.to_thread(entender.entender, texto, _preguntar)
    if entendido is not None:
        try:
            await _enrutar(update, entendido)
            return
        except ValueError:
            logger.info("«%s» clasificado como %s pero no se pudo aplicar; va al diario",
                       texto[:80], entendido.intencion)
        except Exception:
            logger.exception("Error apuntando %s desde el mensaje suelto; va al diario",
                             entendido.intencion)

    # «cené con mi hermana ayer» va al día de ayer, sin el «ayer». Solo el
    # pasado sin ambigüedad cuenta (fechas.fecha_detras): «tengo examen
    # mañana» es una frase de hoy y se queda entera.
    texto, fecha = fechas.fecha_detras(texto)
    try:
        ruta = organizar_texto(texto, fecha=fecha)
        subido = await _subir(ruta, None)
        await responder(update, f"📔 Apuntado en el diario {dia(fecha)} · {subido}")
    except Exception as e:
        logger.exception("Error escribiendo un mensaje suelto en el diario")
        await responder_si_puedo(update, f"❌ Error: {e}")


async def mensaje_libre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cualquier texto que no sea un comando: se entiende, o al diario de hoy."""
    texto = (update.effective_message.text or "").strip()
    if not texto:
        return
    if texto.startswith("/"):
        # Un comando de verdad no llega aquí: lo habría cogido su CommandHandler.
        # Si llega, es que Telegram no lo marcó como comando, y meterlo en el
        # diario sería tragárselo en silencio. Se avisa y se devuelve el texto
        # para poder reenviarlo sin volver a escribirlo.
        logger.warning("Texto que parece comando y no lo es (entidades: %s): %r",
                       [e.type for e in (update.effective_message.entities or [])], texto[:80])
        await responder(update, AVISO_COMANDO.format(texto=texto))
        return
    await procesar(update, texto)
