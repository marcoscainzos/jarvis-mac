import multiprocessing


if __name__ == "__main__":
    # PyInstaller vuelve a ejecutar este binario para procesos auxiliares de
    # Whisper. Debe interceptarlos antes de importar cualquier interfaz Cocoa.
    multiprocessing.freeze_support()

    from jarvis.menu_bar import main

    main()
