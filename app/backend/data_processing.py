import subprocess
import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Callable

import insightface
import torch
import clip
from PIL import Image

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

CLIP_SCENES = [
    "selfie", "group photo", "landscape", "concert",
    "drawing", "meme", "food", "pet", "sports event"
]


class GalleryManager:

    def __init__(self, root_path, db_path):
        # Init database
        self.root_path = Path(root_path)
        self.db_path = Path(db_path)
        self.db = DBManager(db_path=self.db_path)

        self.files = None

        # Init models (maybe do it in functions if too slow?)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Scene classification
        self.preprocess: Callable[[Image.Image], torch.Tensor]
        self.scene_features: torch.Tensor

        self.model, self.preprocess = clip.load("ViT-B/32", device=self.device)
        scene_tokens = clip.tokenize(CLIP_SCENES).to(self.device)
        self.scene_features = self.model.encode_text(scene_tokens)
        self.scene_features /= self.scene_features.norm(dim=-1, keepdim=True)

        # Face detection and recognition
        self.arcface = insightface.app.FaceAnalysis(name="buffalo_l")
        self.arcface.prepare(ctx_id=0, det_size=(640, 640))

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
            img = Image.open(file)
            scene_type = self.infer_scene(img)
            entry_id = self.db.add_entry(str(file.relative_to(self.root_path)), date, camera_model, scene_type)
            print(f"Entry added with ID: {entry_id}")

            # Detectar rostros y extraer embeddings
            bboxes, face_embeddings, confidences = self.detect_faces(img)

            self.db.add_face_detections(entry_id, embeddings_list=face_embeddings, bboxes=bboxes, confidences=confidences)


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

    def infer_scene(self, img: Image.Image):
        """
        Infer scene label using CLIP
        """
        img_tensor = self.preprocess(img)
        img_tensor  = img_tensor.unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(img_tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)
        
            # Compute similarity
            similarity = (image_features @ self.scene_features.T).squeeze(0)

        # Resultado
        best_idx = similarity.argmax().item()
        # TODO añadir umbral
        print(f"Selected scene: {CLIP_SCENES[best_idx]}")
        return CLIP_SCENES[best_idx]
    
    def detect_faces(self, img: Image.Image):
        bboxes, embeddings, confidences = [], [], []

        np_img_bgr = np.array(img)[:, :, ::-1]

        faces = self.arcface.get(np_img_bgr)

        for face in faces:
            if face.det_score < 0.7:
                continue

            # x1, y1, x2, y2 = face.bbox
    
            embeddings.append(face.embedding.tolist())
            bboxes.append(face.bbox)
            confidences.append(face.det_score)


        return bboxes, embeddings, confidences
