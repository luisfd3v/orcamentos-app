# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('src/ui', 'ui'),
        ('src/database.py', '.'),
        ('src/models.py', '.'),
        ('src/pdf_generator.py', '.'),
        ('ico', 'ico'),
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.messagebox',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.scrolledtext',
        'pyodbc',
        'reportlab',
        'reportlab.pdfgen',
        'reportlab.lib',
        'reportlab.lib.styles',
        'reportlab.lib.units',
        'reportlab.platypus',
        'sqlite3',
        'json',
        'datetime',
        'os',
        'sys',
        'pathlib',
        'configparser',
        'decimal',
        're',
        'collections',
        'itertools',
    ],
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
    name='Orcamentos',
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
    icon='C:\\repos\\orcamentos-app\\ico\\pedido.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Orcamentos',
)
