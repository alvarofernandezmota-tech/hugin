"""Entender una frase suelta: ¿tarea, hábito, cita, apunte, pregunta, o diario?

Portado de `diario/entender.py` de midgaror (ADR-020, ADR-024 fase 5). Sin
`inq=`: a diferencia de tareas/citas/habitos/apuntes, este módulo no
persiste nada — clasifica y devuelve datos, quien llama decide a qué
función de `hugin.personal`/`hugin.apuntes` llamar y con qué `inq`.

Si escribes «recuérdame llamar al médico mañana» sin poner `/tarea`
delante, sin esto se apuntaría tal cual en el diario y ahí se quedaría: no
hay tarea, no hay aviso, nada que marcar como hecha. Esto es lo que decide
si de verdad es otra cosa. **Opcional y con red de seguridad**: sin ningún
motor configurado, casi todo cae al diario tal cual —salvo los patrones tan
claros que resuelve `_reglas()` sin preguntarle a nadie—, y con motor, solo
actúa cuando está seguro. Todo lo demás —sin motor y sin regla que case,
error de red, confianza media o baja, o la propia frase que resulta ser
diario de verdad— sigue yendo al diario. Este módulo no puede hacer que se
pierda nada: en el peor caso, deja de reconocer una tarea y la escribe en
el diario, que es lo que ya pasaba antes de que existiera.

## Cuatro motores, el mismo patrón que `hugin/mente/cerebro.py`

    MIDGAROR_LLM=anthropic   + ANTHROPIC_API_KEY   Claude, en la nube (de pago)
    MIDGAROR_LLM=groq        + GROQ_API_KEY        Groq, en la nube (gratis, con límite)
    MIDGAROR_LLM=google      + GOOGLE_API_KEY       Gemini, en la nube (gratis, con límite)
    MIDGAROR_LLM=ollama                            un modelo en esta máquina

Mismos nombres de variable que en producción (Madre ya los tiene puestos en
su `.env`): el porte no le cambia a nadie la configuración. Con Claude
acierta más y el texto sale de casa hacia la API; con Groq/Google sale
también, pero sin coste mientras no se pase el límite gratuito de
peticiones —y con la letra pequeña de cada uno sobre qué hace con lo que le
mandas, que en un diario personal importa—; con Ollama no sale nada, el
modelo corre en la misma máquina que el bot, y a cambio acierta menos y
tarda más. Sin `MIDGAROR_LLM`, Claude si hay clave y nada si no la hay:
elegir uno de los otros tres es siempre explícito, nunca el default.

## La regla de la casa, la misma que en `mente/cerebro.py`

El modelo **clasifica, no escribe**. Su salida son ocho campos con forma
fija, nunca una frase para el usuario. Quien decide si la fecha vale, si el
hábito existe o si el valor es un número lo sigue decidiendo
`hugin.personal.tareas.agregar`, `hugin.personal.habitos.marcar`,
`hugin.personal.citas.agregar` y `hugin.apuntes.apuntar` — las mismas
funciones que ya usan `/tarea`, `/habito`, `/cita` y `/apunte`.
`entender()` no toca ningún dato: solo dice a cuál de las cuatro llamar y
con qué argumentos.

## Por qué el import de `anthropic` está DENTRO de la función

Este módulo se importa en cuanto arranca el bot de Telegram, en la máquina
de producción. Si `anthropic` estuviera importado arriba y no estuviese
instalado, el bot entero dejaría de arrancar por una función que nadie ha
activado todavía. Con el import dentro de `_preguntar_claude`,
`configurado()` corta antes de llegar ahí mientras no haya clave.

## El fallo del «hola» (Madre, 2026-09-18)

Nada de lo de arriba distingue «esto no es nada reconocible, y tampoco
parece diario de verdad» de «esto es diario». Un simple «hola» clasifica
como `diario` (por diseño: la propia instrucción del LLM dice «ante la duda,
diario») y `procesar()` en `handlers/texto.py` manda TODO lo que no se
clasificó al diario, sin distinguir. Resultado: un saludo se escribía como
entrada de diario. `es_saludo()` es la red de seguridad de más, del mismo
tipo que `_reglas()` —estricta, sin LLM, sin ambigüedad—: el mensaje
ENTERO tiene que ser uno de una lista corta y cerrada, para no tragarse un
«hola, hoy ha sido un día raro» que sí es diario de verdad.
"""

