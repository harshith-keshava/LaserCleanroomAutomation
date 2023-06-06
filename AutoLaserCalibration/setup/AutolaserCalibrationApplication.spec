# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

from PyInstaller.utils.hooks import collect_submodules
hidden_imports_Model = collect_submodules('Model')
hidden_imports_View = collect_submodules('View')
hidden_imports_Config = collect_submodules('ConfigFiles')
all_hidden_imports = hidden_imports_Model + hidden_imports_View + hidden_imports_Config

a = Analysis(
    ['AutolaserCalibrationApplication.py'],
    pathex=['C:\GitKraken\AutoLaserCalibration'],
    binaries=[],
    datas=[],
    hiddenimports=all_hidden_imports,
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
    [],
    exclude_binaries=True,
    name='LaserApplication',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='.\View\images\laser-warning_39051.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutolaserCalibrationApplication',
)
