# Pruebas

## Automatizadas sin cuenta

```sh
python -m unittest discover -s tests -v
npm test --prefix transport
npm audit --prefix transport --omit=dev --omit=optional
```

Los fixtures de medios se generan con Pillow y las fuentes sintéticas `testsrc2` y `sine` de FFmpeg. Las pruebas Node usan una función de carga simulada. Se comprueban orden y tipo de carga, separación del audio, forma Protobuf y negativas de subida, conexión o ACK. El ensayo manual del editor abre la GUI, importa un video sintético, genera la vista previa con onda, scrubea, inicia y detiene la reproducción y comprueba limpieza de temporales.

## Validación real

Usa dos cuentas de laboratorio autorizadas. Registra versiones completas de los clientes, sistema operativo, tipo de operación y resultado. Guarda únicamente resúmenes redactados. Comprueba primero que el sticker original suena en los clientes de destino que lo admiten.

1. En la cuenta receptora inicia `python app.py receive --test-account --measure`. Escanea el QR desde **Dispositivos vinculados** y reenvía a esa cuenta el sticker sonoro original desde la segunda cuenta cuando aparezca **Conectado**.
2. Guarda el resumen y repite con un reenvío efectuado por un cliente diferente. El CLI termina tras el primer sticker entrante que reconoce.
3. En la cuenta emisora usa `python app.py send --video video.mp4 --to NUMERO_DE_PRUEBAS --test-account`. Vincula la cuenta emisora, espera el estado y comprueba el resultado en el teléfono receptor. Una segunda prueba puede usar `--self`.
4. Toca el sticker, comprueba imagen y sonido, guarda en favoritos e intenta volver a enviarlo desde favoritos. Reenvía también el mensaje original sin pasar por favoritos. Comprueba el sonido en cada mensaje nuevo.
5. Al finalizar, revisa **Dispositivos vinculados** y revoca cualquier vinculación de laboratorio que haya quedado activa.

| Comprobación | Android | iOS | Web | Escritorio |
| --- | --- | --- | --- | --- |
| Recibir el original y oír el sonido | Pendiente | Pendiente | Pendiente | Pendiente |
| Aceptación de la trama generada por el servidor | Pendiente | Pendiente | Pendiente | Pendiente |
| Recibir la trama como sticker y reproducir su audio | Pendiente | Pendiente | Pendiente | Pendiente |
| Sincronización perceptible de imagen y audio | Pendiente | Pendiente | Pendiente | Pendiente |
| Guardar, reenviar y conservar sonido | Pendiente | Pendiente | Pendiente | Pendiente |

En un caso fallido, registra si fallaron QR, apertura de conexión, carga visual, carga de audio, serialización, ACK, presentación visual o reproducción. La aceptación de la trama y la reproducción del audio son resultados independientes.