import json
import os
import re
import threading
from dataclasses import dataclass

INTENCIONES = ("tarea", "habito", "cita", "apunte", "pregunta", "diario")

# Las que acaban escribiendo algo. `pregunta` no está, y por eso `conversar`
# no puede tocar nada: llega por una rama que no pasa por ningún `agregar`.
ESCRIBEN = ("tarea", "habito", "cita", "apunte")
CONFIANZAS = ("alta", "media", "baja")

MODELO_POR_DEFECTO = "claude-opus-5"
# Un modelo pequeño y multilingüe: lo que cabe en Madre (GTX 1060, 6 GB de
# VRAM, Pascal — sin FlashAttention) y entiende castellano. El mismo por
# defecto que usa hugin/mente/cerebro.py contra el mismo hardware. Cambiado
# el 2026-09-18 de qwen2.5:7b (nunca llegó a descargarse en Madre, y a 4.7 GB
# en Q4_K_M deja poco margen de VRAM sin FlashAttention) a esta variante:
# Qwen3, no Qwen2.5, y la revisión "-instruct-2507" en concreto porque NUNCA
# activa el modo de razonamiento por defecto de Qwen3/3.5 —ese modo tiene
# bugs abiertos en Ollama que rompen la salida estructurada (`format`) justo
# en lo que aquí más importa: el campo `confianza`—. En Q4_K_M pesa ~2.5 GB,
# con margen real de sobra en 6 GB. Se cambia con MIDGAROR_LLM_MODELO.
MODELO_LOCAL_POR_DEFECTO = "qwen3:4b-instruct-2507"
# Rápido, gratis con límite de peticiones, JSON mode nativo. La familia
# 3.3 corre a ~300 tok/s en la infraestructura de Groq (LPU, no GPU) — muy
# por encima del tope de 4s/20s de aquí. Se cambia con MIDGAROR_LLM_MODELO.
MODELO_GROQ_POR_DEFECTO = "llama-3.3-70b-versatile"
# Gratis con límite de peticiones, buen soporte de castellano y JSON Schema
# nativo (`responseSchema`). Sin el "-preview" de las últimas versiones a
# propósito: una entrada en producción no debería depender de un modelo que
# puede cambiar o desaparecer sin aviso.
MODELO_GOOGLE_POR_DEFECTO = "gemini-2.5-flash"
OLLAMA_POR_DEFECTO = "http://127.0.0.1:11434"
TOPE_SEGUNDOS = 4.0
# Con Ollama hace falta más margen, y no por descuido: en hugin/mente/
# cerebro.py el 4.0 es a propósito porque ahí hay una llamada de teléfono en
# vivo esperando. Aquí no hay nadie al otro lado del hilo esperando en
# directo — es un mensaje de Telegram, y el bot ya saca la llamada del
# bucle de eventos con `asyncio.to_thread` para que no se congele para el
# resto de chats mientras tanto. Copiar el 4.0 tal cual haría fallar por
# timeout un modelo de 7B en una CPU sin GPU casi cada vez, no por un
# problema real sino por un límite pensado para otro sitio.
TOPE_SEGUNDOS_OLLAMA = 20.0

_cliente = None
# Dos mensajes de chats distintos pueden llamar a entender() en paralelo
# (asyncio.to_thread en handlers/texto.py) y pisarse el «if _cliente is
# None» de abajo. Benigno —como mucho se crea un cliente de más y se
# descarta—, pero barato de evitar del todo con un candado.
_candado_cliente = threading.Lock()


@dataclass(frozen=True)
class Entendido:
    """Lo que se ha entendido de la frase. Datos, nunca una respuesta."""

    intencion: str
    texto: str | None = None       # tarea/cita: la frase entera, con su cuándo dentro
    nombre: str | None = None      # habito/apunte: el qué
    hecho: bool = True             # habito: sí o no
    valor: float | None = None     # habito (1-10)/apunte (cantidad)
    unidad: str | None = None      # apunte: «h», «l»...
    cuando: str | None = None      # habito/apunte: «ayer», «el lunes»… tal cual lo dijo
    confianza: str = "baja"


