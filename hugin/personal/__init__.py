"""El parser de fechas de una PERSONA, no el de una reserva. A propósito, dos.

`hugin/mente/fechas.py` es el motor de la reserva: las fechas van siempre
hacia delante, porque nadie reserva cita para el martes pasado.

Aquí «el lunes» puede ser el lunes que pasó: un hábito o un apunte se
registran casi siempre DESPUÉS de haberlos hecho, así que «marqué el hábito
el lunes» tiene que poder mirar hacia atrás. Es la regla que ya tenía escrita
`diario/fechas.py` de midgaror, con `fecha_detras()` resolviendo hacia
delante y filtrando lo que ya pasó — la dirección es de quien pregunta, no
del motor (ver `hugin/apuntes.py`, la sección que explica por qué ese modelo
sí se pudo mudar antes que este).

Decidido en la fase 4 del ADR-024, tras refutar tres propuestas que fundían
los dos motores: las tres rompían algo al ejecutarlas (una fecha movida
siete días, un `ValueError` en el camino que escribe, o 287 de 882
combinaciones cambiando de respuesta). Se copia el parser de midgaror TAL
CUAL, sin tocar una sola regla, y se acepta la duplicación:

- Cuando aparezca un bug de vocabulario compartido (ya hay uno: «la semana
  que viene» está roto en los dos motores, de maneras distintas), se arregla
  DOS veces. Es un coste acotado y visible.
- La alternativa —una capa de léxico o un núcleo comunes— fue la que rompió
  al construirla: el coste de compartir se paga en silencio, en el diario de
  alguien.

`tests/test_libreria.py` sujeta el corte por el otro lado: nada de
`hugin/mente/`, `hugin/negocio/` ni `telefono/` puede importar `personal`.
"""
