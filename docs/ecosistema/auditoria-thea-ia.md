---
tipo: ecosistema
fecha: 2026-09-04
repo: midgaror
---

# Auditoría de thea-ia: ¿se puede meter en bifrost?

Hecha el 2026-09-04 sobre el repo clonado (`88161ac`, último commit del
2026-02-02) ejecutando su código, no solo leyéndolo.

**Respuesta corta: no se absorbe thea-ia. Sí se porta una pieza concreta**
—el intérprete de fechas en español— reescrita y con pruebas.

## Qué hay

| | |
|---|---|
| Tamaño | 475 ficheros `.py`, 61.622 líneas |
| Última actividad | 2026-02-02; siete meses parado |
| Estado declarado | «H01 completado: tests pasan 100 %, coverage ≥80 %» (ROADMAP) |
| Stack | FastAPI, SQLAlchemy + PostgreSQL, Alembic, Redis, spaCy, scikit-learn, Groq, python-telegram-bot |

Por bloques:

| Bloque | Líneas | Qué es |
|---|---|---|
| `agents/agenda_agent/` | 6.367 | Agente de citas: FSM propia, parser de fechas, formateador |
| `core/multi_agent/` | 9.035 | Registro, broker de mensajes, descubrimiento, delegación, monitor de rendimiento |
| `agents/` (resto) | 3.193 | Notas, recordatorios, consultas, ayuda, respaldo |
| `ml/intent_detector/` | 1.576 | Clasificador de intención con scikit-learn y sus datos de entrenamiento |
| `adapters/telegram/` | 710 | Bot y adaptador |

## Qué pasa al ejecutarlo

- **`pyproject.toml` está roto**: la línea 11 es
  `version = "3.0.0"description = "…"`, sin salto. El paquete no se puede
  instalar ni construir; `pytest` se niega a arrancar hasta que se le pasa
  otra configuración.
- **La suite de tests no llega a recolectarse**: 14 errores de colección, 69
  tests recogidos de 150 ficheros. Cinco módulos piden `spacy`, tres `numpy`,
  dos `sqlalchemy`.
- **Los tests del agente de agenda no importan**:
  `ImportError: cannot import name 'AgendaAgent' from …agenda_agent.handler`.
  El agente que más código tiene no puede probarse tal cual está.

Es decir: lo de «tests pasan 100 %» era cierto en su día y hoy no se sostiene.
Nada de esto es raro en un proyecto parado siete meses; lo que importa es que
**no se puede dar por bueno sin arreglarlo antes**.

## Lo único que funciona y sirve: el parser de fechas

`agents/agenda_agent/datetime_parser.py` (español e inglés, con `dateutil` y
`pytz`). Ejecutado con fecha de referencia 2026-09-04 20:00:

| Frase | Resultado | |
|---|---|---|
| «quedada mañana a las 10» | 2026-09-05 10:00 | ✅ |
| «reunión el próximo lunes por la tarde» | 2026-09-07 09:00 | ⚠️ día bien, «por la tarde» ignorado |
| «gimnasio en 3 días» | 2026-09-07 | ✅ (pero mete «3 días» como *ubicación*) |
| «llamar a Ana hoy a las 3 de la tarde» | 2026-09-04 15:00 | ✅ (título extraído: «la tarde») |
| «cita el 15 de octubre a las 9:30» | 2026-**09**-15 09:30 | ❌ se come el mes |
| «médico pasado mañana» | 2026-09-05 | ❌ eso es *mañana*, no *pasado mañana* |
| «comprar el pan» | `None` | ✅ no inventa fecha |

Acierta lo relativo simple y falla en el mes explícito y en «pasado mañana».
Además devuelve UTC pese a anunciar `Europe/Madrid`, y la extracción de
título y ubicación confunde trozos de la propia expresión temporal.

## Por qué no se absorbe

1. **La arquitectura sobra.** 9.035 líneas de orquestación multiagente
   (registro, broker, descubrimiento, monitor) resuelven un problema que
   bifrost no tiene: aquí hay un usuario y cinco comandos.
2. **Los datos irían al revés.** thea-ia guarda en PostgreSQL multi-tenant;
   midgaror guarda en ficheros del repo del usuario, versionados en git
   ([bifrost-producto.md](bifrost-producto.md), ADR-009). Meterlo sería
   deshacer la decisión que hace que el diario se pueda leer sin el bot.
3. **La máquina.** Madre es CPU sin GPU: spaCy y scikit-learn cargados en un
   servicio que debe responder en segundos, además de Postgres y Redis, para
   lo que hoy hacen cinco funciones de Python.
4. **Ya se decidió una vez.** El [ADR-007](../adr/007-bifrost-desde-cero.md)
   dijo lo mismo de THDORA: bifrost se construye desde cero. Nada de lo visto
   hoy contradice esa decisión.
5. **Volumen.** Absorberlo son 61.622 líneas que nadie mantiene, con la suite
   de tests rota, contra los ~700 que tiene bifrost hoy.

## Qué sí se porta, y cuándo

**Un módulo `diario/fechas.py` en midgaror** con las reglas del parser
reescritas: relativas (`hoy`, `mañana`, `pasado mañana`, `en N días`,
`próximo lunes`), mes explícito (`15 de octubre`), horas (`9:30`, `las 3 de
la tarde`) y franjas (`por la mañana/tarde/noche`), en `Europe/Madrid`, con
sus pruebas —incluidos los seis casos de la tabla de arriba, los dos que
fallan incluidos—. Unas 150 líneas.

Sirve para lo que ya está planificado:

- `/tarea mañana a las 10 llamar al médico` — fecha de vencimiento en tareas.
- La agenda de citas, la capacidad que falta en
  [bifrost-producto.md](bifrost-producto.md).
- `/habito deporte ayer`, sin escribir la fecha en ISO.

Va **después** de que el bot se use unas semanas: primero hay que saber cómo
se escriben las cosas de verdad. La regla de siempre: el código en midgaror
con pruebas, y bifrost solo lo expone.

De `intent_detector/` interesa su corpus de entrenamiento (402 líneas de
frases reales de ejemplo, en el repo de thea-ia) como referencia de cómo se
dicen las cosas, no el clasificador: para texto libre,
la fase 6 (mimir, Ollama local) es mejor camino que un modelo de sklearn sin
mantener.

## Qué se hace con el repo

Se queda como está: público, parado y sin tocar. No se archiva todavía
—tiene el historial de una fase entera de trabajo— pero deja de ser candidato
a reutilización. Si algún día se retoma, lo primero es arreglar el
`pyproject.toml` y hacer que la suite recolecte.

## Relacionado con

- [bifrost-producto.md](bifrost-producto.md) — qué es bifrost y qué no
- [plan-bot.md](plan-bot.md) — las fases y la regla de arquitectura
- [../adr/007-bifrost-desde-cero.md](../adr/007-bifrost-desde-cero.md) — la misma decisión, con THDORA
- [repos-activos.md](repos-activos.md) — dónde vive thea-ia
