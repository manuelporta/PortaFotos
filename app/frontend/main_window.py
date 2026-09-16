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
    QPushButton,
    QFormLayout,
    QProgressBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QPainter, QPen, QTransform
from PyQt6.QtGui import QPixmap

from app.common.exceptions import UnknownError
from app.database.database_manager import DBManager
from app.backend.data_processing import GalleryManager
from app.backend.gallery_processor import GalleryProcessor

from app.common.lookup import ORIENTATION_LUT


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PortaFotos")
        self.resize(800, 600)
        self._create_status_bar()
        self._create_menu()
        self._create_main_widget()

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
        status.addPermanentWidget(self._status_label)

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        status.addPermanentWidget(self._progress_bar)

    def log_status(self, message: str) -> None:
        """Update the bottom status label with a short message."""
        if hasattr(self, "_status_label") and self._status_label is not None:
            self._status_label.setText(message)
        else:
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

    def _create_main_widget(self):
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
        self.img_list.currentItemChanged.connect(self.on_list_current_changed)
        h.addWidget(self.img_list, 1)
        self.populate_list_from_db()

        # Center: image display (60%)
        # Container for image + controls
        img_container = QWidget(self.main_widget)
        img_v = QVBoxLayout()

        self.image_label = QLabel(img_container)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setMinimumSize(200, 200)
        img_v.addWidget(self.image_label, 1)

        # Rotate buttons side-by-side
        btn_row = QWidget(img_container)
        btn_layout = QHBoxLayout()

        rotate_left_btn = QPushButton("Rotar L", img_container)
        rotate_left_btn.clicked.connect(self.rotate_left)
        rotate_right_btn = QPushButton("Rotar R", img_container)
        rotate_right_btn.clicked.connect(self.rotate_right)

        btn_layout.addWidget(rotate_left_btn)
        btn_layout.addWidget(rotate_right_btn)
        btn_row.setLayout(btn_layout)

        img_v.addWidget(btn_row, 0, Qt.AlignmentFlag.AlignCenter)

        img_container.setLayout(img_v)
        h.addWidget(img_container, 3)

        # Right: properties (20%)
        self.right_props = QWidget(self.main_widget)
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.prop_filename = QLabel("--")
        self.prop_date = QLabel("--")
        self.prop_camera = QLabel("--")
        self.prop_scene = QLabel("--")
        form.addRow("Nombre:", self.prop_filename)
        form.addRow("Fecha de creación estimada:", self.prop_date)
        form.addRow("Modelo de cámara:", self.prop_camera)
        form.addRow("Tipo de escena:", self.prop_scene)
        # Set labels to bold
        for i in range(form.rowCount()):
            label = form.itemAt(i, QFormLayout.ItemRole.LabelRole)
            if label:
                widget = label.widget()
                if widget:
                    widget.setStyleSheet("font-weight: bold;")

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

    def keyPressEvent(self, a0):
        """Allow navigating `self.img_list` with Up/Down arrows and update view.

        Uses parameter name `a0` to match PyQt6 stubs and avoid type-checker override warnings.
        """
        if not a0:
            return super().keyPressEvent(a0)
        
        key = a0.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            if self.img_list is None:
                return super().keyPressEvent(a0)

            count = self.img_list.count()
            if count == 0:
                return super().keyPressEvent(a0)

            current = self.img_list.currentRow()
            if current < 0:
                # No selection yet: start at first/last depending on key
                new = 0 if key == Qt.Key.Key_Down else count - 1
            else:
                delta = 1 if key == Qt.Key.Key_Down else -1
                new = max(0, min(count - 1, current + delta))

            if new != current:
                self.img_list.setCurrentRow(new)
                item = self.img_list.currentItem()
                if item is not None:
                    self.on_list_current_changed(item, item)
            return

        return super().keyPressEvent(a0)
    
    def on_list_current_changed(self, current: QListWidgetItem, previous: QListWidgetItem) -> None:
        """ Carga la imagen seleccionada en la interfaz"""

        if not self.database:
            return

        # Comprobar path seleccionado
        path = current.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        path = Path(path)
        if not path.exists():
            self.log_status("Archivo no encontrado")
            return

        self.current_path = path

        # Cargar imagen y mostrar en el panel central
        img_properties = self.database.get_entry_properties(str(path))
        pix = QPixmap(str(path))
        if pix.isNull():
            self.log_status("No se pudo cargar la imagen")
            return

        orientation = img_properties.get('orientation', 'none')
        if orientation in ORIENTATION_LUT:
            transform = QTransform().rotate(ORIENTATION_LUT[orientation])
            pix = pix.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        pix = self.draw_boxes_on_pixmap(pix, str(path))

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
        if hasattr(self, "prop_date"):
            self.prop_date.setText(img_properties.get('date', 'Unknown'))
        if hasattr(self, "prop_camera"):
            self.prop_camera.setText(img_properties.get('camera_model', 'Unknown'))
        if hasattr(self, "prop_scene"):
            self.prop_scene.setText(img_properties.get('scene_type', 'Unknown'))

        self.log_status(f"Mostrando: {path.name}")

    def rotate_left(self):
        """Rotate the current pixmap 90 degrees counter-clockwise and update display."""
        if not self._current_pixmap or self.image_label is None:
            return

        transform = QTransform().rotate(-90)
        rotated = self._current_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        self._current_pixmap = rotated

        scaled = rotated.scaled(
            self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.log_status("Imagen rotada a la izquierda")

    def rotate_right(self):
        """Rotate the current pixmap 90 degrees clockwise and update display."""
        if not self._current_pixmap or self.image_label is None:
            return

        transform = QTransform().rotate(90)
        rotated = self._current_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        self._current_pixmap = rotated

        scaled = rotated.scaled(
            self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.log_status("Imagen rotada a la derecha")

    def resizeEvent(self, a0):
        # Ensure pixmap scales when window is resized
        super().resizeEvent(a0)
        if self._current_pixmap and self.image_label is not None:
            scaled = self._current_pixmap.scaled(
                self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)

    def draw_boxes_on_pixmap(self, pixmap, path):

        if not self.database:
            return pixmap

        bboxes = self.database.get_bboxes(path)
        if not bboxes or len(bboxes) == 0:
            return pixmap

        annotated = QPixmap(pixmap)

        painter = QPainter(annotated)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(Qt.GlobalColor.red)
        pen.setWidth(int(min(pixmap.width(), pixmap.height()) / 200))
        painter.setPen(pen)

        for (x1, y1, x2, y2) in bboxes:
            painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))

        painter.end()

        return annotated

    def cargar_portafotos(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar portafotos o imagen",
            "",
            "PortaFotos DB (*.db);;All Files (*)",
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
                if any(dir_path.iterdir()):
                    self.log_status(f"Creando nuevo portafotos en: {dir_path}")
                    self.info_label.setText(f"Creando nuevo portafotos en: {dir_path}")

                    db_path = dir_path / "portafotos.db"
                    self.gallery = GalleryManager(dir_path, db_path)
                    self.gallery.read_images()
                    if not self.gallery.files:
                        self.log_status("La carpeta seleccionada está vacía.")
                        return

                    self.log_status(f"{len(self.gallery.files)} imágenes detectadas en {dir_path}. Iniciando procesado...")
                    GalleryProcessor(self).process()
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