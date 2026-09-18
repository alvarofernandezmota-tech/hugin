"""Contestar a una pregunta sobre tus propios datos, en prosa.

Portado de `diario/conversar.py` de midgaror (ADR-021, ADR-024 fase 5). La
otra mitad de `entender.py`. Aquel decide dónde va lo que escribes; este
contesta cuando lo que escribes **no va a ningún sitio porque es una
pregunta**: «¿qué tengo mañana?», «¿cuánto llevo de deporte esta semana?»,
«¿se me olvida algo?».

## La regla de la casa, otra vez: el modelo LEE, no escribe

`entender.py` la dice para la escritura —el modelo clasifica y son
`hugin.personal.tareas.agregar` y compañía quienes escriben—. Aquí va en el
otro sentido y es igual de dura: este módulo **no importa una sola función
que escriba**. Ni `agregar`, ni `marcar`, ni `apuntar`, ni `guardar`. Solo
los cuatro `resumen*`, que son exactamente los que ya pintan lo que ves con
`/hoy`.

Eso no es estilo. Un modelo que puede leer *y* escribir en la misma vuelta
convierte «¿tengo dentista el jueves?» en una cita nueva el jueves, y el
error no se ve hasta que llega el jueves. Leyendo solo, lo peor que puede
pasar es que conteste mal a una pregunta, y eso se ve al leerlo.
`tests/test_conversar_personal.py` lo comprueba sobre el texto del módulo:
si algún día alguien añade aquí un import que escribe, la prueba se cae.

## Por qué los datos que ve son los `resumen*` y no los ficheros/tablas

Podría leer los datos enteros y pasárselos. Sería más «completo» y sería
peor por tres razones:

1. Llevan dentro el histórico entero. Meterlo todo en cada pregunta es
   pagar por miles de líneas para contestar «¿qué tengo hoy?».
2. Los `resumen*` ya resuelven lo difícil: qué tarea está activa, qué cita
   es de esta semana, cómo se formatea un hábito. Repetir ese criterio aquí
   sería una segunda versión que se va separando de la primera.
3. Lo que ve el modelo es **lo mismo que ves tú** con `/hoy`. Cuando
   conteste algo raro, se puede mirar el mismo texto y ver de dónde lo sacó.

## Sin motor, esto no existe

Igual que `entender()`: sin ningún motor configurado, `responder()` devuelve
`None` y quien llama sigue con lo de siempre —escribirlo en el diario—. Un
fallo de red, un JSON roto o un modelo que declina también dan `None`. Este
módulo no puede hacer que se pierda un mensaje.

## El mismo Claude/Ollama que `entender.py`

`entender.proveedor()` decide con qué motor se contesta, así que aquí no se
repite la variable: si `MIDGAROR_LLM=ollama`, tanto clasificar como
contestar corren en la máquina de Madre; si es Claude, los dos van a la
API. Una pregunta nunca sale a un sitio distinto de donde salió su frase.

## `inq=`, a diferencia del original

En midgaror había un solo diario y `tareas.resumen()`/`agenda.resumen()`/
`habitos.resumen_dia()`/`registro.resumen_dia()` no pedían de quién. Aquí sí
—cada uno guarda contra un inquilino (ADR-024)—, así que `datos()` y
`responder()` reciben `inq` y lo pasan tal cual a los cuatro `resumen*`.
"""

from hugin import apuntes as registro
from hugin.personal import citas, entender, habitos, tareas

# Cuánto texto de tus datos se le enseña al modelo, como mucho.
#
# No es por dinero, es porque un contexto largo contesta peor: con seis meses
# de tareas delante, «¿qué tengo hoy?» se contesta con algo de marzo. Los
# `resumen*` ya vienen acotados, pero los apuntes pueden tener un día con
# cuarenta líneas, así que hay un tope duro y se avisa de que se cortó —un
# resumen recortado en silencio es un resumen que miente.
TOPE_CARACTERES = 6000

# Más largo que el de `entender`: aquí se redacta una respuesta, no se
# devuelven ocho campos, y cortar a los 4 s deja al usuario sin nada.
TOPE_SEGUNDOS = 12.0

# Con Ollama hace falta el mismo margen que en entender.py, y por el mismo
# motivo: la CPU de Madre sin GPU, aquí encima redactando una respuesta en
# prosa en vez de clasificar ocho campos, que es más lento todavía. Se
# reutiliza la constante de entender.py en vez de inventar un segundo
# número: una sola fuente de verdad para "cuánto tarda Ollama en Madre".
TOPE_SEGUNDOS_OLLAMA = entender.TOPE_SEGUNDOS_OLLAMA

# Espacio para la respuesta. Da para un párrafo largo o una lista de ocho
# líneas, que es el tamaño de lo que se lee en un móvil sin hacer scroll.
TOPE_PALABRAS = 400

