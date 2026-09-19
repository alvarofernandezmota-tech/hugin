"""El bot vivo: lo que decide qué contestar, sin saber por dónde le hablan.

`Hugin.procesar()` recibe un `Mensaje` y devuelve una `Respuesta`. Eso es
todo el contrato, y es el mismo para una consola, un chat y una llamada: el
canal traduce lo suyo a un `Mensaje`, y traduce la `Respuesta` de vuelta a
lo suyo.

Hasta la fase 1 del épico «Hugin vivo» (issue #23) esta decisión vivía
dentro de `telegram/handlers/texto.py`, así que el bot no existía sin
Telegram: para saber qué contesta a «recuérdame llamar al médico» había que
levantar un `Update`. Ahora la decisión está aquí y Telegram es un
adaptador de veinte líneas.

Lo que **no** vive aquí: `asyncio`. `procesar()` es síncrona a propósito.
Sacar las llamadas lentas del bucle de eventos es un problema del canal
—Telegram lo hace con `asyncio.to_thread`—, y meterlo aquí obligaría a
cada puerta futura a hablar asíncrono para preguntar qué se contesta.
"""
