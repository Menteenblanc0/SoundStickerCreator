# Publicar en GitHub

Extrae el ZIP de código y abre una terminal en la carpeta que contiene el README. Crea un repositorio vacío en GitHub, sin generar otro README ni otra licencia. Conserva la estructura del proyecto, incluido `.github/workflows/build.yml`.

```sh
git init -b main
git add .
git diff --cached --stat
git commit -m "Publicar Sound Sticker Creator 0.1.0"
git remote add origin https://github.com/TU_USUARIO/TU_REPOSITORIO.git
git push -u origin main
```

Antes del commit, revisa los archivos incluidos. Mantén fuera las sesiones, QR, credenciales, números reales, medios privados, `node_modules` y binarios. El ZIP contiene el código y la documentación. Conserva el ZIP de código como copia y extrae su contenido para subirlo.

## Releases

Después de que pasen las pruebas en **Actions**, crea el release `v0.1.0` y adjunta el instalador, el ZIP portable y el archivo de sumas. GitHub genera automáticamente las descargas de código de la etiqueta. Para publicar desde Actions, ejecuta manualmente el workflow **Pruebas y compilación** con `publish` habilitado. Elige uno de los dos métodos para crear esa etiqueta.

Si publicas los binarios ya entregados, incluye los tres archivos a los que hace referencia su `SHA256SUMS.txt`, incluido el ZIP de código original, o regenera el archivo de sumas para los adjuntos exactos del release. El workflow genera sumas para sus dos binarios.

Describe el envío de WhatsApp como integración experimental y deja visible la licencia MIT junto con los avisos de terceros. Conserva FFmpeg como dependencia separada si usas los paquetes de esta entrega.
