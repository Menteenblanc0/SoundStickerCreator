# Privacidad

El editor ejecuta FFmpeg y FFprobe localmente con argumentos estructurados y limita los protocolos de entrada a archivos. Asocia extensiones a demuxers de medios y evita las listas de reproducción externas. Las listas concat internas para WebP contienen nombres de fotogramas generados. El aplicativo no implementa telemetría ni servicios propios.

El editor guarda preferencias y rutas de exportaciones recientes en `SoundStickerCreator/settings.json` bajo `LOCALAPPDATA` en Windows o `~/.config` en Linux. Configuración permite borrarlos. Los archivos exportados permanecen en la carpeta seleccionada por el usuario. Las fuentes de medios conservan su ubicación original. Los temporales se eliminan al terminar normalmente la operación. Un cierre abrupto puede dejar temporales bajo el directorio temporal del sistema.

El envío y diagnóstico requieren un gesto explícito y una cuenta de pruebas. El QR solo aparece para vinculación. Los datos de autenticación se mantienen en memoria, se solicita logout al finalizar y se descartan al salir. Una interrupción abrupta puede dejar el dispositivo marcado como vinculado en el servidor. La vinculación se puede revocar desde el teléfono.

La aplicación desactiva la sincronización completa, rechaza las notificaciones de historial de la biblioteca y no mantiene una base de conversaciones. Baileys puede procesar eventos de protocolo mientras está conectado. Los resúmenes excluyen claves, URLs, IDs de mensaje, números de teléfono y cuerpo de otros mensajes. La CLI opcional `--measure` descarga solo los recursos del sticker analizado a memoria, desde la CDN de WhatsApp.

El uso de un cliente extraoficial puede provocar restricciones de cuenta ante cambios de términos, compatibilidad o mecanismos de integridad. [Términos de WhatsApp](https://www.whatsapp.com/legal/terms-of-service)
