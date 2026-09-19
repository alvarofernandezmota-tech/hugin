# llm/ (pendiente de migración)

Aquí vivirá la capa de modelos: router de motor/modelo según tarea,
contratos de proveedor, prompts del sistema y tool/function calling.

Hoy esta lógica está en src/hugin/motores.py y repartida en telefono/.
Se migra en la fase 4 del epic "Hugin vivo" (#23), consolidando sin
duplicar lo que ya funciona.

Ver docs/arquitectura/07-hugin-bot-vivo.md.
