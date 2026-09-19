# puertos/ (pendiente de migración)

Aquí vivirán los contratos que separan el núcleo de sus implementaciones
y de los conectores externos: canal de entrada/salida, voz, telefonía,
repositorio de datos, notificador y reloj.

Se crean solo cuando exista un primer consumidor real (fases 6-7 del
epic "Hugin vivo" #23, al convertir Telegram y teléfono en adaptadores).
No se define ningún contrato especulativo antes de tener el caso de uso.

Ver docs/arquitectura/07-hugin-bot-vivo.md.
