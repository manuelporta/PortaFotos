from PyQt6.QtWidgets import QApplication
from app.frontend.main_window import MainWindow


def main():
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()