# «recuérdame X» es el más inequívoco de los seis. Cazarlo con una expresión
# regular significa que funciona SIEMPRE, sin motor, sin clave y sin Ollama
# instalado — no porque el motor esté de más, sino porque para este único
# patrón preguntarle a un LLM es pagar por algo que un regex ya resuelve
# igual de bien.
#
# A propósito NO se convierte en un motor de reglas grande: solo los
# patrones donde una frase de diario de verdad casi nunca tiene esa forma
# exacta. Todo lo que no case aquí sigue el camino de siempre: el motor si
# lo hay, si no, el diario.
_RECORDATORIO = re.compile(r"^\s*recu[ée]rdame\s+(?:que\s+)?(.+)$", re.IGNORECASE)

# «tele 3h», «agua 1,5 litros», «correr 5km»: UNA palabra, un número, y una
# unidad OBLIGATORIA — y NADA más en el mensaje. Dos veces más estricto de
# lo que parece necesario, y a propósito:
#
# - Con dos palabras de nombre, «he dormido 8» o «son las 5» también
#   casaban: casi cualquier frase corta con un verbo delante y un número
#   detrás colaba como apunte con un nombre sin sentido.
# - Con la unidad opcional, «energía 7» —ejemplo de HÁBITO, no de apunte,
#   en las propias INSTRUCCIONES— también casaba. Un hábito medido casi
#   nunca lleva unidad; un apunte de verdad casi siempre sí.
#
# Mismos caracteres que acepta `hugin.apuntes.normalizar_que()` (acentos y
# ñ incluidos), para no aceptar aquí lo que ese módulo iba a rechazar después.
_APUNTE = re.compile(
    r"^\s*([a-záéíóúñ]+)\s+(\d+(?:[.,]\d+)?)\s*([a-záéíóúñ]+)\s*$",
    re.IGNORECASE)

# El fallo del «hola» (ver el docstring del módulo): el mensaje ENTERO tiene
# que ser uno de estos, nada más — «hola, qué día tan raro» no casa, y va al
# diario como siempre. Lista corta y cerrada a propósito, igual que
# _RECORDATORIO/_APUNTE: no es un detector de "mensajes cortos" (un hábito
# real puede ser una palabra, «cansado»), es un detector de saludo puro.
_SALUDOS = frozenset({
    "hola", "holaa", "holaaa", "holi", "hey", "ey", "eh",
    "buenas", "buenos dias", "buenas tardes", "buenas noches",
    "hi", "hello",
    "adios", "adiós", "chao", "chau", "hasta luego", "hasta pronto",
    "gracias", "muchas gracias", "vale", "ok", "okay", "okey",
})


def es_saludo(frase: str) -> bool:
    """Si el mensaje entero es un saludo o una muletilla, sin nada más.

    No pasa por `entender()`: no hace falta LLM, ni configurarlo, para
    saber que "hola" no es una entrada de diario.
    """
    limpio = re.sub(r"[¡!¿?.,;:]", "", frase.strip().lower())
    limpio = " ".join(limpio.split())
    return limpio in _SALUDOS


def _reglas(frase: str) -> Entendido | None:
    """Patrones tan claros que no hace falta preguntarle a ningún motor."""
    coincide = _RECORDATORIO.match(frase)
    if coincide:
        resto = coincide.group(1).strip()
        if resto:
            return Entendido(intencion="tarea", texto=resto, confianza="alta")
        return None

    coincide = _APUNTE.match(frase)
    if coincide:
        nombre, valor, unidad = coincide.groups()
        return Entendido(
            intencion="apunte",
            nombre=nombre.strip(),
            valor=float(valor.replace(",", ".")),
            unidad=unidad.strip() or None,
            confianza="alta",
        )

    return None


