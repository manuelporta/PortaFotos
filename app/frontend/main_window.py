from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QListWidgetItem,
    QMainWindow,
    QStatusBar,
    QWidget,
    QLabel,
    QVBoxLayout,
    QFileDialog,
    QListWidget,
    QHBoxLayout,
    QSizePolicy,
    QFormLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QPixmap

from app.common.exceptions import UnknownError
from app.database.database_manager import DBManager
from app.backend.data_processing import GalleryManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PortaFotos")
        self.resize(800, 600)
        self._create_status_bar()
        self._create_menu()
        self._create_central_widget()

        self.database = None
        self.gallery = None

        self._current_pixmap = None
        self.current_path = None

        self.log_status("Listo")

    def _create_status_bar(self):
        # Use QStatusBar with a QLabel to show application state
        status = QStatusBar(self)
        self.setStatusBar(status)

        self._status_label = QLabel("Cargando", self)
        # Add as a permanent widget so it stays visible on the right; use addWidget to align left
        status.addPermanentWidget(self._status_label)

    def log_status(self, message: str) -> None:
        """Update the bottom status label with a short message."""
        if hasattr(self, "_status_label") and self._status_label is not None:
            self._status_label.setText(message)
        else:
            # Fallback to statusBar message if label not present
            status_bar = self.statusBar()
            if status_bar:
                status_bar.showMessage(message)
            else:
                raise UnknownError

    def _create_menu(self):
        menubar = self.menuBar()
        if menubar is None:
            raise UnknownError
        
        archivo_menu = menubar.addMenu("Archivo")
        if archivo_menu is None:
            raise UnknownError

        cargar_action = QAction("Cargar portafotos", self)
        crear_action = QAction("Crear nuevo portafotos", self)

        cargar_action.triggered.connect(self.cargar_portafotos)
        crear_action.triggered.connect(self.crear_portafotos)

        archivo_menu.addAction(cargar_action)
        archivo_menu.addAction(crear_action)

    def _create_central_widget(self):
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout()

        # Initial placeholder message
        self.info_label = QLabel(
            "Interfaz de PortaFotos\n\nUse 'Archivo' → 'Cargar portafotos' o 'Crear nuevo portafotos'"
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.info_label)

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        # Placeholders for the three-pane layout (created on demand)
        self.img_list: QListWidget | None = None
        self.image_label: QLabel | None = None
        self.right_props: QWidget | None = None
        self._current_pixmap: QPixmap | None = None

    def _init_layout(self):
        if self.database is None:
            return
        
        # If already created, do nothing
        if self.img_list is not None:
            return

        # Clear placeholder widgets
        for i in reversed(range(self.main_layout.count())):
            item = self.main_layout.takeAt(i)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # Create horizontal layout with 20/60/20 stretches (1:3:1)
        h = QHBoxLayout()

        # Left: list of names (20%)
        self.img_list = QListWidget(self.main_widget)
        self.img_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.img_list.itemClicked.connect(self.on_list_item_clicked)
        h.addWidget(self.img_list, 1)
        self.populate_list_from_db()

        # Center: image display (60%)
        self.image_label = QLabel(self.main_widget)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(200, 200)
        h.addWidget(self.image_label, 3)

        # Right: properties (20%)
        self.right_props = QWidget(self.main_widget)
        form = QFormLayout()
        self.prop_filename = QLabel("--")
        self.prop_size = QLabel("--")
        self.prop_dimensions = QLabel("--")
        form.addRow("Nombre:", self.prop_filename)
        form.addRow("Tamaño (bytes):", self.prop_size)
        form.addRow("Dimensiones:", self.prop_dimensions)
        self.right_props.setLayout(form)
        h.addWidget(self.right_props, 1)

        self.main_layout.addLayout(h)


    def populate_list_from_db(self) -> None:
        """Puebla `self.img_list` con entradas de la base de datos (usa entry.path)."""
        if self.database is None or self.img_list is None:
            return
        self.img_list.clear()
        for p in self.database.get_all_paths():
            name = Path(p).name
            item = QListWidgetItem(name)
            # Guardar la ruta completa en UserRole para recuperarla luego
            item.setData(Qt.ItemDataRole.UserRole, str(p))
            self.img_list.addItem(item)

    def on_list_item_clicked(self, item: QListWidgetItem) -> None:
        """ Carga la imagen seleccionada en la interfaz"""

        # Comprobar path seleccionado
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        path = Path(path)
        if not path.exists():
            self.log_status("Archivo no encontrado")
            return

        self.current_path = path

        # Cargar imagen y mostrar en el panel central
        pix = QPixmap(str(path))
        if pix.isNull():
            self.log_status("No se pudo cargar la imagen")
            return

        self._current_pixmap = pix
        if self.image_label:
            scaled = pix.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)

        # Actualizar propiedades en la columna derecha
        if hasattr(self, "prop_filename"):
            self.prop_filename.setText(path.name)
        if hasattr(self, "prop_size"):
            self.prop_size.setText(str(path.stat().st_size))
        if hasattr(self, "prop_dimensions"):
            self.prop_dimensions.setText(f"{pix.width()} x {pix.height()}")

        self.log_status(f"Mostrando: {path.name}")


    def resizeEvent(self, a0):
        # Ensure pixmap scales when window is resized
        super().resizeEvent(a0)
        if self._current_pixmap and self.image_label is not None:
            scaled = self._current_pixmap.scaled(
                self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def cargar_portafotos(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar portafotos o imagen",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;PortaFotos DB (*.db);;All Files (*)",
        )

        if not path:
            self.log_status("No se ha introducido ninguna ruta.")
            return

        path = Path(path)
        if not path.exists() or not path.is_file():
            self.log_status("La ruta introducida no corresponde a un archivo.")
            return

        # If a database was selected, preserve old behavior
        if path.suffix.lower() == ".db":
            self.database = DBManager(path)
            self.info_label.setText(f"Cargado DB: {path}")
            self.log_status(f"Cargado DB: {path}")

            self._init_layout()

        # Unknown type fallback
        self.log_status("Tipo de archivo no soportado.")

    def crear_portafotos(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta para nuevo portafotos")
        if dir_path:
            dir_path = Path(dir_path)
            if dir_path.exists() and dir_path.is_dir():
                # Check dir is not empty
                if any(dir_path.iterdir()):

                    db_path = dir_path / "portafotos.db"
                    self.gallery = GalleryManager(dir_path, db_path)
                    self.gallery.create()

                    self.log_status(f"Nuevo portafotos creado en: {dir_path}")
                    self.info_label.setText(f"Nuevo portafotos creado en: {dir_path}")
                else:
                    self.log_status("La carpeta seleccionada está vacía.")
            else:
                self.log_status("La ruta introducida no corresponde a una carpeta.")
        else:
            self.log_status("No se ha introducido ninguna ruta.")



def main():
    import sys

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()