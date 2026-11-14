"""Bootstrap for tests that need Anki's bundled Python + Qt.

Import this first; it puts Anki's packages on sys.path, makes Qt headless and
creates the QApplication. Importing `anki.collection` before other anki modules
avoids a circular-import error.
"""

import os
import sys

APP_PACKAGES = "/Applications/Anki.app/Contents/Resources/app_packages"
if os.path.isdir(APP_PACKAGES) and APP_PACKAGES not in sys.path:
    sys.path.insert(0, APP_PACKAGES)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, Qt as _Qt  # noqa: E402

QCoreApplication.setAttribute(_Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

import anki.collection  # noqa: E402,F401  (import order matters)
import aqt  # noqa: E402,F401
