"""Lo que el usuario escribió, tal y como lo escribió.

Hasta el 2026-09-08 los handlers sacaban el texto de `" ".join(context.args)`.
`context.args` lo parte python-telegram-bot por espacios *y por saltos de
línea*, así que volver a unirlo con espacios convertía

    /diario me he levantado tarde
    luego he ido al gimnasio

en una línea corrida, sin manera de recuperar el original: en el diario ya
solo queda el párrafo aplastado. Y no era raro, porque escribir varias líneas
en Telegram es shift+enter, no un truco.

Aquí el texto se saca del mensaje entero y solo se le quita el comando, así
que los saltos de línea llegan al diario como los mandó Álvaro.

`context.args` se queda para los comandos que de verdad parten en palabras
(`/tarea`, `/cita`, `/habito`, `/hoy`): ahí no hay nada que conservar.
"""


def texto_tras_comando(update) -> str:
    """El texto del mensaje sin el comando de delante, con sus saltos de línea.

    Sirve igual para lo que llega por el menú: una respuesta a un botón no
    lleva comando delante, así que el texto es entero suyo y se devuelve tal
    cual. Es el mismo criterio que usa `menu.py` para repartir (lo que empieza
    por «/» no es una respuesta al menú).
    """
    texto = (update.effective_message.text or "").strip()
    if not texto.startswith("/"):
        return texto
    # maxsplit=1 corta por el primer hueco, sea espacio o salto de línea, y
    # deja el resto intacto. Quita también el @nombre_del_bot de los grupos,
    # que va pegado al comando.
    partes = texto.split(maxsplit=1)
    return partes[1].strip() if len(partes) > 1 else ""
