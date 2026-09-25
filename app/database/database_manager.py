from pathlib import Path
from typing import Any, Dict, List, Tuple

from sqlalchemy import Column, create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database_definitions import Base, Entry, FaceDetection, Identity

class DBManager:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
        self.engine = None
        self.Session = None
        self.session = None

        if self.db_path and self.db_path.exists():
            self.load_database()
        else:
            self.create_database()

    # --------------------------------------------------------
    # CREAR BASE DE DATOS
    # --------------------------------------------------------
    def create_database(self):
        if self.db_path is None:
            print("db_path no especificado.Creando base de datos en memoria (temporal)")
            self.engine = create_engine("sqlite:///:memory:")
        else:
            self.engine = create_engine(f"sqlite:///{self.db_path}")

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def load_database(self):
        if self.db_path is None:
            raise ValueError("db_path no especificado")

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def close(self):
        """Cierra la sesión y libera el motor de la base de datos."""
        if self.session is not None:
            self.session.close()
            self.session = None

        if self.engine is not None:
            self.engine.dispose()
            self.engine = None

        self.Session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # --------------------------------------------------------
    # AÑADIR ENTRADA (IMAGEN)
    # --------------------------------------------------------
    def add_entry(self, path, date, camera_model, orientation, scene_type):
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        entry = Entry(path=path, date=date, camera_model=camera_model, orientation=orientation, scene_type=scene_type)
        self.session.add(entry)
        self.session.commit()
        return entry.id

    # --------------------------------------------------------
    # AÑADIR DETECCIONES FACIALES
    # --------------------------------------------------------
    def add_face_detections(self, entry_id, embeddings_list, bboxes, confidences):
        """
        embeddings_list: lista de vectores de embedding
                        ej: [[v1, v2, ...], [v1, v2, ...], ...]
        """

        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        entry = self.session.query(Entry).filter_by(id=entry_id).first()
        if entry is None:
            raise ValueError("Entry no existe")

        base_index = len(entry.detections)

        for i, embedding in enumerate(embeddings_list):

            det = FaceDetection(
                entry_id=entry_id,
                index=base_index + i,
                embedding=embedding,
                bbox = bboxes[i],
                confidence=confidences[i]
            )

            self.session.add(det)

        self.session.commit()



    # --------------------------------------------------------
    # ASIGNAR IDENTIDAD A UNA DETECCIÓN
    # --------------------------------------------------------
    def assign_identity(self, detection_id, identity_id):
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        det = self.session.query(FaceDetection).filter_by(id=detection_id).first()
        if det is None:
            raise ValueError("Detección no existe")

        det.identity_id = identity_id
        self.session.commit()

    # --------------------------------------------------------
    # CREAR IDENTIDAD GLOBAL
    # --------------------------------------------------------
    def create_identity(self, name, cluster_id, mean_embedding, notes=None):
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")
        
        ident = Identity(name=name, cluster_id=cluster_id, mean_embedding=mean_embedding, notes=notes)
        self.session.add(ident)
        self.session.commit()
        return ident.id

    # --------------------------------------------------------
    # EXTRAER TODOS LOS EMBEDDINGS PARA CLUSTERING
    # --------------------------------------------------------
    def get_all_embeddings(self) -> List[Tuple[int, List[float], str]]:
        """
        Devuelve una lista de tuplas:
        [
            (detection_id, embedding_vector, identity_id),
            ...
        ]

        donde embedding_vector es la lista completa almacenada en JSON.
        """
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        detections = self.session.query(FaceDetection).all()

        embeddings = [
            (det.id, det.embedding, det.identity_id)
            for det in detections
        ]

        return embeddings # type: ignore


    # --------------------------------------------------------
    # BUSCAR ENTRADAS
    # --------------------------------------------------------
    def search_entries(self, **filters):
        # TODO not used yet, but can be used to filter by date, camera_model, scene_type, etc.

        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        query = self.session.query(Entry)

        if "scene_type" in filters:
            query = query.filter(Entry.scene_type == filters["scene_type"])

        if "date" in filters:
            query = query.filter(Entry.date == filters["date"])

        return query.all()

    def get_all_paths(self) -> List[str]:
        """
        Return all image paths in database
        """
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        return [str(entry.path) for entry in self.session.query(Entry).all()]

    def get_entry_properties(self, path: str) -> Dict[str, Any]:
        """
        Return the properties of an entry given its path
        """
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        entry = self.session.query(Entry).filter_by(path=path).first()
        if entry is None:
            raise ValueError("Entry no existe")

        return {
            "date": str(entry.date),
            "camera_model": str(entry.camera_model),
            "scene_type": entry.scene_type if isinstance(entry.scene_type, list) else str(entry.scene_type),
            "orientation": str(entry.orientation)
        }

    def get_face_detections_by_path(self, path: str):
        """
        Return the face detections associated with an entry given its path.
        TODO: not used yet
        """
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        entry = self.session.query(Entry).filter_by(path=path).first()
        if entry is None:
            raise ValueError("Entry no existe")

        return [
            {
                "id": det.id,
                "index": det.index,
                "bbox": det.bbox,
                "confidence": det.confidence,
                "identity_id": det.identity_id,
                "embedding": det.embedding,
            }
            for det in entry.detections
        ]

    def get_dets(self, path: str) -> List[Tuple[List[float], str]]:
        """
        Return the bounding boxes of an entry given its path
        """

        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        entry = self.session.query(Entry).filter_by(path=path).first()
        if entry is None:
            raise ValueError("Entry no existe")

        return [(det.bbox, det.identity_id) for det in entry.detections]

    def get_det_from_id(self, detection_id: int) -> Tuple[str, List[float]]:
        """
        Return the file path and bounding box of a detection given its ID
        """
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        det = self.session.query(FaceDetection).filter_by(id=detection_id).first()
        if det is None:
            raise ValueError("Detección no existe")

        entry = self.session.query(Entry).filter_by(id=det.entry_id).first()
        if entry is None:
            raise ValueError("Entry no existe")

        if isinstance(det.bbox, list):
            return str(entry.path), det.bbox
        else:
            raise ValueError("Bounding box no es una lista válida")


