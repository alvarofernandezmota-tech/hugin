# infraestructura/ (pendiente de migración)

Aquí vivirán las implementaciones técnicas concretas de los contratos
en puertos/: Postgres, archivos, voz, telefonía y tareas programadas.

Hoy esa lógica está en src/hugin/guardado/, telefono/canal/ y
telefono/dueno/. Se migra por partes, capa por capa, empezando siempre
por auditoría del código existente antes de mover nada.

Ver docs/arquitectura/07-hugin-bot-vivo.md.
