# Jarvis

Un asistente personal cuyo cerebro está diseñado para funcionar en diferentes
dispositivos. La versión actual incluye adaptadores de voz y acciones para macOS.

## Funciones de la versión 0.2

- Saludar y responder la hora.
- Abrir Calculadora, Calendario, Notas, Safari o Terminal.
- Rechazar órdenes desconocidas sin ejecutar comandos arbitrarios.
- Salir con `salir`, `adiós` o `Ctrl+C`.
- Escuchar una frase al pulsar Intro y responder con la voz de macOS.
- Reconocer voz en el dispositivo, sin enviar la grabación a una API externa.

## Requisitos

- macOS.
- Python 3.11 o posterior.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Para instalar también el reconocimiento de voz local:

```bash
python -m pip install -e '.[voice]'
```

## Uso

```bash
jarvis
```

Para activar el modo de voz:

```bash
jarvis --voice
```

La primera vez se descargará el modelo de Whisper y macOS solicitará permiso
para usar el micrófono. Después, la transcripción se realiza en el dispositivo.

También puedes ejecutarlo sin instalarlo:

```bash
PYTHONPATH=src python3 -m jarvis.cli
```

Prueba órdenes como `hola Jarvis`, `qué hora es` o `abre Calculadora`.

## Pruebas

Tras instalar pytest con `python -m pip install pytest`:

```bash
pytest
```

## Privacidad

La versión 0.2 no usa una API de voz ni recopila conversaciones. El modelo se
descarga una vez y la transcripción se ejecuta localmente. La grabación temporal
se elimina después de transcribirla. Los futuros secretos
se guardarán en `.env`, que está excluido de Git. Nunca publiques claves de API,
grabaciones o información personal.

## Próximos hitos

- **v0.3:** memoria local con SQLite.
- **v0.4:** icono y controles en la barra de menús.
- **v1.0:** asistente configurable y estable.

## Otros dispositivos

El intérprete de órdenes no depende de macOS. Para Windows, Linux, Android o
Raspberry Pi añadiremos implementaciones específicas de `Listener`, `Speaker`
y apertura de aplicaciones, manteniendo el mismo núcleo de Jarvis.
