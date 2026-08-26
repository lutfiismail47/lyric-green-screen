import sys
import ctypes
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from core.transcriber import resolve_asset_path


def main():
    app = QApplication(sys.argv)
    
    app_id = "com.autocaption.app"
    app.setApplicationName("Mimik | Turn Audio into Lyrics, Instantly")
    app.setDesktopFileName(app_id)

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    icon_path = resolve_asset_path("assets/icon.png")
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()