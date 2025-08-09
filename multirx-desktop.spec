# multirx-desktop.spec

# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

project_root = os.path.abspath(".")  # Root directory of your project

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'app', 'templates'), 'app/templates'),
        (os.path.join(project_root, 'app', 'static'), 'app/static'),
        (os.path.join(project_root, 'staticfiles'), 'staticfiles'),
        (os.path.join(project_root, 'media'), 'media'),
        (os.path.join(project_root, 'multirx'), 'multirx'),  # ✅ include the Django project
        (os.path.join(project_root, 'app/static/fonts'), 'fonts'),
    ],
    hiddenimports=collect_submodules('weasyprint'),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='multirx-desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    onefile=True, 
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='multirx-desktop'
)
