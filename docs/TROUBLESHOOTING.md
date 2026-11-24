# Resolución de problemas

| Síntoma | Comprobación |
| --- | --- |
| Falta FFmpeg o FFprobe | Configura ambos ejecutables, o colócalos en `tools`. Comprueba que FFmpeg incluye libwebp y libopus. |
| La imagen se reproduce pero la vista previa es silenciosa | Comprueba que la exportación incluye `audio.ogg`, que FFplay está instalado y que la salida de audio del sistema está activa. |
| No se alcanza el tamaño objetivo | El codificador prueba calidades decrecientes. Reduce resolución, FPS o duración si sigue excediendo el presupuesto. |
| La vista previa queda desactualizada | Pulsa **Generar** tras cambiar archivos o ajustes. |
| El QR expira o el teléfono no conecta | Abre **Dispositivos vinculados** con la cuenta de pruebas y repite la vinculación. Revisa la versión de Baileys si falla sistemáticamente. |
| El servidor no confirma | Verifica conectividad y destinatario de prueba. Un timeout es inconcluso. Confirma en el receptor antes de repetir el envío. |
| WhatsApp acepta y el receptor no oye sonido | Compara con el sticker original en ese mismo cliente. Ejecuta el diagnóstico y registra tipo de mensaje, audio y duración. |
| El diagnóstico informa medición no disponible | Comprueba que el recurso sigue disponible en la CDN y que tiene referencia, tamaño y hash en el mensaje. Usa el resumen declarado si la medición falla. |
| Quedó un dispositivo vinculado | Revócalo en **Dispositivos vinculados** desde el teléfono. |
