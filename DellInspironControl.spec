# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['dell_control.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['win32timezone', 'win32com.client'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Qt 6.12 on Windows uses Microsoft's system ICU (unversioned exports).
# An unrelated ICU from a PDF/toolchain directory in PATH may be picked up by
# binary analysis and has incompatible version-suffixed exports. Do not bundle it.
a.binaries = [entry for entry in a.binaries
              if entry[0].replace('\\', '/').rsplit('/', 1)[-1].lower()
              not in {'icuuc.dll', 'icudt78.dll'}]
# This is a Widgets app: do not redistribute unrelated PDF/virtual-keyboard/QML
# plugins and their libraries discovered in the build machine's Qt installation.
def used_by_widgets(entry):
    name = entry[0].replace('\\', '/').lower()
    base = name.rsplit('/', 1)[-1]
    if base in {'qt6pdf.dll', 'qt6virtualkeyboard.dll', 'qpdf.dll', 'qtvirtualkeyboardplugin.dll'}:
        return False
    return not base.startswith(('qt6qml', 'qt6quick'))
a.binaries = [entry for entry in a.binaries if used_by_widgets(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DellInspironControl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DellInspironControl',
)
