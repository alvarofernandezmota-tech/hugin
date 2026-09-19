"""Aplicar lo que entendió `entender()`: a tareas, a citas, a hábitos, a
apuntes, o contestar una pregunta.

Extraído de `telegram/handlers/texto.py::_enrutar` en la fase 1 del issue
#23, rama por rama y sin tocar una decisión. Estaba dentro de Telegram por
como creció, no porque necesitara nada de allí: de sus setenta y ocho
líneas, `update` solo aparecía en los cinco `responder(update, …)` del
final. Nunca se leía. Lo que había que mover era el texto que se contesta,
no el canal.

`entender.py` es la otra mitad: dice **qué** se ha entendido y no escribe
nada. Este dice **dónde** va y llama a la función de siempre —la misma que
usan `/tarea`, `/cita`, `/habito` y `/apunte`—, con los mismos datos que le
pasaría su comando. Ninguna rama de aquí puede acabar escribiendo texto
libre que venga del modelo: cada intención va a su `agregar`/`marcar`/
`apuntar`, y quien valida la fecha, el nombre o el valor sigue siendo ese
módulo.

## `ValueError` es parte de la firma

No es un error: es la forma de decir «esto no se ha podido aplicar, trátalo
como lo que era». Una «cita» sin una fecha que `fechas.py` sepa leer, un
«hábito» sin nombre, una pregunta que no se ha podido contestar. Quien
llama lo captura y manda la frase al diario, que es exactamente lo que
pasaba antes de que existiera el clasificador. Así el peor caso de esto es
dejar de reconocer algo, nunca perderlo.

## Por qué `subir` se inyecta

`sincronizar()` hace `git commit` y `git push`: hasta noventa segundos con
mala red, y en Telegram va fuera del bucle de eventos. Aquí no se decide
nada de eso —se recibe una función `subir(ruta, mensaje) -> str` y se pega
lo que devuelva al final de la confirmación—. Telegram le pasa la de
verdad; la consola arranca sin ella, porque una sesión interactiva que
hace `git push` por línea escrita no tiene sentido.
"""

from hugin import apuntes as registro
from hugin.personal import citas, conversar, fechas, habitos, tareas


def coletilla(subido: str) -> str:
    """El « · subido» del final, o nada si no se sincronizó.

    Lo único que NO viene tal cual de `handlers/texto.py`. Allí
    `sincronizar()` corría siempre, así que el « · » iba pegado al literal
    de cada confirmación. Desde que la consola puede arrancar sin
    sincronizar, `subido` puede venir vacío, y un « · » suelto al final
    sería basura en la pantalla. Con Telegram, que sí sincroniza, nunca
    está vacío y el texto sale igual que antes, carácter a carácter.
    """
    return f" · {subido}" if subido else ""


def cuanto(apunte: dict) -> str:
    """« 3h», « 1,5 l», o cadena vacía si el apunte no lleva valor.

    Portada de `telegram/handlers/apunte.py`, que la sigue usando para
    confirmar `/apunte` — importándola de aquí, no con una segunda copia.

    Para confirmar el apunte que se acaba de crear, no una línea de
    resumen: `registro.apuntar()` devuelve `valor`/`unidad`, nunca `total`.
    Usar el `_cantidad()` de los resúmenes aquí revienta con
    `KeyError: 'total'` en cuanto el apunte lleva valor, que es el caso más
    normal («agua 1,5 l»): el dato se guardaba bien y la confirmación moría
    con «❌ Error: 'total'».
    """
    if "valor" not in apunte:
        return ""
    unidad = f" {apunte['unidad']}" if apunte.get("unidad") else ""
    return f" {apunte['valor']}{unidad}"


