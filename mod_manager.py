import os
import sys
import ctypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from config import load_config, save_config
from config import resource_path
from ui import MainWindow, THEME_QSS
from i18n import init_i18n, tr
from utils import has_symlink_permission, relaunch_as_admin

def main():
    if sys.platform == "win32":
        cfg = load_config()
        if cfg.get("symlink_mode", True) and not has_symlink_permission():
            relaunch_as_admin()
            sys.exit(0)

        app_id = "chenbai.mod_manager"
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    app = QApplication(sys.argv)

    icon_path = resource_path("icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Modern style
    app.setStyle("Fusion")
    app.setStyleSheet(THEME_QSS)
    
    # Initialize i18n before any UI string is rendered
    init_i18n()
    from i18n import get_language, set_language
    set_language(get_language())
    
    cfg = load_config()
    if not cfg.get("agreed_disclaimer", False):
        msgBox = QMessageBox()
        msgBox.setWindowTitle(tr("免责声明"))
        msgBox.setText(tr(
            "<b>免责声明</b><br><br>"
            "1. 使用本工具所造成的任何直接或间接损失由使用者自行负责。<br>"
            "2. 因使用MOD对游戏账号造成的任何损失（包括但不限于封号）由使用者自行负责。<br><br>"
            "点击“同意”即代表您已知晓并接受以上条款。如果不同意，请点击“退出”。"
        ))
        msgBox.setIcon(QMessageBox.Icon.Warning)
        btn_agree = msgBox.addButton(tr("同意"), QMessageBox.ButtonRole.AcceptRole)
        btn_disagree = msgBox.addButton(tr("退出"), QMessageBox.ButtonRole.RejectRole)
        
        msgBox.exec()
        if msgBox.clickedButton() == btn_disagree:
            sys.exit(0)
        else:
            save_config({"agreed_disclaimer": True})

    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
