# Jarvis

Un asistente personal cuyo cerebro está diseñado para funcionar en diferentes
dispositivos. La versión actual incluye adaptadores de voz y acciones para macOS.

## Funciones de la versión 0.4

- Saludar y responder la hora.
- Abrir Calculadora, Calendario, Notas, Safari o Terminal.
- Rechazar órdenes desconocidas sin ejecutar comandos arbitrarios.
- Salir con `salir`, `adiós` o `Ctrl+C`.
- Escuchar una frase al pulsar Intro y responder con la voz de macOS.
- Reconocer voz en el dispositivo, sin enviar la grabación a una API externa.
- Recordar tu nombre entre sesiones mediante SQLite local.
- Mostrar u olvidar la información guardada cuando se lo pidas.
- Vivir en la barra superior de macOS sin mantener Terminal abierta.
- Escuchar desde el menú o con el atajo global `Control + Opción + Espacio`.
- Mostrar estados y respuestas mediante notificaciones de macOS.
- Mostrar un núcleo azul flotante a la izquierda mientras escucha, procesa y habla.
- Ejecutarse como aplicación accesoria sin mostrar Python en el Dock.
- Mantener el núcleo visible de forma tenue en reposo y emitir un sonido antes de escuchar.
- Separar visualmente cuatro segundos de escucha del procesamiento de Whisper.
- Detectar audio vacío y explicar cómo corregir el permiso del micrófono.

## Requisitos

- macOS.
- Python 3.11 o posterior.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Para instalar también el reconocimiento de voz local:

```bash
python -m pip install '.[voice]'
```

Para instalar la aplicación de barra superior y la voz:

```bash
python -m pip install '.[voice,mac-app]'
```

## Uso

```bash
jarvis
```

Para activar el modo de voz:

```bash
jarvis --voice
```

Para iniciar la aplicación de barra superior:

```bash
jarvis-app
```

Para instalar `Jarvis.app` y poder abrirlo desde Finder sin mantener Terminal:

```bash
jarvis-install-app
open ~/Applications/Jarvis.app
```

Pulsa su icono `◉` junto al reloj y elige **Escuchar**, o utiliza
`Control + Opción + Espacio`. macOS puede pedir permisos de Micrófono,
Accesibilidad y Notificaciones. El atajo global necesita Accesibilidad; el botón
del menú seguirá funcionando aunque ese permiso todavía no esté concedido.

La primera vez se descargará el modelo de Whisper y macOS solicitará permiso
para usar el micrófono. Después, la transcripción se realiza en el dispositivo.

También puedes ejecutarlo sin instalarlo:

```bash
PYTHONPATH=src python3 -m jarvis.cli
```

Prueba órdenes como `hola Jarvis`, `me llamo Marcos`, `qué sabes de mí`,
`olvida mi nombre`, `qué hora es` o `abre Calculadora`.

Jarvis ignora mayúsculas, acentos y signos de puntuación al interpretar las
órdenes de voz, y reconoce variantes habituales de la transcripción de su nombre.

Si una dependencia de voz falla, Jarvis muestra el componente exacto y guarda
el diagnóstico técnico en `~/.jarvis/jarvis.log`.
En Macs con Apple Silicon, el instalador fuerza la ejecución nativa `arm64` para
evitar que Finder inicie Python mediante Rosetta.

## Pruebas

Tras instalar pytest con `python -m pip install pytest`:

```bash
pytest
```

## Privacidad

La versión 0.3 no usa una API de voz ni recopila conversaciones. El modelo se
descarga una vez y la transcripción se ejecuta localmente. La grabación temporal
se elimina después de transcribirla. Los futuros secretos
se guardarán en `.env`, que está excluido de Git. La memoria vive en
`~/.jarvis/memory.db`, fuera del repositorio. Nunca publiques claves de API,
grabaciones o información personal.

## Próximos hitos

- **v0.5:** notas, recordatorios y temporizadores.
- **v1.0:** asistente configurable y estable.

## Otros dispositivos

El intérprete de órdenes no depende de macOS. Para Windows, Linux, Android o
Raspberry Pi añadiremos implementaciones específicas de `Listener`, `Speaker`
y apertura de aplicaciones, manteniendo el mismo núcleo de Jarvis.
