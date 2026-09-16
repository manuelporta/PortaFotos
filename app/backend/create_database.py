from pathlib import Path
import argparse

from app.backend.data_processing import GalleryManager


def parse_args():
    """Parse and validate CLI arguments.

    Returns:
        argparse.Namespace with attribute `root_path` as a `pathlib.Path`.
    """

    def valid_root_path(path_str: str) -> Path:
        p = Path(path_str)
        if not p.exists():
            raise argparse.ArgumentTypeError(f"La ruta '{path_str}' no existe")
        if not p.is_dir():
            raise argparse.ArgumentTypeError(f"La ruta '{path_str}' no es una carpeta")
        return p

    parser = argparse.ArgumentParser(description="Procesar una carpeta de imágenes")
    parser.add_argument(
        "root_path",
        type=valid_root_path,
        help="Ruta a la carpeta raíz que contiene las imágenes",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    db_path = args.root_path / "portafotos.db"
    gallery = GalleryManager(args.root_path, db_path)
    gallery.create()