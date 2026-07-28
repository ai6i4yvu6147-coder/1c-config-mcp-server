# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# docs/agent-guide.md — the server's own manual, returned by the `guide` tool. It is code,
# not module data: it belongs to the server version, so it ships inside the bundle.
datas = [('server', 'server'), ('shared', 'shared'), ('docs/agent-guide.md', 'docs')]
binaries = []
hiddenimports = ['sqlite3', 'uuid', 'json', 'asyncio', 'xml.etree.ElementTree', 'xml.etree']
tmp_ret = collect_all('xml')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['server\\server.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
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
    [],
    exclude_binaries=True,
    name='1c-config-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='1c-config-server',
)
