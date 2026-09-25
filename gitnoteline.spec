# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None
project_root = os.path.abspath('.')

# Collect all data files, then exclude non-distributable directories
all_datas = []
for root, dirs, files in os.walk('web'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        src = os.path.join(root, f)
        dst = os.path.relpath(root, '.')
        all_datas.append((src, dst))

for root, dirs, files in os.walk('core'):
    dirs[:] = [d for d in dirs if d != '__pycache__']
    for f in files:
        if f.endswith('.py'):
            src = os.path.join(root, f)
            dst = os.path.relpath(root, '.')
            all_datas.append((src, dst))

all_datas.append(('BUILD_NOTICE', '.'))

a = Analysis(
    ['web/__main__.py'],
    pathex=[project_root],
    binaries=[],
    datas=all_datas,
    hiddenimports=['core.services', 'core.credentials', 'core.database', 'core.config'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GitNoteLine-PC',
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
