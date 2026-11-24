# Sound Sticker Creator

Editor local de escritorio y CLI para producir un WebP y una pista Ogg/Opus. Incluye un adaptador experimental para transmitir ambos recursos como un solo mensaje de sticker con audio anidado.

**Estado 0.1.0.** Se verificaron la conversión local, la inspección de la muestra, la construcción Protobuf y la preparación cifrada de dos recursos con una carga simulada. El usuario del proyecto también probó la aplicación en su entorno e informó que funcionó. La compatibilidad del envío, la reproducción y el reenvío puede variar según la cuenta, el dispositivo y la versión de WhatsApp.

## Windows 10/11 x64

Instala el ejecutable de instalación o extrae la versión portable y abre `Sound Sticker Creator.exe`. Ambos incluyen Python, Tcl/Tk y Node.js. Instala una compilación reciente de FFmpeg con `libwebp` y `libopus`. Coloca `ffmpeg.exe`, `ffprobe.exe` y, para escuchar la vista previa, `ffplay.exe` en `tools` o indica sus rutas en Configuración. [Compilaciones de FFmpeg](https://ffmpeg.org/download.html#build-windows)

1. Importa o arrastra una imagen, un GIF, un WebP o un video. Puedes importar una pista aparte. Un video con audio usa esa pista por defecto.
2. Ajusta el inicio, la duración, el recorte, el inicio del audio y su desfase. Pulsa **Generar** para construir la vista previa, ver la onda y conocer el tamaño efectivo.
   - La duración inicial es 6,867 s. Introduce un número con punto decimal y hasta 30 s de edición local. El clip también está limitado por el material de origen y el tamaño objetivo.
3. Pulsa **Exportar** para copiar `sticker.webp`, `audio.ogg` si existe y `metadata.json` a una carpeta nueva.
4. Para una prueba real usa **WhatsApp…**, confirma que usas una cuenta de pruebas y elige un destinatario de pruebas o **A mí**. Para probar con otro número, introdúcelo en formato internacional, por ejemplo `+573001234567` para un celular colombiano. El QR aparece en el diálogo. Haz la comprobación del receptor por separado.

## Desde el código fuente

Se requieren Python 3.12 con Tk, Node.js 24 y FFmpeg. Crea un entorno virtual con `python -m venv .venv` y actívalo según tu sistema.

```sh
python -m pip install -r requirements.txt
npm ci --prefix transport --ignore-scripts --omit=optional
python app.py gui
python app.py inspect sticker.webp
python app.py convert --video "mi video.mp4" --duration 3 --output proyecto
```

Para el envío y diagnóstico de pruebas:

```sh
npm run sticker:send -- --video "mi video.mp4" --self --test-account
npm run sticker:send -- --image sticker.webp --audio audio.mp3 --to NUMERO_INTERNACIONAL --test-account
npm run sticker:receive -- --test-account --measure
```

El parámetro `--measure` permite inspeccionar archivos entrantes en memoria a través de la CDN de WhatsApp. Omítelo para recibir únicamente el resumen Protobuf. Usa `python app.py convert --help` para ver todos los ajustes. En el portable puedes usar `runtime\python.exe app.py` desde PowerShell para ejecutar la CLI.

La integración Web es extraoficial y puede dejar de funcionar o causar restricciones de cuenta. Usa una cuenta de pruebas autorizada. Las claves viven en memoria durante cada operación. [Privacidad](docs/PRIVACY.md) · [Matriz de pruebas](docs/TESTING.md)

[Compilación y empaquetado](docs/BUILD.md) · [Investigación](docs/RESEARCH.md) · [Protocolo](docs/PROTOCOL.md) · [Contribuciones](CONTRIBUTING.md)


## Licencia y publicación

El código propio se distribuye bajo la [licencia MIT](LICENSE). Consulta los [avisos de terceros](THIRD_PARTY_NOTICES.md) para los componentes incluidos en el instalador y el portable. El proyecto es independiente de WhatsApp y Meta.

[Guía para publicar el repositorio y los binarios en GitHub](docs/GITHUB.md)
