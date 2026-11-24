# Protocolo de sticker sonoro

La hipótesis implementada serializa un solo mensaje de conversación con dos referencias multimedia.

```protobuf
// Esquema parcial del mensaje, conservando los números de campo.
message Message {
  optional StickerMessage stickerMessage = 26;
  optional FutureProofMessage audioStickerMessage = 134;
  message StickerMessage {
    oneof audio {
      AudioMessage audioMessage = 26;
    }
  }
}
```

El adaptador emite `Message.stickerMessage.audioMessage`. Reconoce el envoltorio 134 para diagnóstico. El uso de este envoltorio en un mensaje real y su contenido siguen abiertos. Los números de campo están confirmados en esquemas independientes del binario de la aplicación. [Investigación](RESEARCH.md)

1. `prepareWAMessageMedia` recibe un recurso visual y otro de tipo audio en operaciones independientes.
2. La implementación fijada de Baileys usa una clave aleatoria por recurso, deriva claves con HKDF según el tipo de medio, cifra con AES-256-CBC y agrega un MAC truncado. Para esta versión, la tabla de medios asigna stickers al perfil `Image` y al endpoint lógico `/mms/image`, y audios a `Audio` y `/mms/audio`. Los hosts de carga proceden de la conexión de WhatsApp. [Código de Baileys](https://github.com/WhiskeySockets/Baileys/tree/v7.0.0-rc14/src)
3. El builder adjunta la segunda referencia dentro de la primera. Ambas conservan sus propias longitudes, claves de medios, rutas y hashes.
4. Antes del envío se construye, codifica y decodifica la estructura. El builder exige dos referencias y confirma que el mensaje no tenga una pista de audio en el nivel superior.
5. `relayMessage` usa el cifrado E2E y la conexión de dispositivos de Baileys. El CLI correlaciona el ACK de servidor con el ID generado en memoria. Ese ACK mide aceptación de la trama. La reproducción se verifica en el destinatario.

`transport/protocol.mjs` extiende las funciones de codificación y decodificación del paquete fijado en el proceso del adaptador. Esta extensión conserva los campos normales de Baileys. Emplea el objeto devuelto por la decodificación directamente en `relayMessage`; los conversores genéricos upstream `fromObject` y `toObject` no conocen los campos añadidos. La prueba en bytes fija el árbol y los números de campo para detectar cambios al actualizar dependencias.

## Recepción

El resumen muestra nombres de campos reconocidos, envoltorios, dimensiones, tamaño, indicador animado, audio, tipo declarado, duración, forma de onda y marca de reenvío si está presente. `--measure` prueba la descarga de los medios desde una CDN fija de WhatsApp, sin seguir redirecciones, con límite de tamaño y comprobación del hash de contenido. Las rutas, claves, identificadores y contenido quedan fuera del resultado. Cuando la CDN, el formato o la comprobación de contenido fallan, el diagnóstico distingue el resumen Protobuf de la medición.

## Experimentos pendientes

Capturar el resumen de un sticker sonoro real y de un reenvío permite comparar su envoltorio, audio declarado, duración y referencias. Si un receptor muestra el sticker sin sonido, comprueba primero ese mismo cliente con el sticker original. Si el original reproduce y el generado no, compara los resúmenes y los medios antes de cambiar el builder. El material actual no demuestra un rechazo del servidor ni identifica un feature flag necesario.
