# Jarvis para macOS

Un asistente personal que vive en tu Mac. Esta primera versión funciona en la
terminal, procesa las órdenes localmente y solo abre aplicaciones incluidas en
una lista segura.

## Funciones de la versión 0.1

- Saludar y responder la hora.
- Abrir Calculadora, Calendario, Notas, Safari o Terminal.
- Rechazar órdenes desconocidas sin ejecutar comandos arbitrarios.
- Salir con `salir`, `adiós` o `Ctrl+C`.

## Requisitos

- macOS.
- Python 3.11 o posterior.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Uso

```bash
jarvis
```

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

La versión 0.1 no usa Internet ni recopila conversaciones. Los futuros secretos
se guardarán en `.env`, que está excluido de Git. Nunca publiques claves de API,
grabaciones o información personal.

## Próximos hitos

- **v0.2:** escuchar y responder por voz.
- **v0.3:** memoria local con SQLite.
- **v0.4:** icono y controles en la barra de menús.
- **v1.0:** asistente configurable y estable.

