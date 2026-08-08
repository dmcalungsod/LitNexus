import os
import sys

from PyInstaller.utils.hooks import collect_all

# Ensure src is in path so collect_all can find the package
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

datas, binaries, hiddenimports = collect_all("downloader")
