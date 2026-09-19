"""El bot por consola: `python -m hugin`.

La puerta más pequeña que existe, y la que prueba que el bot ya no depende
de ningún canal. Si esto contesta, el cerebro está entero:

    $ INQUILINO=alvaro python -m hugin
    Hugin > recuérdame llamar al médico el 15 de octubre
    ✅ [1] llamar al médico · 2026-10-15
    Hugin > hola
    👋 ¡Hola! No he apuntado nada — dime una tarea, un hábito, una cita, o
    algo para el diario.
    Hugin > (Ctrl-D)

Es la misma `Hugin.procesar()` que atiende por Telegram, con los mismos
módulos escribiendo en la misma carpeta del inquilino. No hay aquí ni una
decisión de qué se contesta: solo `input()`, `print()` y el aviso de lo que
falta si falta.

## Sin sincronizar, salvo que se pida

`sincronizar()` hace `git commit` y `git push`. En Telegram va siempre,
porque cada mensaje es un cambio que interesa subir (ADR-013). Aquí NO por
defecto: una sesión interactiva escribe diez líneas en un minuto y diez
`git push` seguidos no son un respaldo, son ruido —y con mala red, un
minuto de espera por línea—. Con `--sincronizar` se comporta como Telegram.

Lo apuntado se guarda igual en los dos casos: lo que cambia es si además se
sube. Se dice en el arranque para que nadie lo dé por hecho.
"""

import os
import sys

from hugin import inquilino as inquilinos
from hugin.bot.hugin import Hugin
from hugin.bot.mensajes import Mensaje, Sesion
from hugin.guardado.sincronizar import sincronizar

VARIABLE = "INQUILINO"
PROMPT = "Hugin > "

AYUDA = f"""Uso: python -m hugin [--sincronizar]

  --sincronizar   además de guardar, hace git commit y git push de cada
                  cambio, como hace el bot de Telegram. Por defecto NO:
                  una sesión de consola haría un push por línea.

Hace falta decir de quién es este bot con la variable {VARIABLE}:

  export {VARIABLE}=alvaro
  python -m hugin"""


def _sesion(inq) -> Sesion:
    """Una sesión de consola. El actor y la conversación son quien teclea."""
    return Sesion(inquilino=inq, actor_id=inq.nombre,
                  conversacion_id="consola", canal="cli")


def main(argv: list[str] | None = None, entrada=input, salida=print) -> int:
    """El bucle. Devuelve el código de salida del proceso.

    `entrada` y `salida` se inyectan para poder probar la conversación
    entera sin un terminal: una prueba le pasa una lista de frases y lee lo
    que se ha contestado. No es un adorno — es lo que hace que la puerta de
    consola tenga pruebas como las tiene la de Telegram.
    """
    argumentos = list(sys.argv[1:] if argv is None else argv)
    if {"-h", "--help", "ayuda"} & set(argumentos):
        salida(AYUDA)
        return 0
    subir = "--sincronizar" in argumentos
    if subir:
        argumentos.remove("--sincronizar")
    if argumentos:
        salida(f"No entiendo «{' '.join(argumentos)}».\n\n{AYUDA}")
        return 2

    nombre = os.environ.get(VARIABLE, "").strip()
    if not nombre:
        # El mismo fallo claro que `telegram/utils/inquilino.py`: sin esto,
        # el primer módulo que mire una carpeta reventaría con algo que no
        # dice qué hacer.
        salida(f"No sé para quién es este bot: falta {VARIABLE}.\n\n{AYUDA}")
        return 2
    try:
        inq = inquilinos.cargar(nombre)
    except Exception as e:
        salida(f"No he podido cargar el inquilino «{nombre}»: {e}")
        return 2

    cerebro = Hugin(sincronizar=sincronizar if subir else None)
    sesion = _sesion(inq)
    salida(f"Hugin, atendiendo a {inq.nombre}. Ctrl-D para salir.")
    salida("Sin sincronizar: lo que apuntes se guarda, pero no se sube "
           "(--sincronizar para subirlo)." if not subir
           else "Sincronizando: cada cambio se sube con git.")
    while True:
        try:
            dicho = entrada(PROMPT)
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D y Ctrl-C son la forma normal de acabar, no un fallo: se
            # sale con un salto de línea para no dejar el prompt a medias.
            salida("")
            return 0
        dicho = (dicho or "").strip()
        if not dicho:
            continue
        respuesta = cerebro.procesar(Mensaje(texto=dicho, sesion=sesion))
        salida(respuesta.texto)


if __name__ == "__main__":
    raise SystemExit(main())
