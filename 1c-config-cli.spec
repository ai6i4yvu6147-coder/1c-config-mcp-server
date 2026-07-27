# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['sqlite3', 'json']
hiddenimports += collect_submodules('onec_metadata_schema')


a = Analysis(
    ['admin_tool\\cli.py'],
    pathex=[],
    binaries=[],
    # docs/agent-guide.md — same manual the MCP `guide` tool serves; the Hub reads it through
    # `1c-config-cli guide --json`, so the CLI bundle carries its own copy.
    datas=[('shared', 'shared'), ('docs/agent-guide.md', 'docs')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='1c-config-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
