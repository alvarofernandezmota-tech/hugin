---
tipo: adr
fecha: 2026-09-19
repo: hugin
etiquetas: [arquitectura, mente, personal, inquilino]
estado: aceptado, en marcha (fase 1 de 4 cerrada)
---

# ADR-001: un solo cerebro, gobernado por las capacidades del inquilino

## Contexto

Hoy `hugin` tiene **dos** implementaciones paralelas de lo mismo, separadas
por a quién atienden en vez de por lo que hacen:

- `mente/cerebro.py` + `mente/recepcion.py` + `negocio/agenda.py`: el
  recepcionista telefónico de un negocio, atendiendo a terceros.
- `personal/entender.py` + `personal/conversar.py` + `personal/citas.py`
  (+ `tareas.py`, `habitos.py`, `apuntes.py`): el diario personal de un
  individuo.

`inquilino.py` ya resolvió la mitad del problema (ADR-024): un inquilino es
una carpeta con **capacidades** sueltas (`agenda`, `tarifas`, `tareas`...),
no un `tipo` cerrado «persona» o «negocio». Pero el código que atiende a ese
inquilino no usa esa abstracción todavía — sigue eligiendo entre dos
cerebros distintos por fuera, en vez de que un solo cerebro consulte
`inq.puede(capacidad)` por dentro.

## Decisión

Fusionar los dos en un cerebro único, gobernado por capacidades. El
individuo y el negocio dejan de ser dos caminos de código: son dos
inquilinos con capacidades distintas, atendidos por el mismo motor.

## Plan, en fases (cada una se prueba y se comitea sola)

1. **Selector de motor LLM único** — `hugin/motores.py` (CERRADA,
   2026-09-19). `mente/cerebro.py` y `personal/entender.py` delegan en el
   mismo `SelectorDeMotor` para `proveedor()`/`configurado()`/`modelo()`/
   `ollama()`/`motores_nube()`, cada uno con su variable de entorno
   (`GJALLARHORN_LLM`/`MIDGAROR_LLM`) y si lee o no `ajustes.py`. El modo
   `auto` (nube con fallback a Ollama) ya vive aquí para los dos, aunque
   `personal/entender.py` todavía no implementa el bucle de reintento —
   queda para la fase 2.
2. **Un clasificador único** — fusionar `cerebro.entender()` +
   `personal.entender.entender()` en un solo `entender()` cuyas
   instrucciones e intenciones válidas dependan de `inq.capacidades`: con
   `tarifas`/`agenda` de negocio entiende de precios y citas de terceros;
   con `tareas`/`habitos`/`apuntes` entiende de diario. Un inquilino con
   varias capacidades a la vez (el caso del autónomo del docstring de
   `inquilino.py`) entiende de las dos cosas sin bifurcar código.
3. **Un modelo de cita único** — `mente.recepcion.Cita` (con `acotada`,
   `franja`, el flujo de negocio) y el `dict` de `personal/citas.py` (con
   `sin_franja`, `duracion`, choques) comparten ya casi el mismo problema
   —hora sin franja, no citar en el pasado—; converger en un solo modelo,
   con lo que no aplica a cada perfil quedando opcional (un negocio no
   tiene `duracion` variable, una cita personal no tiene `servicio` de
   tabla).
4. **Un `Conversacion` único, persistible** — `recepcion.Conversacion` hoy
   vive en memoria de una llamada de teléfono (correcto para ese canal: una
   llamada es un proceso). Para un canal de chat (Telegram, WhatsApp...)
   donde los turnos llegan separados en el tiempo, el estado
   (`esperando`, `cita` a medias) tiene que sobrevivir entre mensajes.
   Se persiste con `guardado/almacen.py`, igual que ya hace `citas.py` con
   las citas mismas — por inquilino, nunca en memoria del proceso.

## Qué no cambia

La regla que da sentido al repo sigue mandando: **ningún canal se importa
aquí**. La fusión pasa entera dentro de `hugin/`; `telegram/` y `telefono/`
siguen siendo puertas finas que no saben que la otra existe.

## Pendiente de otro repo

Este ADR documenta la decisión tomada en esta sesión de trabajo. Las
sesiones de trabajo en sí (el detalle día a día) siguen en midgaror, no
aquí — ver `docs/sesiones/`.
