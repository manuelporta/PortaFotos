from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.database.database_manager import DBManager




class SceneEditWindow(QDialog):
    def __init__(self, database: DBManager, path: str, parent=None):
        super().__init__(parent)
        self.database = database    
        self.path = path

        self.setWindowTitle("Editar escenas")
        self.resize(1100, 700)
        self.setModal(True)

        self._load_scenes()
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.selection_label = QLabel("Ordena las escenas según su exactitud.\n 'default' marca la última escena aceptada.")
        header.addWidget(self.selection_label)
        header.addStretch()
        main_layout.addLayout(header)

        if not self.scene_values:
            self.selection_label.setText("No hay escenas detectadas para editar.")
            return

        self.scene_list = QListWidget(self)
        self.scene_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.scene_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.scene_list.setDropIndicatorShown(True)
        for scene_value in self.scene_values:
            item = QListWidgetItem(str(scene_value[0]))
            item.setData(Qt.ItemDataRole.UserRole, scene_value)
            self.scene_list.addItem(item)
        main_layout.addWidget(self.scene_list)

        main_layout.addStretch()
        confirm_row = QHBoxLayout()
        confirm_row.addStretch()
        self.confirm_button = QPushButton("Guardar", self)
        self.confirm_button.clicked.connect(self._save_edit)
        confirm_row.addWidget(self.confirm_button)
        main_layout.addLayout(confirm_row)

    def _save_edit(self):

        new_scene_values = []
        score = 1
        for index in range(self.scene_list.count()):
            item = self.scene_list.item(index)
            if item is None:
                QMessageBox.warning(self, "Error", f"Error al guardar la escena en la posición {index}.")
                continue
            scene_value = item.data(Qt.ItemDataRole.UserRole)

            if scene_value == 'default':
                if index > 0:
                    score = 0.1
                else:
                    new_scene_values.append((scene_value, score))
                    score = 0.1
                    continue
            
            new_scene_values.append((scene_value[0], score))
            if score > 0.5:
                score -= 0.05


        self.database.update_scene_types(self.path, new_scene_values)


        QMessageBox.information(self, "Éxito", "Escenas guardadas correctamente.")
        self.accept()

    def _load_scenes(self):

        self.scene_values = self.database.get_scene_types(self.path)
