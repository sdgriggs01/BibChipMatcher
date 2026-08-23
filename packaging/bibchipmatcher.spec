# PyInstaller spec for Bib Chip Matcher (onedir build: faster startup and
# fewer antivirus false-positives than --onefile; Inno Setup packages the
# whole output folder into one installer anyway, so onedir costs nothing on
# the distribution side).
#
# Build with: pyinstaller packaging/bibchipmatcher.spec

import os

project_root = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(SPECPATH, "entrypoint.py")],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BibChipMatcher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BibChipMatcher",
)