def proveedor() -> str:
    """Qué motor se usa: «anthropic», «ollama», «groq», «google» o «» si no hay ninguno.

    Sin `MIDGAROR_LLM`, lo de siempre: Claude si hay clave y nada si no.
    Mismo criterio que `hugin/mente/cerebro.py`, misma variable con otro
    prefijo. Groq y Google (Gemini) son gratuitos con límite de peticiones,
    y cada uno necesita su propia clave (`GROQ_API_KEY`, `GOOGLE_API_KEY`)
    para contar como configurado — igual que Claude con `ANTHROPIC_API_KEY`.
    Elegir uno sin su clave puesta no enciende nada, igual que pasaba ya con
    Claude: nunca un `MIDGAROR_LLM` mal puesto tira el bot, cae al camino de
    siempre (diario).
    """
    elegido = os.environ.get("MIDGAROR_LLM", "").strip().lower()
    if elegido in ("no", "off", "ninguno", "0"):
        return ""
    if elegido in ("ollama", "local"):
        return "ollama"
    if elegido in ("groq",):
        return "groq" if os.environ.get("GROQ_API_KEY", "").strip() else ""
    if elegido in ("google", "gemini"):
        return "google" if os.environ.get("GOOGLE_API_KEY", "").strip() else ""
    # "anthropic"/"claude" explícitos y cualquier otra cosa (vacío, una
    # errata) acaban en el mismo sitio: Claude si hay clave, nada si no.
    return "anthropic" if os.environ.get("ANTHROPIC_API_KEY", "").strip() else ""


def configurado() -> bool:
    """¿Hay algún motor con el que contar? Sin él, esto no existe."""
    return bool(proveedor())


def modelo() -> str:
    propio = os.environ.get("MIDGAROR_LLM_MODELO", "").strip()
    if propio:
        return propio
    return {
        "ollama": MODELO_LOCAL_POR_DEFECTO,
        "groq": MODELO_GROQ_POR_DEFECTO,
        "google": MODELO_GOOGLE_POR_DEFECTO,
    }.get(proveedor(), MODELO_POR_DEFECTO)


def ollama() -> str:
    return os.environ.get("MIDGAROR_OLLAMA", "").strip() or OLLAMA_POR_DEFECTO


ESQUEMA = {
    "type": "object",
    "properties": {
        "intencion": {"type": "string", "enum": list(INTENCIONES)},
        "texto": {"type": ["string", "null"]},
        "nombre": {"type": ["string", "null"]},
        "hecho": {"type": "boolean"},
        "valor": {"type": ["number", "null"]},
        "unidad": {"type": ["string", "null"]},
        "cuando": {"type": ["string", "null"]},
        "confianza": {"type": "string", "enum": list(CONFIANZAS)},
    },
    "required": ["intencion", "texto", "nombre", "hecho", "valor",
                 "unidad", "cuando", "confianza"],
    "additionalProperties": False,
}

INSTRUCCIONES = """Vas a leer un mensaje suelto que alguien le escribe a su \
propio diario personal por Telegram, sin usar ningún comando. Tu trabajo es \
decidir a qué se parece más, de estas seis:

- tarea: algo que hay que hacer, con fecha o sin ella («recuérdame llamar al \
médico», «llevar el coche al taller el jueves»). Pon la frase ENTERA en \
`texto`, con el cuándo dentro si lo dijo: la fecha se la saca otra función, \
tú no la calcules.
- cita: un compromiso a una hora concreta con alguien o en algún sitio \
(«dentista el jueves a las 5», «como con mi hermana mañana»). Igual que \
tarea: la frase entera en `texto`, cuándo incluido.
- habito: algo que YA se ha hecho o no se ha hecho hoy, o un valor que se \
mide («he hecho deporte», «no he meditado», «energía 7», «he dormido fatal» \
si hay un hábito de sueño evidente). `nombre` es el hábito en una o dos \
palabras en infinitivo o sustantivo («deporte», «meditar»); `hecho` es \
`false` solo si lo niega explícitamente («no he...», «sin...»); `valor` solo \
si dio un número; `cuando` solo si dijo un día distinto de hoy («ayer», «el \
lunes»), si no, null.
- apunte: una cantidad de algo que se hizo hoy, con o sin unidad («tele \
3h», «agua 1,5 litros», «he corrido 5km»). `nombre` es el qué («tele», \
«agua», «correr»); `valor` el número; `unidad` si la dijo; `cuando` si dijo \
otro día.
- pregunta: pide información sobre lo que YA está apuntado, no apunta nada \
nuevo («¿qué tengo mañana?», «¿cuánto llevo de deporte esta semana?», «¿se \
me olvida algo?», «dime mis tareas»). Todos los campos a null, `texto` \
incluido: no hay nada que guardar, solo algo que contestar, y la frase la \
tiene ya quien te llama. Ojo con las dos que se parecen y no \
son lo mismo: «¿voy al dentista el jueves?» es una pregunta —quiere saber si \
ya está apuntado—, y «dentista el jueves» es una cita. Si no está preguntando \
por algo que ya debería existir, no es pregunta.
- diario: cualquier otra cosa. Un sentimiento, un relato de lo que ha \
pasado, una reflexión, algo ambiguo. Es el valor por defecto: ante la duda, \
diario.

No inventes nada que no esté en la frase. Si dudas entre dos categorías, o \
la frase podría ser las dos cosas, es media o baja confianza y no alta. \
`confianza` es "alta" solo cuando no hay otra lectura razonable — de eso \
depende que esto se guarde donde toca en vez de perderse, así que ante la \
mínima duda, confianza más baja, nunca alta a ciegas.

Devuelve SOLO el JSON con los ocho campos. Los que no apliquen, van a null \
(o `true` en `hecho` si no es un hábito)."""


