# Conectores

Un conector adapta un protocolo externo a Hugin.

## Responsabilidades permitidas

- Recibir un evento del canal.
- Validar e identificar al actor.
- Construir un contexto de canal.
- Llamar al núcleo Hugin.
- Transformar la respuesta de Hugin al formato del canal.
- Registrar errores de transporte y operación.

## Responsabilidades prohibidas

- Decidir reglas de citas.
- Implementar RAG.
- Consultar Postgres directamente.
- Escribir ficheros de dominio.
- Duplicar reglas de negocio existentes en Hugin.

## Conector Telegram

`telegram/` contiene hoy handlers, autenticación, utilidades y arranque del
servicio. Se auditará para extraer reglas de dominio que hayan quedado dentro
de handlers.

## Conector teléfono

`telefono/` contiene adaptación de voz/teléfono y conocimiento de ejemplos de
negocio. Se auditará para garantizar que usa el núcleo y no una lógica paralela.

## Conectores futuros

- Web.
- API.
- WhatsApp.
- Panel administrativo.
