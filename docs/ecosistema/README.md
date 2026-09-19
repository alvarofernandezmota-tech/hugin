---
tipo: readme
fecha: 2026-09-19
repo: hugin
etiquetas: [indice, ecosistema]
---

# El ecosistema alrededor de hugin

Qué otros repos existen, para qué sirve cada uno y cómo se relacionan con
este. Esqueleto abierto el 2026-09-19, a la espera de portar el detalle real
desde midgaror (todavía fuera del scope de esta sesión).

| Repo | Qué es | Relación con hugin |
|---|---|---|
| [gjallarhorn](https://github.com/alvarofernandezmota-tech/gjallarhorn) | El producto original, de donde salió el cerebro (ADR-019) | hugin nació de aquí, commit `cf000df` |
| [bifrost](https://github.com/alvarofernandezmota-tech/bifrost) | La puerta de Telegram | Su historia entera vive ahora en `telegram/` de este repo |
| midgaror | Repo de infraestructura, ADR y documentación de sesiones de trabajo | Fuente de los ADR que faltan por portar (ver `docs/adr/`) |

## Auditorías portadas

`hugin/personal/fechas.py` menciona una auditoría del parser de thea-ia
(`docs/ecosistema/auditoria-thea-ia.md`), hecha el 2026-09-04. El fichero en
sí no se ha portado todavía — solo la idea, ya incorporada al código. Pendiente
de traer el documento original cuando se conecte midgaror.
