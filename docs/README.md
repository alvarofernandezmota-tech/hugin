---
tipo: readme
fecha: 2026-09-19
repo: hugin
etiquetas: [indice, documentacion]
---

# Documentación de hugin

Sigue las convenciones de
[midgaror](https://github.com/alvarofernandezmota-tech/midgaror): los `.md` de
`docs/` llevan frontmatter `tipo/fecha/repo`; los de la raíz no.

**Cambio del 2026-09-19**: hasta ahora este fichero decía que los ADR de
hugin vivían solo en midgaror, para no tener dos versiones de la misma
decisión separándose con el tiempo. Se decidió lo contrario: **hugin pasa a
ser la fuente de verdad de su propia documentación** (ADR, ecosistema,
infraestructura). Las **sesiones de trabajo** son la excepción — esas siguen
en midgaror, que es el repo pensado para eso. ADR-019, ADR-024 y la
auditoría de thea-ia ya se portaron de midgaror, verbatim.

## Dónde está cada cosa

| Qué | Dónde | Por qué ahí |
|---|---|---|
| **Cómo se usa y cómo se monta** | [`README.md`](../README.md) (raíz) | Lo primero que lee quien llega |
| **Las reglas del dominio y las invariantes** | [`CLAUDE.md`](../CLAUDE.md) (raíz) | Lo que hay que saber **antes** de tocar nada |
| **Qué ha ido cambiando** | [`CHANGELOG.md`](CHANGELOG.md) | Sacado del historial |
| **Por qué se decidió cada cosa** | [`adr/`](adr/README.md) | Decisiones de arquitectura propias de hugin |
| **Qué otros repos hay y cómo se relacionan** | [`ecosistema/`](ecosistema/README.md) | gjallarhorn, bifrost, midgaror... |
| **Dónde corre esto de verdad** | [`infraestructura/`](infraestructura/README.md) | Madre, systemd, CI (o su ausencia) |
| **Sesiones de trabajo** | [`sesiones/`](sesiones/README.md) | Siguen en midgaror; aquí solo el hueco reservado |

## Lo que no hay, y por qué

**No hay `docs/procedimientos/` ni `scripts/`.** Una librería no se opera: no
se arranca, no se despliega, no se reinicia. No hay procedimiento que escribir.

## Al añadir un `.md` aquí

1. Frontmatter obligatorio: `tipo`, `fecha`, `repo: hugin`.
2. Entra en la tabla de arriba en el **mismo commit**.
