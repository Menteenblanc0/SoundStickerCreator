# Compilación y distribución

## Desarrollo

Instala Python 3.12 con Tk, Node.js 24 y FFmpeg con los codificadores `libwebp` y `libopus`. Consulta el README para instalar dependencias y lanzar la GUI. La rama de transporte fija dependencias transitivas con `package-lock.json`. Ejecuta npm con `--ignore-scripts --omit=optional`.

## Windows desde Linux

El ensamblaje de Windows usa Go 1.27.4 para compilar el launcher PE x64 y NSIS 3.11 para el instalador. Python verifica SHA-256 de CPython y Node antes de extraerlos. Pip verifica las ruedas de Windows contra el archivo de hashes. El paquete contiene el código propio, Node, CPython con Tk, Pillow, TkDND y dependencias JS puras para este flujo.

```sh
python3 packaging/build_windows.py --go /ruta/bin/go --makensis /ruta/makensis
cd dist
sha256sum -c SHA256SUMS.txt
```

Los archivos son `SoundStickerCreator-0.1.0-win-x64-portable.zip` y `SoundStickerCreator-0.1.0-win-x64-setup.exe`. El ZIP contiene `SoundStickerCreator/Sound Sticker Creator.exe`. El instalador NSIS es un bootstrap de 32 bits que instala binarios x64 en el espacio del usuario actual. Los ejecutables van sin firma digital. FFmpeg se obtiene por separado y puede configurarse en la aplicación.

Para comparar hashes de compilaciones, iguala las versiones de Go, NSIS, npm y Python que usa el proceso. El build fija las fechas de las entradas ZIP. NSIS y su entorno pueden introducir diferencias de binario. GitHub Actions compila y prueba en CI. El despacho manual permite crear un release con los artefactos si se habilita expresamente la opción de publicación.