INSTRUCCIONES = """Eres el diario personal de alguien, contestando por \
Telegram a una pregunta sobre sus propios datos. Abajo van sus tareas, su \
agenda, sus hábitos y sus apuntes de hoy, tal y como se los pintaría la app.

Contesta corto y directo, como contestaría un amigo que tiene la lista \
delante. Sin saludos, sin «según tus datos», sin repetir la pregunta. Si la \
respuesta son tres cosas, son tres líneas, no un párrafo.

Tres reglas que no se saltan:

- **Solo lo que está abajo.** Si la respuesta no está en esos datos, dilo: \
«no tienes nada apuntado de eso». No completes con lo que suene razonable.
- **No inventes fechas, números ni nombres.** Si una tarea no tiene fecha, \
no tiene fecha; no es «seguramente esta semana».
- **No prometas hacer nada.** No puedes crear tareas, citas ni apuntes \
desde aquí. Si te piden que apuntes algo, di que lo escriban sin el signo \
de interrogación y se apunta solo.

Si la pregunta no va sobre estos datos, dilo en una línea en vez de \
inventarte una respuesta."""


def configurado() -> bool:
    """¿Hay clave? Sin ella esto no existe. Es la misma de `entender`."""
    return entender.configurado()


def modelo() -> str:
    return entender.modelo()


def _recortar(texto: str, tope: int = TOPE_CARACTERES) -> str:
    """El texto, o su principio con un aviso de que falta lo demás."""
    if len(texto) <= tope:
        return texto
    return texto[:tope].rstrip() + "\n\n[…cortado: hay más de lo que cabe aquí]"


def _o_nada(hacer, si_falla: str) -> str:
    """Llama a `hacer()`, o devuelve `si_falla` si revienta.

    Que falten datos —o que estén a medio escribir justo en ese momento— no
    puede dejar sin contestar una pregunta que va de otra cosa.
    """
    try:
        return hacer()
    except Exception:
        return si_falla


def _apuntes_de_hoy(inq=None) -> str:
    """Los apuntes de hoy en texto. `resumen_dia` devuelve un dict."""
    datos = registro.resumen_dia(inq=inq)
    lineas = datos.get("lineas") or []
    if not lineas:
        return "Sin apuntes hoy."
    return "\n".join(str(linea) for linea in lineas)


def datos(inq=None) -> str:
    """Todo lo que el modelo puede ver, en el mismo formato que lo ves tú.

    Cuatro bloques con título. El título importa: sin él, una lista de
    fechas sueltas no se distingue de otra, y el modelo mezcla una cita con
    una tarea.
    """
    bloques = (
        ("TAREAS", lambda: tareas.resumen(inq), "No se pudieron leer las tareas."),
        ("AGENDA (esta semana)", lambda: citas.resumen(inq=inq, semana=True),
         "No se pudo leer la agenda."),
        ("HÁBITOS DE HOY", lambda: habitos.resumen_dia(inq=inq),
         "No se pudieron leer los hábitos."),
        ("APUNTES DE HOY", lambda: _apuntes_de_hoy(inq), "No se pudieron leer los apuntes."),
    )
    return _recortar("\n\n".join(
        f"## {titulo}\n{_o_nada(hacer, si_falla)}" for titulo, hacer, si_falla in bloques
    ))


def _preguntar_claude(pregunta: str, contexto: str) -> str:
    """La llamada a la API. Separada para poder sustituirla en las pruebas."""
    import anthropic

    cliente = anthropic.Anthropic(timeout=TOPE_SEGUNDOS, max_retries=0)
    respuesta = cliente.beta.messages.create(
        model=modelo(),
        max_tokens=TOPE_PALABRAS * 2,
        system=INSTRUCCIONES,
        messages=[{"role": "user",
                   "content": f"{contexto}\n\n---\n\nPregunta: {pregunta}"}],
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("el modelo declinó la petición")
    return "".join(b.text for b in respuesta.content if b.type == "text").strip()


def _preguntar_ollama(pregunta: str, contexto: str) -> str:
    """Lo mismo, pero contra un modelo de esta máquina. Nada sale de Madre.

    Sin `format`: aquí se redacta una respuesta en prosa, no se rellena un
    esquema. `stream: False` para leer la respuesta entera de una vez, igual
    que hace el cliente de Anthropic.
    """
    import json
    import urllib.request

    cuerpo = json.dumps({
        "model": modelo(),
        "messages": [{"role": "system", "content": INSTRUCCIONES},
                     {"role": "user",
                      "content": f"{contexto}\n\n---\n\nPregunta: {pregunta}"}],
        "stream": False,
    }).encode("utf-8")
    peticion = urllib.request.Request(
        f"{entender.ollama()}/api/chat", data=cuerpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=TOPE_SEGUNDOS_OLLAMA) as respuesta:
        contestado = json.loads(respuesta.read().decode("utf-8"))
    return (contestado["message"]["content"] or "").strip()


def responder(pregunta: str, preguntar=None, contexto=None, inq=None) -> str | None:
    """La respuesta a `pregunta`, o `None` si aquí no hay nada que hacer.

    `None` significa siempre lo mismo para quien llama: sigue como antes,
    escribe la frase en el diario. Cubre no tener clave, cualquier error al
    preguntar, y una respuesta vacía —contestar con una burbuja en blanco es
    peor que no contestar, porque parece que se ha tragado el mensaje.
    """
    if not (pregunta or "").strip():
        return None
    if preguntar is None:
        cual = entender.proveedor()
        if not cual:
            return None
        preguntar = _preguntar_ollama if cual == "ollama" else _preguntar_claude
    try:
        respuesta = preguntar(pregunta, datos(inq) if contexto is None else contexto)
    except Exception:
        return None
    return (respuesta or "").strip() or None
