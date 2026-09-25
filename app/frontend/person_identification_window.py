from pathlib import Path

import hdbscan
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QTransform
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database.database_manager import DBManager
from app.common.lookup import ORIENTATION_LUT


DISTANCE_THRESHOLD = 0.55


class PersonIdentificationWindow(QDialog):
    def __init__(self, database: DBManager, parent=None):
        super().__init__(parent)
        self.database = database    
        self.selected_faces = set()

        self.setWindowTitle("Identificar personas")
        self.resize(1100, 700)
        self.setModal(True)

        self._build_ui()
        self._load_detections()
        self.cluster_index = 0
        self._display_detections(self.cluster_index)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.selection_label = QLabel("Selecciona las imágenes de la misma persona")
        header.addWidget(self.selection_label)
        header.addStretch()
        main_layout.addLayout(header)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        # TODO review scroll horizontal
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.image_container = QWidget(self.scroll_area)
        self.image_grid = QGridLayout(self.image_container)
        self.image_grid.setSpacing(12)
        self.image_grid.setContentsMargins(12, 12, 12, 12)
        self.scroll_area.setWidget(self.image_container)
        main_layout.addWidget(self.scroll_area, 1)

        self.current_checkboxes = {}

        form_layout = QHBoxLayout()
        self.toggle_all_button = QPushButton("Desmarcar todas", self)
        self.toggle_all_button.clicked.connect(self._toggle_all_checkboxes)
        form_layout.addWidget(self.toggle_all_button)

        form_layout.addWidget(QLabel("Etiqueta:"))
        self.name_input = QLineEdit(self)
        self.name_input.setPlaceholderText("Inserta el nombre o etiqueta de la persona")
        form_layout.addWidget(self.name_input)

        self.next_button = QPushButton("Siguiente", self)
        self.next_button.clicked.connect(self.on_next_clicked)
        form_layout.addWidget(self.next_button)

        main_layout.addLayout(form_layout)

    def _load_detections(self):

        keep_labels = self._ask_keep_labels()

        msg_label = QLabel("Cargando clusters de imágenes...")
        self.image_grid.addWidget(msg_label, 0, 0)

        detections = self.database.get_all_embeddings()
        if not detections:
            self.selection_label.setText("No hay rostros detectados para clusterizar.")
            self.next_button.setEnabled(False)
            self.name_input.setEnabled(False)
            return

        detection_ids = []
        embeddings = []

        for detection_id, embedding, identity_id in detections:
            if embedding is None:
                continue
            if keep_labels and identity_id is not None:
                continue
            detection_ids.append(detection_id)
            embeddings.append(np.asarray(embedding, dtype=np.float64))

        if not embeddings:
            self.selection_label.setText("No hay embeddings válidos para clusterizar.")
            self.next_button.setEnabled(False)
            self.name_input.setEnabled(False)
            return

        vectors = np.vstack(embeddings)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = vectors / norms

        similarity = normalized @ normalized.T
        distance = 1.0 - similarity
        np.fill_diagonal(distance, 0.0)

        clusterer = hdbscan.HDBSCAN(
            metric="precomputed",
            min_cluster_size=2,
            min_samples=1,
            cluster_selection_epsilon=DISTANCE_THRESHOLD,
            allow_single_cluster=True,
        )

        labels = clusterer.fit_predict(distance)

        self.detection_clusters = {
            det_id: int(label)
            for det_id, label in zip(detection_ids, labels)
        }

        cluster_count = len({label for label in labels if label != -1})
        self.selection_label.setText(
            f"Se han detectado {cluster_count} cluster(s) con un umbral de similitud coseno de {DISTANCE_THRESHOLD:.2f}"
        )

        self.cluster_to_detections = {}
        for det_id, label in self.detection_clusters.items():
            self.cluster_to_detections.setdefault(int(label), []).append(det_id)

        if cluster_count == 0:
            self.selection_label.setText(
                "No se ha encontrado ninguna agrupación clara con el umbral actual."
            )
            self.next_button.setEnabled(False)
            self.name_input.setEnabled(False)
            return

        self.next_button.setEnabled(True)
        self.name_input.setEnabled(True)


    def _ask_keep_labels(self):
        reply = QMessageBox.question(
            self,
            "Mantener etiquetas existentes",
            "¿Desea mantener las etiquetas existentes en la base de datos?\n"
            "Si selecciona 'No', se eliminarán todas las etiquetas anteriores.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _display_detections(self, n: int = 0):

        self._clear_image_grid()

        if not self.cluster_to_detections or len(self.cluster_to_detections) == 0:
            empty_label = QLabel("No hay imágenes disponibles para identificar.")
            self.image_grid.addWidget(empty_label, 0, 0)
            return
        if n >= len(self.cluster_to_detections):
            empty_label = QLabel("Se han etiquetado todos los clusters.")
            self.image_grid.addWidget(empty_label, 0, 0)
            return

        cluster_ids = list(self.cluster_to_detections.keys())
        det_ids = self.cluster_to_detections[cluster_ids[n]]
        self.current_checkboxes = {}
        for index, det_id in enumerate(det_ids):
            card = self._create_image_card(det_id)
            row = index // 3
            col = index % 3
            self.image_grid.addWidget(card, row, col)

        self.image_grid.setColumnStretch(0, 1)
        self.image_grid.setColumnStretch(1, 1)
        self.image_grid.setColumnStretch(2, 1)
        self._update_toggle_all_button()

        # Reset scroll position to top-left
        vertical_scroll_bar = self.scroll_area.verticalScrollBar()
        if vertical_scroll_bar is not None:
            vertical_scroll_bar.setValue(0)

        horizontal_scroll_bar = self.scroll_area.horizontalScrollBar()
        if horizontal_scroll_bar is not None:
            horizontal_scroll_bar.setValue(0)

    def _clear_image_grid(self):
        """ Clear all widgets from the image grid layout."""

        for i in reversed(range(self.image_grid.count())):
            item = self.image_grid.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)

        return

    def _create_image_card(self, det_id):
        card = QWidget(self.image_container)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)

        # load img
        file_path, bbox = self.database.get_det_from_id(det_id)
        pixmap = QPixmap(str(file_path))
        if pixmap.isNull():
            pixmap = QPixmap(180, 140)
            pixmap.fill(Qt.GlobalColor.lightGray)

        # rotate img
        img_properties = self.database.get_entry_properties(str(file_path))
        orientation = img_properties.get('orientation', 'none')
        if orientation in ORIENTATION_LUT:
            transform = QTransform().rotate(ORIENTATION_LUT[orientation])
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # crop image to bbox
        x, y, x2, y2 = [int(a) for a in bbox]
        w, h = x2 - x, y2 - y
        pixmap = pixmap.copy(x, y, w, h)

        # create thumbnail
        thumb = QLabel(card)
        thumb.setPixmap(
            pixmap.scaled(
                180,
                140,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setFixedSize(180, 140)
        thumb.setStyleSheet("border: 1px solid #ccc; border-radius: 4px;")
        card_layout.addWidget(thumb)

        # create checkbox
        checkbox = QCheckBox(Path(file_path).name, card)
        checkbox.setChecked(True)
        checkbox.toggled.connect(lambda checked, p=det_id: self._handle_checkbox_toggle(p, checked))
        card_layout.addWidget(checkbox)
        self.current_checkboxes[str(det_id)] = checkbox

        self.selected_faces.add(str(det_id))

        return card

    def _handle_checkbox_toggle(self, file_path, checked):
        self._toggle_image_selection(file_path, checked)
        self._update_toggle_all_button()

    def _toggle_image_selection(self, file_path, checked):
        path = str(file_path)
        if checked:
            self.selected_faces.add(path)
        else:
            self.selected_faces.discard(path)

    def _toggle_all_checkboxes(self):
        if not self.current_checkboxes:
            return

        should_check = not all(checkbox.isChecked() for checkbox in self.current_checkboxes.values())
        for checkbox in self.current_checkboxes.values():
            checkbox.setChecked(should_check)

        self._update_toggle_all_button()

    def _update_toggle_all_button(self):
        if not hasattr(self, "toggle_all_button"):
            return

        if not self.current_checkboxes:
            self.toggle_all_button.setText("Marcar todas")
            return

        all_checked = all(checkbox.isChecked() for checkbox in self.current_checkboxes.values())
        self.toggle_all_button.setText("Desmarcar todas" if all_checked else "Marcar todas")

    def on_next_clicked(self):
        selected_count = len(self.selected_faces)
        label = self.name_input.text().strip()
        
        if selected_count == 0 or not label:
            reply = QMessageBox.question(
                        self,
                        "Continuar sin guardar identidad",
                        f"No se ha etiquetado ningún rostro. ¿Desea continuar?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
            if reply == QMessageBox.StandardButton.Yes:
                self.go_next()
            
            return

        for det_id in self.selected_faces:
            self.database.assign_identity(det_id, label)

        self.go_next()

    def go_next(self):
        self.selected_faces.clear()
        self.name_input.clear()
        self.cluster_index += 1
        self._display_detections(self.cluster_index)
