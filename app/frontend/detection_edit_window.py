from pathlib import Path

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPixmap, QTransform, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.database.database_manager import DBManager
from app.common.lookup import ORIENTATION_LUT


class DetectionCanvas(QGraphicsView):
    rectangleDrawn = pyqtSignal(QRectF)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drawing_enabled = False
        self._start_position = None
        self._preview_rect = None

    def set_drawing_enabled(self, enabled: bool):
        self._drawing_enabled = enabled
        self._start_position = None
        self._preview_rect = None

    def mousePressEvent(self, event: QMouseEvent | None):
        if event is None:
            return
        if not self._drawing_enabled or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        scene = self.scene()
        if scene is None:
            return

        self._start_position = self.mapToScene(event.position().toPoint())
        self._preview_rect = scene.addRect(
            QRectF(self._start_position, self._start_position),
            QPen(Qt.GlobalColor.red, 2),
        )
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent | None):
        if event is None:
            return
        if self._start_position is None or self._preview_rect is None:
            super().mouseMoveEvent(event)
            return

        current_position = self.mapToScene(event.position().toPoint())
        self._preview_rect.setRect(
            QRectF(self._start_position, current_position).normalized()
        )
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent | None):
        if event is None:
            return
        if (
            self._start_position is None
            or event.button() != Qt.MouseButton.LeftButton
            or self._preview_rect is None
        ):
            super().mouseReleaseEvent(event)
            return

        scene = self.scene()
        if scene is None:
            return

        end_position = self.mapToScene(event.position().toPoint())
        rectangle = QRectF(self._start_position, end_position).normalized()
        rectangle = rectangle.intersected(scene.sceneRect())
        preview_rect = self._preview_rect
        self._start_position = None
        self._preview_rect = None

        if rectangle.width() < 1 or rectangle.height() < 1:
            scene.removeItem(preview_rect)
            event.accept()
            return

        preview_rect.setRect(rectangle)
        self.rectangleDrawn.emit(rectangle)
        event.accept()


