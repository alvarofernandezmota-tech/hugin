# Mente, cerebro y motores

## Mente

`hugin/mente/` es la capa que decide cómo comprender y contestar.

Componentes iniciales:

- `cerebro.py`: coordinación conversacional y decisiones.
- `conocimiento.py`: acceso a conocimiento editable.
- `rag.py`: recuperación local de fragmentos relevantes.

## Motores

`hugin/motores.py` selecciona un proveedor opcional de LLM.

Un motor puede ser Claude, Ollama, Groq, Google u otro proveedor compatible.
La falta de motor, clave o red no debe impedir que funcionen reglas
deterministas como citas, tareas, hábitos, fechas y persistencia.

## Auditoría pendiente

- API pública de `cerebro.py`.
- Dependencias de `cerebro.py`.
- Límites entre clasificación, conversación y ejecución.
- Qué rutas requieren LLM y cuáles tienen alternativa determinista.
- Confirmación de que mente no importa conectores.
