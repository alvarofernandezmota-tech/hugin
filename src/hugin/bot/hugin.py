"""El bot: entra un `Mensaje`, sale una `Respuesta`.

Este es el cuerpo que hasta la fase 1 del issue #23 vivía en
`telegram/handlers/texto.py::procesar`, movido rama por rama: un saludo se
contesta y no se apunta, lo que `entender()` reconozca con seguridad va a
su sitio por `hugin.personal.enrutar`, y todo lo demás —sin clasificar, con
dudas, o clasificado pero imposible de aplicar— cae al diario de hoy, que
es lo que pasaba antes de que existiera el clasificador.

## Síncrono a propósito

`procesar()` no es una corrutina y no importa `asyncio`. Las tres llamadas
lentas de dentro —clasificar con un modelo, contestar una pregunta,
sincronizar con git— las saca del bucle de eventos **el canal**: Telegram
envuelve esta llamada entera en un `asyncio.to_thread`, igual que antes
envolvía las tres por separado. Meter `asyncio` aquí obligaría a cada
puerta futura a hablar asíncrono solo para preguntar qué se contesta, y una
consola no tiene bucle de eventos que proteger.

## Las tres dependencias que se inyectan

`preguntar` y `responder_pregunta` son los dos motores: clasificar una
frase y contestar una pregunta. Son dos porque son dos llamadas con dos
firmas distintas. En producción van en `None` y cada módulo usa el suyo si
hay motor configurado; en pruebas se les pasa uno falso para no llamar
nunca a una API de verdad. Es el mismo par que `handlers/texto.py` tenía
como globales de módulo, y los sigue teniendo: lo que hace el adaptador es
pasarlos aquí en cada llamada.

`sincronizar` es `git commit` + `git push`. En `None` no se sincroniza y la
confirmación sale sin coletilla — así arranca la consola, porque un push
por cada línea de una sesión interactiva no tiene sentido. Telegram le pasa
la de verdad y el texto sale idéntico a antes.

Nada de esto elige un motor ni monta un RAG: eso es la fase 4 del issue
#23. Aquí solo se llama a lo que ya existía.
"""

import logging

from hugin.bot import mensajes
from hugin.bot.mensajes import Mensaje, Respuesta
from hugin.personal import diario, entender, enrutar
from hugin.personal import fechas as fechas_personal

logger = logging.getLogger(__name__)


class Hugin:
    """El cerebro con sus motores puestos. Sin estado entre mensajes.

    Construirlo es barato y no abre nada: un canal puede tener uno vivo
    todo el proceso o hacerse uno por mensaje, que es lo que hace Telegram
    para poder cambiar los motores desde una prueba sin reimportar nada.

    La memoria de una conversación —el «sí» que contesta a «¿te refieres a
    las 17:00?»— es `sesion.py` en la fase 2. Aquí cada mensaje se atiende
    solo, como ya hacía `handlers/texto.py`.
    """

    def __init__(self, preguntar=None, responder_pregunta=None, sincronizar=None):
        self._preguntar = preguntar
        self._responder_pregunta = responder_pregunta
        self._sincronizar = sincronizar

    def _subir(self, ruta, mensaje: str | None) -> str:
        """La coletilla de sincronización, o nada si no hay con qué."""
        if self._sincronizar is None:
            return ""
        return mensajes.breve(self._sincronizar(ruta, mensaje))

    def procesar(self, mensaje: Mensaje) -> Respuesta:
        """Lo que se contesta a un texto suelto. Nunca lanza.

        Si algo revienta por el camino, se contesta con el aviso de error:
        quien escribe tiene que enterarse de que su frase no se ha guardado,
        y un canal no tiene manera de saber qué decir en su lugar.
        """
        texto = mensaje.texto
        inq = mensaje.sesion.inquilino

        # Un saludo suelto («hola», «gracias», «vale») no es una entrada de
        # diario. Antes de esto caía al diario igual que cualquier otra cosa
        # sin clasificar y se escribía tal cual — comprobado en Madre el
        # 2026-09-18. Va ANTES de entender(): ni hace falta un modelo para
        # saberlo, ni tiene sentido pagar la llamada por algo que un regex
        # ya resuelve.
        if entender.es_saludo(texto):
            return Respuesta(texto=mensajes.SALUDO)

        # inquilino delante y no en cada rama: "pregunta" sobre el servicio
        # que se ofrece (tarifas/faq) solo se reconoce con el inquilino
        # puesto — sin él, entender() se queda en su sentido más estrecho
        # (solo lo ya apuntado). Ver personal/entender.py::_instrucciones.
        entendido = entender.entender(texto, self._preguntar, inq)
        if entendido is not None:
            try:
                return Respuesta(texto=enrutar.enrutar(
                    entendido, inq, self._subir, self._responder_pregunta))
            except ValueError:
                logger.info("«%s» clasificado como %s pero no se pudo aplicar; va al diario",
                            texto[:80], entendido.intencion)
            except Exception:
                logger.exception("Error apuntando %s desde el mensaje suelto; va al diario",
                                 entendido.intencion)

        # «cené con mi hermana ayer» va al día de ayer, sin el «ayer». Solo
        # el pasado sin ambigüedad cuenta (fechas.fecha_detras): «tengo
        # examen mañana» es una frase de hoy y se queda entera.
        texto, fecha = fechas_personal.fecha_detras(texto)
        try:
            ruta = diario.organizar_texto(texto, fecha=fecha)
            subido = self._subir(ruta, None)
            return Respuesta(
                texto=f"📔 Apuntado en el diario {mensajes.dia(fecha)}"
                      f"{enrutar.coletilla(subido)}")
        except Exception as e:
            logger.exception("Error escribiendo un mensaje suelto en el diario")
            return Respuesta(texto=f"{mensajes.ERROR}{e}")