class DetectionEditWindow(QDialog):
    def __init__(self, database: DBManager, path: str, parent=None):
        super().__init__(parent)
        self.database = database    
        self.path = path
        self._editing_detection_id = None

        self.setWindowTitle("Editar escenas")
        self.resize(1100, 700)
        self.setModal(True)

        self._load_detections()
        self._build_ui()
        self.display_detection()

    def _load_detections(self):

        self.detections = self.database.get_full_detections_by_path(self.path)
        
        # Load the image
        image_path = Path(self.path)
        self.img_pixmap = QPixmap(str(image_path))
        if self.img_pixmap.isNull():
            QMessageBox.critical(self, "Error", f"No se pudo cargar la imagen: {self.path}")
            self.reject()
            return
        
        # Load rotation
        img_properties = self.database.get_entry_properties(self.path)
        orientation = img_properties.get('orientation', 'none')
        if orientation in ORIENTATION_LUT:
            transform = QTransform().rotate(ORIENTATION_LUT[orientation])
            self.img_pixmap = self.img_pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        self.det_index = -1
      
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.info_label = QLabel("Modifica las detecciones como desees.")
        header.addWidget(self.info_label)
        header.addStretch()
        main_layout.addLayout(header)

        if not self.detections:
            self.info_label.setText("No hay detecciones para editar.")
            return

        content_row = QHBoxLayout()
        image_column = QVBoxLayout()
        self.image_canvas = DetectionCanvas(self)
        self.image_scene = QGraphicsScene(self.image_canvas)
        self.image_canvas.setScene(self.image_scene)
        self.image_canvas.rectangleDrawn.connect(self._save_drawn_rectangle)
        image_column.addWidget(self.image_canvas, stretch=1)
        self.name_label = QLabel("Nombre: Sin asignar", self)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_column.addWidget(self.name_label)
        content_row.addLayout(image_column, stretch=1)

        button_column = QVBoxLayout()
        self.remove_btn = QPushButton("Eliminar", self)
        self.rename_btn = QPushButton("Renombrar", self)
        self.edit_btn = QPushButton("Modificar", self)
        self.add_btn = QPushButton("Añadir", self)
        self.remove_btn.clicked.connect(self._remove_detection)
        self.rename_btn.clicked.connect(self._rename_detection)
        self.edit_btn.clicked.connect(self._edit_bbox)
        self.add_btn.clicked.connect(self._add_detection)
        button_column.addWidget(self.remove_btn)
        button_column.addWidget(self.rename_btn)
        button_column.addWidget(self.edit_btn)
        button_column.addWidget(self.add_btn)
        button_column.addStretch()
        content_row.addLayout(button_column)
        main_layout.addLayout(content_row, stretch=1)

        main_layout.addStretch()
        confirm_row = QHBoxLayout()
        confirm_row.addStretch()
        self.confirm_button = QPushButton("Siguiente", self)
        self.confirm_button.clicked.connect(self.display_detection)
        confirm_row.addWidget(self.confirm_button)
        main_layout.addLayout(confirm_row)

    def display_detection(self):
        if not self.detections:
            print("No hay detecciones para mostrar.")
            return

        self.det_index += 1
        if self.det_index >= len(self.detections):
            QMessageBox.information(self, "Edición finalizada", "No hay más detecciones para mostrar.")
            self.accept()
            return        
        
        self.info_label.setText("Modifica la detección como desees.")
        detection = self.detections[self.det_index]
        identity = detection.get("identity_id", "None")
        self.name_label.setText(f"ID asignado: {identity }")

        # crop image to bbox
        x, y, x2, y2 = [int(a) for a in detection['bbox']]
        w, h = x2 - x, y2 - y
        pixmap = self.img_pixmap.copy(x, y, w, h)

        # Display the image in the graphics view
        self.image_scene.setSceneRect(QRectF(pixmap.rect()))
        self.image_scene.clear()
        self.image_scene.addPixmap(pixmap)
        QTimer.singleShot(0, self._fit_image_to_view)

    def display_full_img(self):
        if not self.img_pixmap or self.img_pixmap.isNull():
            print("No hay imagen para mostrar.")
            return

        self.info_label.setText("Dibuja el rectángulo de la nueva detección.")
        
        # Display the image in the graphics view
        self.image_scene.setSceneRect(QRectF(self.img_pixmap.rect()))
        self.image_scene.clear()
        self.image_scene.addPixmap(self.img_pixmap)
        QTimer.singleShot(0, self._fit_image_to_view)

    def _fit_image_to_view(self):
        self.image_canvas.fitInView(
            self.image_scene.sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def _remove_detection(self):
        if self.det_index < 0 or self.det_index >= len(self.detections):
            QMessageBox.warning(self, "Error", "No hay detecciones para eliminar.")
            return

        det_id = self.detections[self.det_index]['id']
        try:
            self.database.remove_detection(det_id)
        except ValueError as e:
            QMessageBox.warning(self, "Error al eliminar", str(e))

        self.display_detection()

    def _rename_detection(self):
        if self.det_index < 0 or self.det_index >= len(self.detections):
            QMessageBox.warning(self, "Error", "No hay detecciones para renombrar.")
            return

        det_id = self.detections[self.det_index]['id']
        new_name, ok = QInputDialog.getText(self, "Renombrar detección", "Nuevo nombre:")
        if ok and new_name:
            try:
                self.database.assign_identity(det_id, new_name)
            except ValueError as e:
                QMessageBox.warning(self, "Error al renombrar", str(e))
            self.name_label.setText(f"ID asignado: {new_name }")

    def _edit_bbox(self):
        if self.det_index < 0 or self.det_index >= len(self.detections):
            QMessageBox.warning(self, "Error", "No hay detecciones para modificar.")
            return

        self._editing_detection_id = self.detections[self.det_index]['id']
        self.display_full_img()
        self.image_canvas.set_drawing_enabled(True)

    def _add_detection(self):
        self._editing_detection_id = None
        self.display_full_img()
        self.image_canvas.set_drawing_enabled(True)

    def _save_drawn_rectangle(self, rectangle: QRectF):
        left = max(0, min(self.img_pixmap.width(), round(rectangle.left())))
        top = max(0, min(self.img_pixmap.height(), round(rectangle.top())))
        right = max(0, min(self.img_pixmap.width(), round(rectangle.right())))
        bottom = max(0, min(self.img_pixmap.height(), round(rectangle.bottom())))
        if right <= left or bottom <= top:
            return

        bbox = [float(left), float(top), float(right), float(bottom)]
        try:
            if self._editing_detection_id is None:
                detection_id = self.database.add_manual_detection(self.path, bbox)
                identity = self._ask_identity()
                if identity:
                    self.database.assign_identity(detection_id, identity)
                    self.name_label.setText(f"ID asignado: {identity }")
            else:
                detection_id = self._editing_detection_id
                self.database.update_detection_bbox(detection_id, bbox)
        except ValueError as error:
            QMessageBox.warning(self, "Error al guardar la detección", str(error))
            return

        self._editing_detection_id = None
        self.image_canvas.set_drawing_enabled(False)

    def _ask_identity(self):
        """Solicita al usuario el nombre de nueva detección."""
        nombre, ok = QInputDialog.getText(
            self,
            "Nombre de la nueva detección",
            "",
            text="JoseAntonio",
        )

        if not ok or not nombre.strip():
            QMessageBox.warning(self, "Error de nombre", "No se asignará nombre a la nueva detección")
            return None

        return nombre.strip()


