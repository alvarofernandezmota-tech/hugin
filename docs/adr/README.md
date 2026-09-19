---
tipo: readme
fecha: 2026-09-19
repo: hugin
etiquetas: [indice, adr]
---

# Decisiones de arquitectura (ADR)

Esqueleto abierto el 2026-09-19: hugin pasa a ser la **fuente de verdad** de
su propia documentación, incluidos los ADR que hasta ahora vivían solo en
[midgaror](https://github.com/alvarofernandezmota-tech/midgaror). Ese repo no
está todavía en el scope de esta sesión — cuando se conecte, los ADR que
mandan aquí se portan a esta carpeta, con su número y su fecha original, y
`docs/README.md` deja de remitir a midgaror.

## Pendientes de portar desde midgaror

| ADR | De qué trata | Estado |
|---|---|---|
| ADR-019 | El cerebro sale de gjallarhorn a hugin como submódulo | Pendiente de portar |
| ADR-024 | «Un cerebro y dos puertas»: hugin como librería, telegram/ y telefono/ como aplicaciones finas | Pendiente de portar |

## Convención

Un ADR por fichero: `NNN-titulo-en-kebab-case.md`, con frontmatter
`tipo: adr`, `fecha`, `repo: hugin`, y estado (`propuesto`, `aceptado`,
`superado-por-NNN`). Números sin reutilizar, aunque un ADR quede superado.