def enrutar(e, inq, subir, responder_pregunta=None) -> str:
    """Aplica lo que entendió `entender()` y devuelve la confirmación.

    `e` es un `entender.Entendido`. `inq` el inquilino de la sesión, ya
    resuelto. `subir(ruta, mensaje) -> str` la coletilla de sincronización
    —cadena vacía si no se sincroniza—. `responder_pregunta` el punto de
    inyección de `conversar.responder`, para no llamar a la API en pruebas.

    Puede lanzar `ValueError`: ver el docstring del módulo.
    """
    if e.intencion == "pregunta":
        # La única rama que no escribe nada: lee los resúmenes y contesta.
        # `conversar` no importa ni una función que escriba —lo vigila
        # `tests/test_conversar_personal.py` sobre el propio fichero—, así
        # que esta rama no puede tocar un JSON aunque el modelo se empeñe.
        respuesta = conversar.responder(e.texto or "", responder_pregunta, None, inq)
        if respuesta is None:
            # Sin clave, red caída o respuesta vacía. Al diario, como todo.
            raise ValueError("no se pudo contestar la pregunta")
        return respuesta
    if e.intencion == "tarea":
        if not e.texto:
            raise ValueError("tarea sin texto")
        t = tareas.agregar(e.texto, inq)
        subido = subir(inq.ruta / tareas.FICHERO, f"tareas: {inq.nombre}")
        cuando = ""
        if t.get("fecha"):
            cuando = f" · {t['fecha']}" + (f" {t['hora']}" if t.get("hora") else "")
        return f"✅ [{t['id']}] {t['texto']}{cuando}{coletilla(subido)}"
    if e.intencion == "cita":
        if not e.texto:
            raise ValueError("cita sin texto")
        cita, solapan = citas.agregar(e.texto, inq)
        subido = subir(inq.ruta / citas.FICHERO, f"citas: {inq.nombre}")
        cuando = (f"{cita['fecha']} {cita['hora']}" if cita.get("hora")
                  else f"{cita['fecha']} (todo el día)")
        texto_conf = f"📅 [{cita['id']}] {cita['texto']} · {cuando}{coletilla(subido)}"
        aviso = citas.aviso_choques(solapan)
        return f"{texto_conf}\n{aviso}" if aviso else texto_conf
    if e.intencion == "habito":
        if not e.nombre:
            raise ValueError("hábito sin nombre")
        # habitos.marcar() SÍ resuelve lenguaje natural internamente
        # (normalizar_fecha llama a fechas.normalizar hacia atrás) — a
        # diferencia de apuntes.apuntar(), que a propósito no lo hace. No
        # hay aquí el bug que sí había en la rama "apunte".
        fecha, nombre, marca = habitos.marcar(
            e.nombre, hecho=e.hecho, fecha=e.cuando, inq=inq, valor=e.valor)
        subido = subir(inq.ruta / habitos.FICHERO, f"habitos: {inq.nombre}")
        return f"{habitos.formato(marca)} {nombre} — {fecha}{coletilla(subido)}"
    if e.intencion == "apunte":
        if not e.nombre:
            raise ValueError("apunte sin nombre")
        # `e.cuando` viene en español tal cual lo dijo quien escribe
        # (entender.py: "'ayer', 'el lunes'... tal cual"), y `apuntar()`
        # espera AAAA-MM-DD. Sin resolverlo aquí, normalizar_fecha('ayer')
        # lanza ValueError y el apunte se pierde silenciosamente como prosa
        # del diario, que es justo lo que el comando /apunte ya evita.
        # Hacia ATRÁS: un apunte habla de algo que ya pasó.
        fecha = fechas.normalizar(e.cuando, hacia_atras=True) if e.cuando else None
        apunte = registro.apuntar(e.nombre, valor=e.valor, unidad=e.unidad,
                                  fecha=fecha, inq=inq)
        subido = subir(inq.ruta / registro.FICHERO, f"apuntes: {inq.nombre}")
        return f"📝 {apunte['que']}{cuanto(apunte)} — {apunte['fecha']}{coletilla(subido)}"
    # entender() nunca debería devolver otra cosa (solo alta confianza y sin
    # ser "diario"), pero si algún día cambia el esquema, esto cae al diario
    # en vez de intentar adivinar qué hacer con una intención que no conoce.
    raise ValueError(f"intención sin manejar: {e.intencion!r}")
