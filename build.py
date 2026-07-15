import PyInstaller.__main__
import os
import shutil

# Clean previous builds
if os.path.exists("build"):
    shutil.rmtree("build")
if os.path.exists("dist"):
    shutil.rmtree("dist")

print("Building PinPowerTool...")

# PyInstaller arguments
args = [
    'main.py',
    '--name=PinPowerTool',
    '--windowed',  # No console window
    '--noconfirm',
    '--clean',
    '--add-data=assets;assets',  # Include assets folder
    '--add-data=src;src',        # Include src folder (imports)
    # '--onefile', # Uncomment if single file exe is preferred, but dir is faster for debugging
]

# Add icon if exists
if os.path.exists("assets/logo.ico"):
    args.append('--icon=assets/logo.ico')

PyInstaller.__main__.run(args)

print("Build complete. Output in 'dist/PinPowerTool'")
