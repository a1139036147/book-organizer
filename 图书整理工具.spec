# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# 必须在加载任何 PyInstaller 内部 Hook 之前设置环境变量，使 TclTkInfo 能正确识别 Tcl/Tk
tcl_base = r'D:\图书管理\tcl'
if os.path.isdir(os.path.join(tcl_base, 'tcl8.6')):
    os.environ['TCL_LIBRARY'] = os.path.join(tcl_base, 'tcl8.6')
    os.environ['TK_LIBRARY'] = os.path.join(tcl_base, 'tk8.6')

from PyInstaller.utils.hooks import collect_all

datas = [
    (r'D:\图书管理\tcl', 'tcl'),
    (r'D:\图书管理\tcl\tcl8.6', '_tcl_data'),
    (r'D:\图书管理\tcl\tk8.6', '_tk_data'),
    (r'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\Lib\codex-rejected-cas.pem', '.'),
]

py_root = os.path.dirname(sys.executable)
py_dlls = os.path.join(py_root, 'DLLs')

binaries = []
for dll_name in ['_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll']:
    dll_path = os.path.join(py_dlls, dll_name)
    if os.path.exists(dll_path):
        binaries.append((dll_path, '.'))

hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.scrolledtext',
    'tkinter.constants',
    'bookshelf_manager',
    'calibre_shim',
    '_tkinter',
]

tmp_ret = collect_all('tkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('lxml')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    [r'D:\图书管理\gui.py'],
    pathex=[r'D:\图书管理'],
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
    a.binaries,
    a.datas,
    [],
    name='图书整理工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
