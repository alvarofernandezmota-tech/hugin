---
tipo: arquitectura
fecha: 2026-09-19
repo: hugin
etiquetas: [arquitectura, nucleo, conectores, bot-vivo]
relacionado:
  - docs/adr/024-un-cerebro-dos-puertas.md
  - docs/adr/025-fusion-mente-personal.md
  - docs/adr/027-hugin-nucleo-conectores.md
  - docs/auditorias/2026-09-19-arquitectura-actual.md
---

# Hugin, bot vivo: visión de destino

**Esto es un mapa, no una orden de trabajo.** Describe a dónde va el código
con el tiempo, no qué carpetas hay que crear hoy. Ninguna de las carpetas
que aparecen abajo se crea antes de tener contenido real que meter dentro
— crear una carpeta vacía "porque va a hacer falta" es exactamente lo que
el propio `CLAUDE.md` de este repo prohíbe.

## La idea, en una frase

**Hugin es un bot completo y vivo — no un cerebro que unos bots externos
usan.** Telegram y teléfono no son "sitios donde vive parte del bot": son
dos cuerpos del mismo Hugin. Debe poder funcionar sin ninguno de los dos:

```bash
python -m hugin
```

Si `python -m hugin` no puede mantener una conversación completa (crear una
cita, contestar una pregunta de tarifas, apuntar una tarea), Hugin sigue
siendo un cerebro con dos bots pegados encima, no un bot.

## Qué significa "núcleo" y qué significa "conector"

La regla que va al ADR cuando esto se acepte formalmente:

> **Toda capacidad que aporte valor al usuario vive en Hugin. Todo código
> que solo traduce una API externa vive en un conector.**

"Crear una cita", "recordar mañana", "entender una fecha en español",
"consultar una tarifa", "decidir si hace falta el LLM" → **núcleo**.
"Recibir un `Update` de Telegram", "pintar un `InlineKeyboardButton`",
"comprobar la firma Ed25519 de un webhook", "hacer TTS con un proveedor
concreto" → **conector**.

Hoy, medido (ver auditoría de más abajo), esa regla **ya se cumple casi
del todo**: los handlers de Telegram y el `canal/` de teléfono ya llaman a
funciones de `src/hugin/`, no reimplementan lógica de dominio. Lo que falta
no es "sacar lógica de negocio de los conectores" — ya está fuera. Falta
que exista **un contrato neutral** por el que entrar sin pasar por ningún
conector, y una fachada única que lo sirva.

## El mapa gradual (destino, no plan de hoy)

```text
src/hugin/
├── bot/              # Mensaje, Sesion, Respuesta, Hugin.procesar(), CLI
├── mente/            # ya existe: cerebro, rag, conocimiento, recepcion...
├── llm/              # cuando motores.py necesite más de un fichero
├── dominio/
│   ├── personal/     # citas, tareas, hábitos... (hoy: personal/)
│   └── negocio/      # agenda, tarifas... (hoy: negocio/)
├── guardado/         # ya existe
├── inquilino/         # cuando inquilino.py necesite más de un fichero
├── puertos/          # contratos, SOLO cuando haya una segunda implementación real
└── infraestructura/  # implementaciones concretas de esos contratos

conectores/
├── telegram/         # hoy: telegram/, movido en un PR aparte
├── telefono/         # hoy: telefono/, movido en un PR aparte
└── cli/              # nuevo: consola para probar Hugin sin canal
```

**Cada carpeta de esta lista se crea el día que tenga un fichero real que
meter dentro**, no antes. `personal/` y `negocio/` no se renombran a
`dominio/personal/` y `dominio/negocio/` hasta que haya un motivo medido
para hacerlo (hoy no lo hay: los nombres actuales ya son claros y tienen
cientos de pruebas que los referencian). `puertos/` no se crea hasta que
exista de verdad una segunda implementación de algo (un segundo STT, un
segundo proveedor de telefonía) que justifique la abstracción — con una
sola implementación, un puerto es indirección sin beneficio.

## Cómo se sabe que un módulo ya está bien (no hace falta moverlo)

Un módulo de conector está bien donde está si:

1. No hay lógica de dominio dentro — solo traduce el formato del canal.
2. No accede a Postgres/JSON directamente — llama a `hugin.*`.
3. Sus pruebas no dependen de un ciclo de vida de Telegram/teléfono en
   ningún test del núcleo.

Eso ya se cumplió y se verificó (con búsqueda de imports, no con intuición)
en la auditoría del 2026-09-19: `hugin/` no importa `telegram/` ni
`telefono/`; `telegram/handlers/` no toca Postgres/JSON directo; `telefono/
canal/` usa una superficie pública de 9 funciones sin tocar internos.
Ver `docs/auditorias/2026-09-19-arquitectura-actual.md`.

## Lo que falta de verdad (y es poco)

No falta "sacar negocio de los conectores". Falta:

1. **Un contrato neutral de entrada/salida** (`Mensaje`, `Sesion`,
   `Respuesta`) que hoy no existe — cada conector construye su propia
   forma de llamar al núcleo (`comando_hoy(update, context)` en Telegram,
   una función de webhook en teléfono), en vez de pasar por una forma común.
2. **Una fachada única** (`Hugin.procesar()`, o el nombre que se decida)
   que hoy no existe — cada conector llama directamente a
   `hugin.personal.citas`, `hugin.personal.tareas`, etc., en vez de a un
   único punto de entrada.
3. **Una forma de usar Hugin sin ningún conector** — hoy no existe ni una
   CLI ni ninguna prueba de extremo a extremo que hable con el núcleo sin
   pasar por Telegram o teléfono.

Esas tres cosas son el contenido real de la primera extracción (ver
`docs/auditorias/2026-09-19-inventario-modulos.md` para el inventario
completo y la propuesta concreta).

## Qué no cambia con esto

- La regla de siempre: `tests/test_libreria.py` sigue vigilando que el
  núcleo no importe ningún canal.
- Nada de esto toca `systemd`, Postgres, ni el despliegue de Madre.
- `telegram/` y `telefono/` no se mueven a `conectores/` todavía — eso es
  un PR aparte, de layout puro, igual que fue mover `hugin/` a
  `src/hugin/`.
