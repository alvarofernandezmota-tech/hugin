# Dominio y persistencia

## Dominio estructurado

- Citas.
- Tareas.
- Hábitos.
- Apuntes.
- Agenda comercial.

## Conocimiento editable

- Tarifas.
- FAQ.
- Frases y sinónimos.

## Memoria narrativa

- Diario.

## Almacenes

| Información | Almacén principal |
|---|---|
| Citas | Postgres si hay `base`; fichero en modo local |
| Tareas | Postgres si hay `base`; fichero en modo local |
| Hábitos | Postgres si hay `base`; fichero en modo local |
| Apuntes | Postgres si hay `base`; fichero en modo local |
| Diario | Markdown |
| Tarifas | Markdown |
| FAQ | Markdown |
| Frases | TOML |

## Regla

El dominio accede a sus adaptadores de persistencia. Telegram y teléfono no
deben ejecutar SQL ni leer o escribir JSON de dominio directamente.

La relación entre datos no se fuerza creando una única tabla gigantesca. El
núcleo carga las entidades y el conocimiento de la misma instalación según la
intención de cada mensaje.
