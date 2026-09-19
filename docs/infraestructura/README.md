---
tipo: readme
fecha: 2026-09-19
repo: hugin
etiquetas: [indice, infraestructura]
---

# Infraestructura

Dónde corre esto de verdad, y con qué. Esqueleto abierto el 2026-09-19.

## Hoy (lo que se sabe por esta sesión)

- **Madre**: la máquina donde vive el bot de Telegram en producción
  (`hugin-telegram.service`, systemd), con Ollama local para
  `GJALLARHORN_LLM=ollama`/`auto`.
- **CI**: no hay. Ver la sección "Verificar" de `CLAUDE.md` (raíz) — cuenta de
  GitHub Actions bloqueada por un cobro rechazado desde 2026-09-04.
  `make pruebas` en local es la única verificación real.

## Pendiente

Detalle de despliegue (unidades systemd, variables de entorno por servicio,
cómo se actualiza) vive hoy disperso en conversaciones y en el `.env` de
Madre. Portar aquí cuando se conecte midgaror.
