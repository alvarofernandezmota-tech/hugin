---
tipo: readme
fecha: 2026-09-19
repo: hugin
etiquetas: [indice, ecosistema]
---

# El ecosistema alrededor de hugin

Qué otros repos existen, para qué sirve cada uno y cómo se relacionan con
este.

| Repo | Qué es | Relación con hugin |
|---|---|---|
| [gjallarhorn](https://github.com/alvarofernandezmota-tech/gjallarhorn) | El producto original, de donde salió el cerebro (ADR-019) | hugin nació de aquí, commit `cf000df`. Según ADR-024, queda archivado con un README que apunta aquí |
| [bifrost](https://github.com/alvarofernandezmota-tech/bifrost) | La puerta de Telegram | Su historia entera vive ahora en `telegram/` de este repo. Según ADR-024, queda archivado igual que gjallarhorn |
| [midgaror](https://github.com/alvarofernandezmota-tech/midgaror) | Documentación, infraestructura, formación y lo que Álvaro escribe a mano — nunca código en producción (ADR-024) | Origen de ADR-019 y ADR-024 (portados a `docs/adr/`) y de la auditoría de thea-ia (portada abajo). Las sesiones de trabajo siguen viviendo ahí |

## Archivar gjallarhorn y bifrost

El propio ADR-024 lo deja dicho: una vez el producto vive entero en hugin,
`gjallarhorn` y `bifrost` "quedan archivados con un README que apunta aquí".
**Todavía no se ha hecho** — Madre en producción seguía, a fecha de esta
sesión, arrancando desde `midgaror-bot/proyectos/bifrost` según el propio
texto del ADR. Antes de archivar hay que confirmar que nada en producción
depende ya de esos repos.

## Auditorías portadas

[`auditoria-thea-ia.md`](auditoria-thea-ia.md) (2026-09-04, portada de
midgaror el 2026-09-19): por qué no se absorbió thea-ia entero y qué pieza sí
se portó (el intérprete de fechas en español, reescrito — hoy
`personal/fechas.py` y `mente/fechas.py`).
