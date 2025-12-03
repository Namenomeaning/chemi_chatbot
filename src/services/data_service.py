"""TinyDB-based data service for chemistry compounds."""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from tinydb import TinyDB, Query
from dotenv import load_dotenv

from ..core.logging import setup_logging

load_dotenv()
logger = setup_logging(__name__)


class DataService:
    """Handles loading and retrieving compound data using TinyDB."""

    def __init__(self, db_path: str = "data/chemistry.json"):
        # Use relative paths from project root (not absolute)
        self.data_dir = Path(os.getenv("DATA_DIR", "data"))
        self.images_prefix = os.getenv("IMAGES_DIR", "data/images")
        self.audio_prefix = os.getenv("AUDIO_DIR", "data/audio")

        self.db = TinyDB(db_path, sort_keys=True, indent=2)
        self.compounds = self.db.table('compounds')

        if len(self.compounds) == 0:
            self._load_compounds_from_files()

    def _load_compounds_from_files(self):
        """Load all compounds from data/compounds.json file into TinyDB."""
        compounds_file = self.data_dir / "compounds.json"
        if not compounds_file.exists():
            return

        try:
            with open(compounds_file, "r", encoding="utf-8") as f:
                compounds_data = json.load(f)

            # Update paths to be relative from project root (data/images/..., data/audio/...)
            for compound in compounds_data:
                if "image_path" in compound:
                    # Convert "images/file.png" to "data/images/file.png"
                    filename = Path(compound["image_path"]).name
                    compound["image_path"] = f"{self.images_prefix}/{filename}"
                if "audio_path" in compound:
                    # Convert "audio/file.wav" to "data/audio/file.wav"
                    filename = Path(compound["audio_path"]).name
                    compound["audio_path"] = f"{self.audio_prefix}/{filename}"

            if compounds_data:
                self.compounds.insert_multiple(compounds_data)
                logger.info(f"TinyDB loaded {len(compounds_data)} compounds from {compounds_file}")
        except Exception as e:
            logger.error(f"TinyDB load error - file: {compounds_file}, error: {str(e)}")

    def get_all_compounds(self) -> List[Dict[str, Any]]:
        """Get all compounds."""
        return self.compounds.all()

    def get_compound_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get compound by doc_id."""
        Compound = Query()
        return self.compounds.get(Compound.doc_id == doc_id)


# Singleton instance
_data_service = None


def get_data_service() -> DataService:
    """Get or create the singleton data service instance."""
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service
