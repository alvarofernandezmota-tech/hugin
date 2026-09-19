# conectores/ (pendiente de migración)

Regla de esta carpeta: cada conector solo traduce un protocolo o API
externa a los contratos públicos de Hugin (Mensaje, Sesion, Respuesta,
Accion). Ningún conector contiene reglas de negocio, conversación, RAG,
LLM, acceso directo a datos ni autorización de inquilino.

Hoy Telegram y teléfono siguen viviendo en telegram/ y telefono/ en la
raíz del repositorio, con su funcionalidad completa. Se trasladan aquí
como adaptadores delgados en las fases 6 y 7 del epic "Hugin vivo" (#23),
solo después de que el núcleo absorba sus capacidades.

Ver docs/arquitectura/07-hugin-bot-vivo.md.
