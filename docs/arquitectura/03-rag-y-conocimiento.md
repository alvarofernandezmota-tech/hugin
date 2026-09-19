# RAG y conocimiento

El RAG de Hugin recupera conocimiento editable de una instalación.

## Fuentes de conocimiento

- `tarifas.md`: servicios, precios, duración y condiciones.
- `faq.md`: preguntas frecuentes.
- `frases.toml`: expresiones, sinónimos y lenguaje del negocio.
- Otros ficheros de conocimiento que se incorporen con pruebas.

## Regla

El RAG lee conocimiento y devuelve contexto para responder.

El RAG no debe:

- Escribir citas.
- Crear tareas.
- Cambiar hábitos.
- Guardar diario.
- Depender de Telegram o teléfono.

## Situación actual

La recuperación es local y léxica. Antes de añadir embeddings o una base
vectorial se deben medir fallos reales de recuperación, cobertura de sinónimos,
ranking y trazabilidad de las respuestas.

## Auditoría pendiente

- Fragmentación de documentos.
- Ranking.
- Cobertura de sinónimos.
- Pruebas de preguntas equivalentes.
- Fuente exacta de cada respuesta.
