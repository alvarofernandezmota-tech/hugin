---
tipo: decision
fecha: 2026-09-19
repo: hugin
etiquetas: [datos, postgres, diario]
estado: aceptado
relacionado: [docs/adr/024-un-cerebro-dos-puertas.md, docs/adr/025-fusion-mente-personal.md]
---

# ADR-026: Datos estructurados en Postgres; diario en ficheros

## Contexto
El PR #17 unió clasificar → leer → contestar (tarifas/FAQ por capacidad).
Telegram es un canal, no el almacén. Hoy citas/tareas/hábitos pueden ir
a JSON o a Postgres; el diario solo a markdown.

## Decisión
- Citas, tareas, hábitos (y apuntes si tienen tabla): Postgres por inquilino (`inq.base`).
- Diario en prosa: ficheros markdown. No se borra ni se convierte en apuntes.
- Apuntes no sustituyen citas.
- DBeaver (u otro cliente) contra Postgres, no contra el diario.
- El handler de Telegram no cambia de contrato: llama a `hugin.personal.*`; el backend lo elige el inquilino.

## Lo que no es este ADR
No activa APIs en Madre (sigue la checklist del ADR-025).
No implementa el esquema: eso va en el PR de código siguiente.
