"""El LLM, opcional, para lo que las reglas no entienden. Nunca para el precio.

Las reglas de `recepcion.py` cubren lo que se pide por teléfono en un negocio
—precio, cita, anular, horario, lo que esté escrito en los `.md`— y todo lo
demás acaba en «tomo nota». Funciona y no se inventa nada, pero «oye, que me
han dicho que hacéis lo del alisado ese, ¿lo tenéis?» se pierde en un recado.

Aquí entra Claude **solo cuando las reglas y el buscador no han entendido**, y
solo para devolver datos con forma fija:

    intencion   precio | cita | anular | cambiar | horario | despedida | otro
    servicio    uno de los nombres de la tabla de tarifas, o ninguno
    cuando      «el jueves a las cinco», tal cual lo dijo, para fechas.py
    franja      manana | tarde | noche, si la dijo de otra forma
    nombre      si lo dio
    confianza   alta | media | baja

Lo que hace `recepcion.py` con eso es lo mismo que haría con una frase que las
reglas sí entienden: el precio sale de la tabla, la fecha la resuelve
`fechas.py`, la agenda decide si cabe. **El modelo no redacta lo que se le
dice al cliente y no pone ningún número.** Es la regla de la casa, y la forma
de garantizarla es que su salida sea un JSON de seis campos, no una frase.

Por eso aquí no hay ningún `contestar()`: no es un olvido. El día que el
modelo redacte, redactará precios, y ese día esto deja de poder prometer que
un precio sale de la tabla.

## Lo que ve el modelo

Tres cosas, y las tres importan para acertar:

1. **La frase**, transcrita por el proveedor, con sus erratas.
2. **Los últimos turnos de la llamada.** Sin ellos, «¿y el jueves?» no es
   nada. Van como mensajes de verdad, que es como el modelo los entiende.
3. **Lo que el negocio tiene escrito sobre eso**, recuperado por `rag.py`.
   Así «lo del alisado» encuentra el tratamiento de keratina si el dueño lo
   escribió en algún `.md`, en vez de que el modelo se lo imagine.

## Apagado por defecto, y cuatro formas de encenderlo

Sin nada configurado, las reglas solas, como hasta ahora. Y hay cuatro
motores, que no son lo mismo para quien lleva el negocio:

    GJALLARHORN_LLM=anthropic   + ANTHROPIC_API_KEY   Claude, en la nube (de pago)
    GJALLARHORN_LLM=groq        + GROQ_API_KEY        Groq, en la nube (gratis, con límite)
    GJALLARHORN_LLM=google      + GOOGLE_API_KEY       Gemini, en la nube (gratis, con límite)
    GJALLARHORN_LLM=ollama                             un modelo en esta máquina
    GJALLARHORN_LLM=auto                                nube primero, Ollama si falla

Con Claude/Groq/Google acierta más y **el texto de lo que dijo el cliente
sale de casa** hacia la API; el audio no, el texto sí. Con Ollama no sale
nada de la máquina: el modelo corre en el mismo ordenador que atiende el
teléfono, y a cambio acierta menos y tarda más, lo que en un teléfono se
nota. Entre las tres de la nube: Claude es de pago y sin letra pequeña
sobre entrenar con lo que se le manda; Groq y Google tienen nivel gratuito
con límite de peticiones, y conviene mirar los términos de cada uno antes
de mandarles lo que dice un cliente — más aún si el negocio trata datos
sensibles.

Cuál de los cuatro es cosa del negocio, no de este fichero, y por eso no
viene puesto ninguno. Sin `GJALLARHORN_LLM`, se usa Claude si hay clave y
nada si no la hay, que es como estaba antes.

`auto` es el quinto modo, y combina dos: prueba la nube primero, en el
orden Claude, Groq, Google (la primera que tenga clave puesta), y si esa
llamada falla —red caída, clave rechazada, límite agotado— cae a Ollama
local antes de rendirse. Va en ese orden y no al revés porque Ollama
acierta menos y tarda más: como red de seguridad no se nota, como motor
principal sí. Si no hay ninguna clave de nube puesta, `auto` prueba
directamente Ollama. Solo entra en juego una vez: si Ollama también falla,
`entender()` devuelve `None` como siempre — no hay un tercer intento.

## Tres frenos

- **Tiempo.** `TOPE_SEGUNDOS` corto y sin reintentos: una pausa de cuatro
  segundos al teléfono ya es larga, y dos seguidas son una llamada colgada.
- **Gasto.** `TOPE_CONSULTAS` por llamada. Quien no se entiende con el
  agente no puede costar veinte consultas: a partir de ahí, reglas solas y
  recado, que es lo que iba a pasar de todas formas.
- **Confianza.** Si el modelo dice que está poco seguro, se descarta. Un
  recado es más barato que apuntar una cita que nadie pidió.

## Si falla, no pasa nada

Sin red, con la clave mal, con el modelo tardando: se devuelve None y las
reglas siguen como si el LLM no existiera. Una llamada nunca se cae por esto,
y cada fallo deja un aviso para que se vea al día siguiente.
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from hugin.mente import conocimiento
from hugin.mente import rag

MODELO_POR_DEFECTO = "claude-opus-5"
# Un modelo pequeño y multilingüe: lo que cabe en la máquina de un negocio y
# entiende castellano. El mismo por defecto que usa hugin/personal/entender.py
# contra el mismo hardware (Madre: GTX 1060, 6 GB, Pascal — sin
# FlashAttention). Cambiado el 2026-09-18 de qwen2.5:7b (nunca llegó a
# descargarse en Madre, y a 4.7 GB en Q4_K_M deja poco margen de VRAM sin
# FlashAttention) a esta variante: Qwen3, no Qwen2.5, y la revisión
# "-instruct-2507" porque NUNCA activa el modo de razonamiento por defecto de
# Qwen3/3.5 —bugs abiertos en Ollama rompen la salida estructurada (`format`)
# con ese modo activo—. En Q4_K_M pesa ~2.5 GB, con margen real en 6 GB. Se
# cambia con GJALLARHORN_LLM_MODELO.
MODELO_LOCAL_POR_DEFECTO = "qwen3:4b-instruct-2507"
OLLAMA_POR_DEFECTO = "http://127.0.0.1:11434"
TOPE_SEGUNDOS = 4.0
TOPE_CONSULTAS = 6          # por llamada
TURNOS_DE_CONTEXTO = 4      # los últimos, no la llamada entera
INTENCIONES = ("precio", "cita", "anular", "cambiar", "horario", "despedida", "otro")
FRANJAS = ("manana", "tarde", "noche")
CONFIANZAS = ("alta", "media", "baja")

_cliente = None


@dataclass(frozen=True)
class Entendido:
    """Lo que el modelo ha entendido. Datos, nunca una frase que decir."""

    intencion: str
    servicio: str | None = None
    cuando: str | None = None
    nombre: str | None = None
    franja: str | None = None
    confianza: str = "alta"
    ms: float = 0.0

    @property
    def fiable(self) -> bool:
        """Con poca confianza no se usa: se toma el recado y ya está."""
        return self.confianza != "baja"


def proveedor() -> str:
    """Qué motor se usa: «anthropic», «ollama», «groq», «google» o «» si no hay ninguno.

    Sin `GJALLARHORN_LLM`, lo de siempre: Claude si hay clave y nada si no.
    Así, quien ya lo tenía funcionando no tiene que tocar nada. Groq y
    Google (Gemini) son gratuitos con límite de peticiones, cada uno con su
    propia clave (`GROQ_API_KEY`, `GOOGLE_API_KEY`) — elegir uno sin su
    clave puesta no enciende nada, como ya pasaba con Claude.
    """
    from hugin.guardado import ajustes
    ajustes.leer()
    elegido = os.environ.get("GJALLARHORN_LLM", "").strip().lower()
    if elegido in ("no", "off", "ninguno", "0"):
        return ""
    if elegido == "auto":
        return "auto"
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
    """¿Hay algún modelo con el que contar? Sin él, esto no existe."""
    return bool(proveedor())


MODELO_GROQ_POR_DEFECTO = "llama-3.3-70b-versatile"
MODELO_GOOGLE_POR_DEFECTO = "gemini-2.5-flash"


def modelo() -> str:
    propio = os.environ.get("GJALLARHORN_LLM_MODELO", "").strip()
    if propio:
        return propio
    return {
        "ollama": MODELO_LOCAL_POR_DEFECTO,
        "groq": MODELO_GROQ_POR_DEFECTO,
        "google": MODELO_GOOGLE_POR_DEFECTO,
    }.get(proveedor(), MODELO_POR_DEFECTO)


def ollama() -> str:
    return os.environ.get("GJALLARHORN_OLLAMA", "").strip() or OLLAMA_POR_DEFECTO


def _esquema(servicios: list[str]) -> dict:
    """La forma fija de la respuesta. `servicio` solo puede ser uno de la tabla."""
    return {
        "type": "object",
        "properties": {
            "intencion": {"type": "string", "enum": list(INTENCIONES)},
            "servicio": {"type": ["string", "null"], "enum": [*servicios, None]},
            "cuando": {"type": ["string", "null"]},
            "nombre": {"type": ["string", "null"]},
            "franja": {"type": ["string", "null"], "enum": [*FRANJAS, None]},
            "confianza": {"type": "string", "enum": list(CONFIANZAS)},
        },
        "required": ["intencion", "servicio", "cuando", "nombre", "franja", "confianza"],
        "additionalProperties": False,
    }


# Cómo se le cuenta al modelo qué se le acaba de preguntar al cliente. Sin
# esto, «Marta» es un nombre suelto y «el jueves» no es nada.
SE_LE_PREGUNTO = {
    "fecha": "qué día quiere la cita",
    "hora": "a qué hora quiere la cita",
    "franja": "si la hora que dijo es de la mañana o de la tarde",
    "nombre": "a nombre de quién se apunta la cita",
    "cual": "cuál de los servicios que se le han ofrecido le interesa",
    "anular_nombre": "a nombre de quién está la cita que quiere anular",
    "anular_cual": "cuál de sus citas quiere anular",
    "algo_mas": "si necesita algo más",
}


def _instrucciones(servicios: list[str], sabido: str = "", esperando: str | None = None) -> str:
    """Lo que el modelo tiene que saber para clasificar bien esta frase."""
    lista = "\n".join(f"- {s}" for s in servicios) or "- (no hay servicios cargados)"
    texto = (
        "Eres el clasificador de un recepcionista telefónico de un negocio en "
        "España. Te llega lo que acaba de decir quien llama, transcrito por voz "
        "(puede traer errores de transcripción). Devuelve SOLO el JSON pedido.\n\n"
        "intencion:\n"
        "- precio: pregunta cuánto cuesta o cuánto tarda algo\n"
        "- cita: quiere reservar, pedir hora, saber si hay hueco\n"
        "- anular: quiere quitar una cita que ya tiene\n"
        "- cambiar: quiere mover una cita que ya tiene a otro día u hora\n"
        "- horario: pregunta cuándo abrís o cerráis\n"
        "- despedida: se despide o da las gracias para colgar\n"
        "- otro: cualquier otra cosa\n\n"
        "servicio: el servicio de esta lista al que se refiere, escrito EXACTAMENTE "
        "como aparece, o null si no se refiere a ninguno o no está en la lista. "
        "Nunca inventes uno ni elijas el más parecido si no es claramente ese:\n"
        f"{lista}\n\n"
        "cuando: el trozo literal de la frase que dice el día y/o la hora "
        "(«el jueves a las cinco», «mañana por la tarde»), o null.\n"
        "franja: manana, tarde o noche si se entiende de lo que dice, o null.\n"
        "nombre: el nombre de la persona si lo dice, o null.\n"
        "confianza: alta si está claro, media si es probable, baja si estás "
        "adivinando. Con baja no se hace nada, así que no adivines: es mejor "
        "un recado que una cita que nadie pidió."
    )
    if esperando:
        texto += (f"\n\nLo último que le ha preguntado el recepcionista es: "
                  f"{esperando}. Lo que dice ahora suele ser la respuesta a eso.")
    if sabido:
        texto += ("\n\nEsto es lo que el negocio tiene escrito y puede venir a "
                  "cuento. Sirve para entender de qué habla, NO para copiarlo "
                  f"en la respuesta:\n{sabido}")
    return texto


def _preguntar_claude(frase: str, servicios: list[str], turnos=None,
                      sabido: str = "", esperando: str | None = None) -> dict:
    """La llamada a la API. Separada para poder sustituirla en las pruebas."""
    global _cliente
    import anthropic

    if _cliente is None:
        _cliente = anthropic.Anthropic(timeout=TOPE_SEGUNDOS, max_retries=0)

    respuesta = _cliente.beta.messages.create(
        model=modelo(),
        max_tokens=256,
        system=_instrucciones(servicios, sabido, esperando),
        messages=_mensajes(frase, turnos),
        output_config={"effort": "low",
                       "format": {"type": "json_schema", "schema": _esquema(servicios)}},
        # Si el modelo declina por politica, que conteste otro en la misma
        # llamada en vez de dejar al cliente sin respuesta.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if respuesta.stop_reason == "refusal":
        raise RuntimeError("el modelo declinó la petición")
    texto = next(b.text for b in respuesta.content if b.type == "text")
    return json.loads(texto)


def _mensajes(frase: str, turnos) -> list[dict]:
    """La conversación como la entiende un modelo: turnos de verdad."""
    mensajes = []
    for dicho, contestado in (turnos or [])[-TURNOS_DE_CONTEXTO:]:
        mensajes.append({"role": "user", "content": dicho})
        mensajes.append({"role": "assistant", "content": contestado})
    mensajes.append({"role": "user", "content": frase})
    return mensajes


def _preguntar_ollama(frase: str, servicios: list[str], turnos=None,
                      sabido: str = "", esperando: str | None = None) -> dict:
    """Lo mismo, pero contra un modelo de esta máquina. Nada sale de casa.

    Por HTTP a Ollama y con `urllib`, sin cliente ni dependencia: son veinte
    líneas y el paquete de Ollama arrastra más de lo que resuelve. El esquema
    va igual que con Claude —Ollama admite JSON Schema en `format`— así que
    la garantía es la misma: seis campos, y el servicio solo de la tabla.
    """
    import urllib.error
    import urllib.request

    cuerpo = json.dumps({
        "model": modelo(),
        "messages": [{"role": "system", "content": _instrucciones(servicios, sabido, esperando)},
                     *_mensajes(frase, turnos)],
        "format": _esquema(servicios),
        "stream": False,
        # Sin creatividad: esto clasifica, no escribe.
        # Fijo y no al default de Ollama (variable segun VRAM libre): una
        # llamada real acumula turnos de conversacion, asi que va con el
        # mismo margen que hugin/personal/conversar.py, no el ajustado de
        # una clasificacion de una sola frase.
        "options": {"temperature": 0, "num_ctx": 8192},
    }).encode("utf-8")
    peticion = urllib.request.Request(
        f"{ollama()}/api/chat", data=cuerpo,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=TOPE_SEGUNDOS) as respuesta:
        contestado = json.loads(respuesta.read().decode("utf-8"))
    return json.loads(contestado["message"]["content"])


def _preguntar_groq(frase: str, servicios: list[str], turnos=None,
                    sabido: str = "", esperando: str | None = None) -> dict:
    """Lo mismo, contra Groq. API compatible con la de OpenAI, sin cliente.

    `json_object`, no `json_schema` con `strict`: ese modo estricto solo
    está en "modelos seleccionados" según la propia documentación de Groq,
    y no hay garantía de que el de `modelo()` sea uno. La palabra "JSON"
    tiene que aparecer en algún mensaje para que la API acepte el modo —ya
    está, en las instrucciones ("Devuelve SOLO el JSON pedido").
    """
    import urllib.request

    clave = os.environ.get("GROQ_API_KEY", "").strip()
    cuerpo = json.dumps({
        "model": modelo(),
        "messages": [{"role": "system", "content": _instrucciones(servicios, sabido, esperando)},
                     *_mensajes(frase, turnos)],
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


def _preguntar_google(frase: str, servicios: list[str], turnos=None,
                      sabido: str = "", esperando: str | None = None) -> dict:
    """Lo mismo, contra la API de Google AI Studio (Gemini).

    Sin historial nativo de turnos en `contents` (a diferencia de Claude/
    Groq, que aceptan roles user/assistant alternados): se simplifica
    metiendo los turnos anteriores como parte del texto del sistema, porque
    `_mensajes()` está pensado para el formato OpenAI/Anthropic y rehacerlo
    para el de Gemini sería duplicar la lógica de turnos en dos formatos
    para ganar poco — aquí solo hacen falta unos pocos turnos de contexto
    (`TURNOS_DE_CONTEXTO`), no una conversación larga.
    """
    import urllib.request

    clave = os.environ.get("GOOGLE_API_KEY", "").strip()
    instrucciones = _instrucciones(servicios, sabido, esperando)
    historial = "\n".join(
        f"Cliente: {dicho}\nRecepcionista: {contestado}"
        for dicho, contestado in (turnos or [])[-TURNOS_DE_CONTEXTO:])
    if historial:
        instrucciones += f"\n\nLo que se ha dicho antes en esta llamada:\n{historial}"
    cuerpo = json.dumps({
        "system_instruction": {"parts": [{"text": instrucciones}]},
        "contents": [{"role": "user", "parts": [{"text": frase}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _esquema(servicios),
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


def _llamar(preguntar, frase, servicios, turnos, sabido, esperando) -> dict:
    """Llama a `preguntar` como sepa: con contexto, o solo con la frase.

    Un `preguntar` escrito antes de que existiera el contexto solo acepta
    (frase, servicios). Se le llama como sabe en vez de obligar a cambiarlo:
    esto es la costura por la que se prueba todo lo demás.
    """
    import inspect

    try:
        acepta = set(inspect.signature(preguntar).parameters)
    except (TypeError, ValueError):
        acepta = set()
    if {"turnos", "sabido", "esperando"} <= acepta:
        return preguntar(frase, servicios, turnos=turnos, sabido=sabido, esperando=esperando)
    return preguntar(frase, servicios)


def _motores_nube() -> list[str]:
    """Los motores en la nube con clave puesta, en el orden en que se prueban."""
    candidatos = (("anthropic", "ANTHROPIC_API_KEY"),
                  ("groq", "GROQ_API_KEY"),
                  ("google", "GOOGLE_API_KEY"))
    return [motor for motor, var in candidatos if os.environ.get(var, "").strip()]


def _llamar_con(motor: str | None, preguntar, frase, servicios, turnos, sabido, esperando) -> dict:
    """Como `_llamar`, fijando `GJALLARHORN_LLM` al motor real mientras dura.

    `modelo()` lee `proveedor()` —y por tanto `GJALLARHORN_LLM`— para saber
    qué modelo por defecto usar. En modo `auto` esa variable vale "auto", que
    no está en el mapa de `modelo()`: sin este ajuste, cada intento pediría
    el modelo de Claude aunque estuviera llamando a Ollama. Se restaura
    siempre, para no dejar el proceso con la variable cambiada.
    """
    if motor is None:
        return _llamar(preguntar, frase, servicios, turnos, sabido, esperando)
    antes = os.environ.get("GJALLARHORN_LLM")
    os.environ["GJALLARHORN_LLM"] = motor
    try:
        return _llamar(preguntar, frase, servicios, turnos, sabido, esperando)
    finally:
        if antes is None:
            os.environ.pop("GJALLARHORN_LLM", None)
        else:
            os.environ["GJALLARHORN_LLM"] = antes


def entender(frase: str, base: Path | None = None, preguntar=None,
             turnos=None, esperando: str | None = None) -> Entendido | None:
    """Qué quiere quien llama, según el modelo. None si no hay modelo o falla.

    `preguntar` es la función que habla con la API; se cambia en las pruebas
    por una que devuelve lo que se le diga. `turnos` es lo que se lleva dicho
    en esta llamada y `esperando` lo que se le acaba de preguntar: sin eso,
    «el jueves» y «Marta» no significan nada.
    """
    servicios = [s["servicio"] for s in conocimiento.tarifas(base)]
    sabido = rag.contexto(frase, base, tope=2, limite=600)
    arranque = time.perf_counter()

    if preguntar is not None:
        motores = [(None, preguntar)]
    else:
        cual = proveedor()
        if not cual:
            return None
        # Se busca en el módulo, no en un mapa fijado al importar: así una
        # prueba que sustituye `cerebro._preguntar_groq` (mock.patch.object)
        # se respeta también aquí, igual que cuando se llama directo.
        nombres = {"anthropic": "_preguntar_claude", "ollama": "_preguntar_ollama",
                  "groq": "_preguntar_groq", "google": "_preguntar_google"}
        if cual == "auto":
            # Nube primero (la primera con clave puesta), Ollama de respaldo
            # si la nube falla. Sin ninguna clave de nube, directo a Ollama.
            motores = [(m, globals()[nombres[m]]) for m in (*_motores_nube(), "ollama")]
        else:
            motores = [(cual, globals().get(nombres.get(cual, ""), _preguntar_claude))]

    error_final = None
    for motor, fn in motores:
        try:
            crudo = _llamar_con(motor, fn, frase, servicios, turnos,
                                sabido, SE_LE_PREGUNTO.get(esperando or ""))
            break
        except Exception as error:  # noqa: BLE001 — red, clave, modelo: nada tumba una llamada
            error_final = error
    else:
        return _no_contesto(error_final)
    ms = (time.perf_counter() - arranque) * 1000

    intencion = crudo.get("intencion")
    if intencion not in INTENCIONES:
        return None
    servicio = crudo.get("servicio")
    if servicio not in servicios:
        # Un servicio que no esta en la tabla no existe, diga lo que diga el
        # modelo. Es la regla que impide cantar un precio de algo inventado.
        servicio = None
    franja = crudo.get("franja")
    confianza = crudo.get("confianza")
    return Entendido(intencion=intencion, servicio=servicio,
                     cuando=(crudo.get("cuando") or None),
                     nombre=(crudo.get("nombre") or None),
                     franja=franja if franja in FRANJAS else None,
                     # "baja", no "alta": una confianza ausente o con una
                     # forma que no se reconoce es al reves de "el modelo
                     # esta seguro" — es "no se ha podido leer lo que dijo
                     # el modelo", y eso tiene que caer al lado seguro
                     # (Entendido.fiable == False), no al que actua solo.
                     confianza=confianza if confianza in CONFIANZAS else "baja",
                     ms=ms)


def _no_contesto(error: Exception) -> None:
    """Un fallo del modelo no tumba la llamada, pero no se traga en silencio."""
    aviso = f"El LLM no contestó ({type(error).__name__}: {error}); siguen las reglas solas"
    print(f"⚠️  {aviso}", file=sys.stderr)
    try:
        from hugin.guardado import avisos
        avisos.registrar("fallo", aviso)
    except Exception:  # noqa: BLE001 — si ni eso se puede, al menos queda el stderr
        pass
    return None


def main() -> int:
    """`python3 cerebro.py "frase"`: qué entiende el modelo, y cuánto tarda."""
    import argparse

    from hugin.negocio import negocio as negocios

    parser = argparse.ArgumentParser(description="Qué entiende el LLM de una frase")
    parser.add_argument("frase", nargs="?", default="oye, ¿hacéis lo del alisado ese?")
    parser.add_argument("--negocio", default="peluqueria")
    args = parser.parse_args()

    if not configurado():
        print("El LLM está apagado: las reglas van solas. Para encenderlo, en .env:")
        print("  GJALLARHORN_LLM=anthropic  + ANTHROPIC_API_KEY=…   (Claude, en la nube, de pago)")
        print("  GJALLARHORN_LLM=groq       + GROQ_API_KEY=…        (Groq, en la nube, gratis con límite)")
        print("  GJALLARHORN_LLM=google     + GOOGLE_API_KEY=…      (Gemini, en la nube, gratis con límite)")
        print("  GJALLARHORN_LLM=ollama                             (un modelo local)")
        print()
        print("Con Claude/Groq/Google el TEXTO de lo que dice el cliente sale de casa")
        print("hacia la API (el audio no). Con Ollama no sale nada de la máquina, y a")
        print("cambio acierta menos y tarda más. Es decisión del negocio.")
        return 1
    n = negocios.cargar(args.negocio)
    donde = f"en local ({ollama()})" if proveedor() == "ollama" else "en la nube"
    print(f"modelo {modelo()} {donde} · «{args.frase}»")
    entendido = entender(args.frase, n.conocimiento)
    if entendido is None:
        print("❌ sin respuesta (mira el aviso de arriba)")
        return 1
    print(f"   intención {entendido.intencion} · servicio {entendido.servicio} · "
          f"cuándo {entendido.cuando!r} · franja {entendido.franja} · "
          f"nombre {entendido.nombre} · confianza {entendido.confianza} · "
          f"{entendido.ms:.0f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
