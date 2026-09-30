# Agente de escaneo para Windows

Este agente permite que el botón **Escanear ficha** del sistema reciba directamente un PDF generado por el Epson ES-60W. Escucha únicamente en `127.0.0.1`; el documento temporal se elimina después de enviarlo al navegador.

## Instalación en cada computadora

1. Instala el paquete oficial del Epson ES-60W (controlador y Epson Scan 2) y comprueba que escanee por Wi-Fi.
2. Instala [NAPS2](https://www.naps2.com/download) y crea un perfil llamado `Instituto ES-60W` usando el controlador WIA o TWAIN del Epson. Configúralo a 300 DPI, color o escala de grises y tamaño A4.
3. Instala Python 3 para Windows si la computadora aún no lo tiene.
4. Descarga y descomprime el paquete desde el enlace **Descargar agente Windows** del sistema.
5. Ejecuta `instalar-agente.bat` e indica la dirección del sistema cuando sea solicitada.
6. Abre `http://127.0.0.1:17654/health` en esa computadora. Debe mostrar `"status": "ready"`.

El instalador registra una tarea de Windows para iniciar el agente automáticamente con el usuario actual. Funciona en segundo plano, sin mantener una ventana abierta. Si el proceso falla, Windows intentará reiniciarlo.

## Uso

En la edición de una ficha, pulsa **Escanear ficha**, indica el número de páginas y alimenta el ES-60W. Cuando el campo muestre el nombre del PDF, pulsa **Guardar**.

Si son varias páginas, `page_delay_ms` define el tiempo para cambiar la hoja; el valor inicial es 10 segundos. Si se necesita más tiempo, por ejemplo 15 segundos, usa `15000`.

El selector normal de archivos continúa disponible como respaldo si el agente o el escáner no están activos.

Para retirarlo, ejecuta `desinstalar-agente.bat`. Esto elimina únicamente la tarea y los archivos instalados en `%LOCALAPPDATA%\Instituto\ScannerAgent`; no desinstala NAPS2, Python ni el controlador Epson.

## Diagnóstico

- `configuration_required`: NAPS2 no fue encontrado. Corrige `naps2_console` con la ruta de `NAPS2.Console.exe`.
- `Este sitio no está autorizado`: agrega el origen exacto del sistema a `allowed_origins` y reinicia el agente.
- `No se completó el escaneo`: abre NAPS2 y prueba el perfil `Instituto ES-60W`; verifica que el escáner esté encendido, cargado y conectado a la misma red.
- El registro de diagnóstico se guarda en `%LOCALAPPDATA%\Instituto\ScannerAgent\scanner-agent.log`.
