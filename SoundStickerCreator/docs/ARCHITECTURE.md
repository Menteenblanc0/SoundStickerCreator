# Arquitectura

| Módulo | Responsabilidad |
| --- | --- |
| `desktop.py` | Tk, importación, controles, línea de tiempo y forma de onda, vista previa renderizada, exportación, configuración y operación WhatsApp en segundo plano. |
| `app.py` | GUI y CLI, rutas de herramientas, comandos explícitos para transmitir o diagnosticar. |
| `media.py` | FFmpeg y FFprobe con parámetros estructurados, reimportación WebP animado mediante Pillow, trim, crop, encuadre, compresión y sincronización. |
| `riff.py` | Inspección RIFF y construcción de metadatos de paquete. |
| `transport/` | Extensión de esquema, cifrado de medios vía Baileys, vinculación y sesión volátil, relay y diagnóstico filtrado. |
| `packaging/` | Launcher GUI Win64, ensamblaje portable y NSIS. |

Tk evita un Chromium residente y Python se usa principalmente como coordinador de FFmpeg. Tauri requiere una WebView y un sidecar de Node para Baileys. Electron simplifica compartir JavaScript entre escritorio y transporte a cambio de incluir un runtime gráfico mayor. El diseño elegido inicia Node únicamente en el envío o la recepción. Las tareas de render y red se ejecutan fuera del hilo gráfico. No se midieron recursos en el Intel Core i3-1215U.

La aplicación comunica el directorio exportado y el destinatario al adaptador mediante argumentos de proceso. La capa de medios funciona aun cuando el adaptador cambia o falta. Ajustes, rutas a binarios y la lista de exportaciones recientes se guardan localmente. Reabrir una exportación recupera su vista previa y medios. La lista no almacena fuentes ni un historial editable de capas.
