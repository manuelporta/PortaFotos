from pathlib import Path
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database_dependencies import Base, Entry, FaceDetection, Identity

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

    # --------------------------------------------------------
    # AÑADIR ENTRADA (IMAGEN)
    # --------------------------------------------------------
    def add_entry(self, path, date, camera_model, scene_type):
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        entry = Entry(path=path, date=date, camera_model=camera_model, scene_type=scene_type)
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
    def get_all_embeddings(self):
        """
        Devuelve una lista de tuplas:
        [
            (detection_id, embedding_vector),
            ...
        ]

        donde embedding_vector es la lista completa almacenada en JSON.
        """
        if not self.session:
            raise ValueError("Sesión no inicializada. Llama a create_database() o load_database() primero.")

        detections = self.session.query(FaceDetection).all()

        embeddings = [
            (det.id, det.embedding)
            for det in detections
        ]

        return embeddings


    # --------------------------------------------------------
    # BUSCAR ENTRADAS
    # --------------------------------------------------------
    def search_entries(self, **filters):

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

