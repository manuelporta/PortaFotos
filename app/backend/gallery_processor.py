from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtCore import QThread


class GalleryProcessingWorker(QObject):
    """Runs a gallery import job in a background thread and emits progress updates."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, gallery):
        super().__init__()
        self.gallery = gallery

    def run(self):
        try:
            self.gallery.process_images(on_progress=self._emit_progress)
            self.finished.emit(self.gallery)
        except Exception as exc:  # pragma: no cover - errors are surfaced to the UI
            self.error.emit(str(exc))

    def _emit_progress(self, current: int, total: int, file_name: str) -> None:
        self.progress.emit(current, total, file_name)

class GalleryProcessor:
    """Handles the processing of a gallery in a background thread."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.gallery = main_window.gallery
        self.progress_bar = main_window._progress_bar
        self.thread = None
        self.worker = None

    def process(self):
        """Start the gallery processing in a background thread."""

        if self.gallery is None or self.gallery.files is None:
            return

        total = len(self.gallery.files)
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(0)

        self.thread = QThread()
        self.thread.setObjectName("ImageProcessingThread")
        self.worker = GalleryProcessingWorker(self.gallery)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.error.connect(self.thread.quit)

        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def _on_progress(self, current: int, total: int, file_name: str) -> None:
        """Handle progress updates from the worker."""
        if self.progress_bar:
            if total <= 0:
                total = 1
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(current)
            
        self.main_window.log_status(f"Processing {file_name} ({current}/{total})")

    def _on_finished(self) -> None:
        """Handle completion of the gallery processing."""
        if self.progress_bar:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)

        self.main_window.log_status(f"Procesado completado. Nuevo portafotos creado en {self.gallery.db_path}.")
        if self.gallery:
            self.main_window.database = self.gallery.db
            self.main_window._init_layout()


    def _on_error(self, error_message: str) -> None:
        """Handle errors from the worker."""
        if self.progress_bar:
            self.progress_bar.setVisible(False)
            self.progress_bar.setValue(0)

        self.main_window.log_status(f"Error during gallery processing: {error_message}")


