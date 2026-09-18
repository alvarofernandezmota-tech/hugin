"""Cuanto cabe en un mensaje de Telegram, y como recortar lo que no cabe.

Telegram rechaza los mensajes de mas de 4096 con un BadRequest. Cuando eso
pasa el handler lo caza como excepcion generica y contesta "❌ Error:
Message is too long" — y ese comando queda inservible hasta que se limpie
la lista. Medido el 2026-09-05: /hoy revienta con 29 tareas pendientes,
/tareas con 81, /agenda semana con 126 citas y /habitos semana con 68
habitos.

Esto es interfaz de Telegram, no dominio: por eso vive en bifrost y no en
midgaror/diario/, que no sabe ni que Telegram existe.
"""

LIMITE = 4096
# Se deja margen para el pie que se anade al recortar y para cualquier
# prefijo que se ponga delante mas adelante.
TOPE = 4000
MARCA = "\n… (recortado)"


def longitud(texto: str) -> int:
    """Lo que mide un texto PARA TELEGRAM: unidades UTF-16, no caracteres.

    No es lo mismo y la diferencia decide: '📅' mide 1 para len() y 2 para
    Telegram; '🗑️' mide 2 y 3. Con las lineas del bot hay una banda real
    —alrededor de 120 citas— donde len() dice que cabe y Telegram lo
    rechaza. Y contar bytes UTF-8 recorta de mas en cuanto hay acentos.
    """
    return len(texto.encode("utf-16-le")) // 2


def recortar_duro(texto: str, tope: int = TOPE) -> str:
    """Corta a lo bruto, respetando caracteres enteros, y lo dice.

    Se recorre carácter a carácter en vez de cortar por indice: asi nunca
    se parte un emoji por la mitad (un par suplente son dos unidades
    UTF-16 pero un solo caracter de Python).
    """
    if longitud(texto) <= tope:
        return texto
    disponible = tope - longitud(MARCA)
    acumulado, trozos = 0, []
    for caracter in texto:
        ancho = longitud(caracter)
        if acumulado + ancho > disponible:
            break
        trozos.append(caracter)
        acumulado += ancho
    return "".join(trozos).rstrip() + MARCA


def recortar(texto: str, tope: int = TOPE) -> str:
    """Recorta por lineas enteras y dice cuantas se ha dejado fuera.

    Una lista cortada por la mitad de una linea no se entiende, y peor:
    una tarea a medias pierde su id, que es el asa para actuar sobre ella.
    Se conservan las primeras, que en tareas y citas son las mas urgentes
    (el dominio ya las ordena por fecha).
    """
    if longitud(texto) <= tope:
        return texto

    lineas = texto.split("\n")
    if len(lineas) == 1:
        return recortar_duro(texto, tope)

    cabidas, acumulado = [], 0
    for i, linea in enumerate(lineas):
        pie = f"\n… y {len(lineas) - i} líneas más"
        ancho = longitud(linea) + (1 if cabidas else 0)
        if acumulado + ancho + longitud(pie) > tope:
            break
        cabidas.append(linea)
        acumulado += ancho

    if not cabidas:
        return recortar_duro(texto, tope)
    return "\n".join(cabidas) + f"\n… y {len(lineas) - len(cabidas)} líneas más"
