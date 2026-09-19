---
tipo: readme
fecha: 2026-09-19
repo: hugin
etiquetas: [indice, adr]
---

# Decisiones de arquitectura (ADR)

Desde el 2026-09-19, hugin es la **fuente de verdad** de su propia
documentación. ADR-019 y ADR-024 se portaron de
[midgaror](https://github.com/alvarofernandezmota-tech/midgaror), que sigue
siendo su origen —son copias verbatim, con su número y su fecha original—;
`midgaror` ya está en el scope de esta sesión.

## Los ADR de hugin

| ADR | De qué trata | Estado |
|---|---|---|
| [019](019-cerebro-de-gjallarhorn-en-hugin.md) | El cerebro sale de gjallarhorn a hugin como submódulo (portado de midgaror) | Aceptado, cerrado — hugin ya no es submódulo, es el repo del producto (ver ADR-024) |
| [024](024-un-cerebro-dos-puertas.md) | «Un cerebro y dos puertas»: hugin como el producto entero, telegram/ y telefono/ como puertas finas (portado de midgaror) | En marcha — fases 1-2 cerradas, `personal/` ya portado; ver nota dentro del fichero |
| [025](025-fusion-mente-personal.md) | Un solo cerebro, gobernado por las capacidades del inquilino — la decisión del punto 4 del ADR-024 | Aceptado, fase 1 de 4 cerrada |
| [026](026-postgres-estructurado.md) | Datos estructurados en Postgres; diario y conocimiento editable permanecen en ficheros | Aceptado, fase inicial cerrada: tareas, citas, hábitos y apuntes tienen adaptador Postgres |
| [027](027-hugin-nucleo-conectores.md) | Hugin como núcleo; Telegram y teléfono como conectores | Propuesto — auditoría de arquitectura iniciada |

## Convención

Un ADR por fichero: `NNN-titulo-en-kebab-case.md`, con frontmatter
`tipo: adr`/`tipo: decision`, `fecha`, `repo`, y estado (`propuesto`,
`aceptado`, `superado-por-NNN`). Números sin reutilizar, aunque un ADR quede
superado. Los portados de midgaror conservan su número y su `repo`
original en el frontmatter; solo los propios de hugin llevan `repo: hugin`.
