import subprocess
import json
from datetime import datetime
from pathlib import Path

from app.database.database_manager import DBManager

IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"}
DATE_FIELDS = [
    "DateTimeOriginal",
    "CreateDate",
    "ModifyDate",
    "MetadataDate",
    "FileCreationDateTime",
    "FileModificationDateTime",
    "FileAccessDateTime",
]
CAMERA_FIELDS = ["Model", "CameraModelName", "Make"]


class GalleryManager:

    def __init__(self, root_path, db_path):
        self.root_path = Path(root_path)
        self.db_path = Path(db_path)
        self.db = DBManager(db_path=self.db_path)

        self.files = None

    def read_images(self):
        files = [file for file in self.root_path.rglob("*")]
        files_extensions = set([file.suffix.lower() for file in files])
        if unknown_extensions:=files_extensions - IMG_EXTENSIONS:
            raise ValueError(f"Unkown extensions found: {unknown_extensions}")
        
        self.files = [file for file in files if file.suffix.lower() in IMG_EXTENSIONS]

    def process_images(self):
        if self.files is None:
            raise ValueError("No images read. Call read_images() first.")

        for file in self.files:
            print(f"Adding image: {file}")
            date, camera_model = self.extract_metadata(file)
            scene_type = "Unknown"  # Placeholder, can be updated later
            entry_id = self.db.add_entry(str(file), date, camera_model, scene_type)
            print(f"Entry added with ID: {entry_id}")

            # Detectar rostros y extraer embeddings
            face_embeddings, confidences = self.detect_faces(file)

            self.db.add_face_detections(entry_id, embeddings_list=face_embeddings, confidences=[])


    def extract_metadata(self, path):
        """
        Obtain the oldest date and camera model from the image metadata using exiftool.
        If missing, return default values.
        """

        # Run exiftool
        result = subprocess.run(
            ["exiftool.exe", "-json", path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        data = json.loads(result.stdout)[0]

        if not data or len(data) == 0:
            return "Unknown", "Unknown"

        # Extaract older date
        dates = []

        for field in DATE_FIELDS:
            if field in data:
                try:
                    # Normalizar formato EXIF: YYYY:MM:DD HH:MM:SS
                    d = data[field].replace(":", "-", 2)
                    dates.append(datetime.fromisoformat(d))
                except Exception as e:
                    print(f"Error while parsing date from field {field} ({data[field]}): {e}")

        if dates:
            oldest_date = min(dates)
        else:
            oldest_date = "Unknown"


        # Extract camera model
        camera_model = "Unknown"
        for field in CAMERA_FIELDS:
            if field in data:
                camera_model = data[field]
                break

        return oldest_date, camera_model

    
    def detect_faces(self, file: Path):
        embeddings, confidences = [], []

        # TODO

        return embeddings, confidences

    def extract_embeddings(self):
        # Extraer embeddings de los rostros detectados
        pass