def _preguntar_claude(frase: str) -> dict:
    """La llamada a la API. Separada para poder sustituirla en las pruebas."""
    global _cliente
    import anthropic

    if _cliente is None:
        with _candado_cliente:
            if _cliente is None:  # otro hilo pudo crearlo mientras esperaba
                _cliente = anthropic.Anthropic(timeout=TOPE_SEGUNDOS, max_retries=0)

    respuesta = _cliente.beta.messages.create(
        model=modelo(),
        max_tokens=256,
        system=INSTRUCCIONES,
        messages=[{"role": "user", "content": frase}],
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": ESQUEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("el modelo declinó la petición")
    texto = next(b.text for b in respuesta.content if b.type == "text")
    return json.loads(texto)


def _preguntar_ollama(frase: str) -> dict:
    """Lo mismo, pero contra un modelo de esta máquina. Nada sale de Madre.

    Por HTTP a Ollama y con `urllib`, sin cliente ni dependencia nueva.
    Mismo patrón que `hugin/mente/cerebro.py::_preguntar_ollama`.
    """
    import urllib.request

    cuerpo = json.dumps({
        "model": modelo(),
        "messages": [{"role": "system", "content": INSTRUCCIONES},
                     {"role": "user", "content": frase}],
        "format": ESQUEMA,
        "stream": False,
        # Sin creatividad: esto clasifica, no escribe. num_ctx fijo a
        # proposito y no al default de Ollama: ese default se calcula segun
        # la VRAM libre en el momento (variable, y con documentacion propia
        # de Ollama que no siempre coincide consigo misma) — un mensaje
        # suelto mas el esquema no necesita mucho, pero mejor no dejarlo a
        # una heuristica que puede cambiar de version en version.
        "options": {"temperature": 0, "num_ctx": 4096},
    }).encode("utf-8")
    peticion = urllib.request.Request(
        f"{ollama()}/api/chat", data=cuerpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=TOPE_SEGUNDOS_OLLAMA) as respuesta:
        contestado = json.loads(respuesta.read().decode("utf-8"))
    return json.loads(contestado["message"]["content"])


def _preguntar_groq(frase: str) -> dict:
    """Lo mismo, contra Groq. API compatible con la de OpenAI, sin cliente.

    `response_format: json_object` en vez de `json_schema` con `strict`:
    ese modo estricto solo está en "modelos seleccionados" según la propia
    documentación de Groq, y no hay garantía de que el de `modelo()` sea
    uno de ellos. `json_object` sí está en todos y ya obliga a un JSON
    válido; que tenga los ocho campos con la forma que toca lo comprueba
    `entender()` después, igual que con cualquier otro motor. La palabra
    "JSON" tiene que aparecer en algún mensaje para que la API la acepte —
    ya está, en la última frase de `INSTRUCCIONES`.
    """
    import urllib.request

    clave = os.environ.get("GROQ_API_KEY", "").strip()
    cuerpo = json.dumps({
        "model": modelo(),
        "messages": [{"role": "system", "content": INSTRUCCIONES},
                     {"role": "user", "content": frase}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }).encode("utf-8")
    peticion = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=cuerpo,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {clave}"},
        method="POST")
    with urllib.request.urlopen(peticion, timeout=TOPE_SEGUNDOS) as respuesta:
        contestado = json.loads(respuesta.read().decode("utf-8"))
    return json.loads(contestado["choices"][0]["message"]["content"])


def _preguntar_google(frase: str) -> dict:
    """Lo mismo, contra la API de Google AI Studio (Gemini).

    `responseSchema` con el ESQUEMA tal cual: la documentación de Google
    dice que sus modelos ya aceptan JSON Schema estándar, no un dialecto
    propio. Si algún día dejara de ser así, esto lo diría fallando —el
    `except` de `entender()` se lo traga igual que cualquier otro fallo de
    red o de JSON, cae al diario, nunca revienta.
    """
    import urllib.request

    clave = os.environ.get("GOOGLE_API_KEY", "").strip()
    cuerpo = json.dumps({
        "system_instruction": {"parts": [{"text": INSTRUCCIONES}]},
        "contents": [{"role": "user", "parts": [{"text": frase}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": ESQUEMA,
            "temperature": 0,
        },
    }).encode("utf-8")
    peticion = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{modelo()}:generateContent?key={clave}",
        data=cuerpo, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=TOPE_SEGUNDOS) as respuesta:
        contestado = json.loads(respuesta.read().decode("utf-8"))
    texto = contestado["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(texto)


def entender(frase: str, preguntar=None) -> Entendido | None:
    """Clasifica `frase`, o `None` si hay que mandarla al diario como siempre.

    `None` cubre TODO lo que no es un «sí, alta confianza, no es diario»:
    sin clave configurada, error al preguntar (red, JSON roto, lo que sea),
    confianza media o baja, e intención «diario». Quien llama no necesita
    distinguir estos casos: la respuesta es la misma para todos, escribir
    en el diario tal cual. `es_saludo()` es aparte a propósito — no pasa
    por aquí, es un chequeo previo de quien llama (ver su docstring).

    `pregunta` sí sale de aquí, con todos los demás campos vacíos: no hay
    nada que guardar. Quien llama la manda a `conversar.responder()`, que
    lee y contesta sin tocar un solo dato. Y si eso falla, vuelve a pasar
    lo de siempre: al diario.

    Antes de tocar ningún motor, y solo cuando nadie ha puesto un
    `preguntar` a mano (producción de verdad, nunca una prueba con su
    propio doble), `_reglas()` prueba los patrones que no necesitan
    preguntar a nadie.
    """
    if preguntar is None:
        regla = _reglas(frase)
        if regla is not None:
            return regla
        cual = proveedor()
        if not cual:
            return None
        preguntar = {
            "ollama": _preguntar_ollama,
            "groq": _preguntar_groq,
            "google": _preguntar_google,
        }.get(cual, _preguntar_claude)
    try:
        datos = preguntar(frase)
        intencion = datos.get("intencion")
        confianza = datos.get("confianza")
        if intencion not in INTENCIONES or confianza not in CONFIANZAS:
            return None
        if confianza != "alta" or intencion == "diario":
            return None
        return Entendido(
            intencion=intencion,
            # En `pregunta`, `texto` es la frase original tal cual la
            # escribió, puesta aquí y no por el modelo: repetir una frase
            # entera es pagar por generarla y arriesgarse a que la resuma o
            # le corrija una tilde. Aquí ya la tenemos delante: se copia.
            texto=frase if intencion == "pregunta" else datos.get("texto"),
            nombre=datos.get("nombre"),
            hecho=datos.get("hecho", True),
            valor=datos.get("valor"),
            unidad=datos.get("unidad"),
            cuando=datos.get("cuando"),
            confianza=confianza,
        )
    except Exception:
        # Cualquier fallo aquí —red, límite de la API, un JSON que no cuadra
        # con el esquema, lo que sea— cae al diario. Nunca una excepción que
        # le llegue al usuario ni que se trague el mensaje sin guardarlo.
        return None
