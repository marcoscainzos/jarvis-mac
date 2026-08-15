from PyInstaller.utils.hooks import collect_all, collect_submodules


datas = []
binaries = []
hiddenimports = collect_submodules("jarvis") + collect_submodules("pynput")

for package in (
    "av",
    "certifi",
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
    "numpy",
    "onnxruntime",
    "sounddevice",
    "tokenizers",
    "Vision",
    "CoreML",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

a = Analysis(
    ["packaging/jarvis_app.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Jarvis",
)

app = BUNDLE(
    coll,
    name="Jarvis.app",
    bundle_identifier="dev.marcoscainzos.jarvis",
    version="0.4.0",
    target_arch="arm64",
    info_plist={
        "CFBundleDisplayName": "Jarvis",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "Jarvis necesita oír tus órdenes.",
        "NSScreenCaptureUsageDescription": "Jarvis necesita ver la ventana cuando se lo pidas.",
    },
)
