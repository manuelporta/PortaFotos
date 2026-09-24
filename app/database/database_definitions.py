from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import JSON

from datetime import datetime

Base = declarative_base()


# ============================================================
# MODELOS
# ============================================================

class Entry(Base):
    __tablename__ = "entries"

    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.now)
    orientation = Column(String, default='Unknown')
    camera_model = Column(String, default='Unknown')
    scene_type = Column(JSON, default=list, nullable=True)  # lista ordenada de cadenas

    detections = relationship("FaceDetection", cascade="all, delete-orphan")


class Identity(Base):
    __tablename__ = "identities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # se asigna tras clustering
    cluster_id = Column(Integer, nullable=True)
    mean_embedding = Column(JSON, nullable=True)  # vector medio del cluster
    notes = Column(String, nullable=True)

    detections = relationship("FaceDetection", back_populates="identity")


class FaceDetection(Base):
    __tablename__ = "face_detections"

    id = Column(Integer, primary_key=True)
    entry_id = Column(Integer, ForeignKey("entries.id"))
    index = Column(Integer)  # posición en la lista de detecciones

    # Embedding almacenado JSON
    embedding = Column(JSON)

    # Bounding box opcional almacenada como JSON: {"x1":.., "y1":.., "x2":.., "y2":..}
    bbox = Column(JSON)

    # Confianza opcional
    confidence = Column(Float, nullable=True)

    # Identidad global (opcional)
    identity_id = Column(String, ForeignKey("identities.id"), nullable=True)

    entry = relationship("Entry", back_populates="detections")
    identity = relationship("Identity", back_populates="detections")
