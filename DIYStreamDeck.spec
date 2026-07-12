# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for DIYStreamDeck menu-bar app.

Build:
    ./build-app.sh          # or: .venv/bin/pyinstaller DIYStreamDeck.spec --clean --noconfirm

Install:
    cp -r dist/DIYStreamDeck.app /Applications/
    src/mac/service/install-service.sh --app
"""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
REPO = os.path.abspath('.')

# PyObjC packages use lazy __getattr__ dispatch — collect_all grabs the .so
# extensions and metadata that static AST analysis would miss.
datas_objc,   binaries_objc,   hi_objc   = collect_all('objc')
datas_found,  binaries_found,  hi_found  = collect_all('Foundation')
datas_appkit, binaries_appkit, hi_appkit = collect_all('AppKit')
datas_cocoa,  binaries_cocoa,  hi_cocoa  = collect_all('Cocoa')
datas_cf,     binaries_cf,     hi_cf     = collect_all('CoreFoundation')

hi_rumps       = collect_submodules('rumps')
hi_spotipy     = collect_submodules('spotipy')
hi_serial      = collect_submodules('serial')
hi_playsound   = collect_submodules('playsound3')
hi_pyobjctools = collect_submodules('PyObjCTools')

a = Analysis(
    [os.path.join('src', 'mac', 'statusbar.py')],
    pathex=[REPO],
    binaries=(binaries_objc + binaries_found + binaries_appkit +
              binaries_cocoa + binaries_cf),
    datas=(
        datas_objc + datas_found + datas_appkit + datas_cocoa + datas_cf +
        [
            # Plugin .py files must be real files on disk (watchdog uses spec_from_file_location)
            (os.path.join('src', 'mac', 'plugins'), os.path.join('src', 'mac', 'plugins')),
            # Key layout JSON
            (os.path.join('src', 'pi_pico', 'key_def.json'), os.path.join('src', 'pi_pico')),
            # Menu bar icon
            (os.path.join('src', 'mac', 'assets', 'grid_icon.png'), os.path.join('src', 'mac', 'assets')),
        ]
    ),
    hiddenimports=(
        hi_objc + hi_found + hi_appkit + hi_cocoa + hi_cf +
        hi_rumps + hi_spotipy + hi_serial + hi_playsound + hi_pyobjctools +
        [
            # PyObjC extension modules missed by static analysis
            'objc._objc',
            'objc._machsignals',
            'Foundation._Foundation',
            'Foundation._inlines',
            'AppKit._AppKit',
            'AppKit._inlines',
            'AppKit._nsapp',
            'CoreFoundation._CoreFoundation',
            'CoreFoundation._inlines',
            # pyserial macOS port detection
            'serial.tools.list_ports_osx',
            'serial.tools.list_ports_posix',
            # spotipy runtime imports
            'spotipy.cache_handler',
            'spotipy.oauth2',
            # our src packages
            'src',
            'src.mac',
            'src.mac.statusbar',
            'src.mac.watchdog',
            'src.mac.layout_formatter',
            'src.mac.plugins',
            'src.mac.plugins.base_plugin',
            'src.mac.plugins.claude',
            'src.mac.plugins.hue',
            'src.mac.plugins.sounds',
            'src.mac.plugins.spotify',
        ]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'serial.tools.list_ports_windows',
        'matplotlib', 'numpy', 'PIL', 'tkinter', '_tkinter',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    ],
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
    name='DIYStreamDeck',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,       # UPX corrupts macOS .so extensions
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='DIYStreamDeck',
)

app = BUNDLE(
    coll,
    name='DIYStreamDeck.app',
    icon=None,
    bundle_identifier='com.lennarthennigs.diystreamdeck',
    info_plist={
        'LSUIElement': True,
        'CFBundleIdentifier': 'com.lennarthennigs.diystreamdeck',
        'CFBundleName': 'DIYStreamDeck',
        'CFBundleDisplayName': 'DIY StreamDeck',
        'CFBundleVersion': '1.2.2',
        'CFBundleShortVersionString': '1.2.2',
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'LSMinimumSystemVersion': '12.0',
        'NSHighResolutionCapable': True,
        # Homebrew non-framework Python workaround: prevents the bundled Python
        # from searching for its stdlib outside the bundle.
        'LSEnvironment': {'PYTHONHOME': ''},
    },
)
