"""Search tool for chemistry compounds."""

import json
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from rapidfuzz import fuzz

from ...core.logging import setup_logging

logger = setup_logging(__name__)

# Load chemistry data once at module level
_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "chemistry_data.json"
_COMPOUNDS: list = []


def _load_data() -> list:
    """Load chemistry data lazily."""
    global _COMPOUNDS
    if not _COMPOUNDS:
        if _DATA_PATH.exists():
            with open(_DATA_PATH, "r", encoding="utf-8") as f:
                _COMPOUNDS = json.load(f)
            logger.info(f"Loaded {len(_COMPOUNDS)} compounds from {_DATA_PATH}")
        else:
            logger.warning(f"Data file not found: {_DATA_PATH}")
    return _COMPOUNDS


@tool
def search_compound(query: str) -> str:
    """Tìm kiếm thông tin hợp chất hóa học trong cơ sở dữ liệu.

    ĐÂY LÀ TOOL DUY NHẤT để tra cứu thông tin hóa học. Kết quả bao gồm
    tất cả thông tin về chất: tên, công thức, hình ảnh, audio phát âm.

    Args:
        query: Tên IUPAC, tên thông thường, công thức hóa học, hoặc ký hiệu
               Ví dụ: "ethanol", "hydrogen", "H2O", "CH4", "Na"

    Returns:
        JSON chứa đầy đủ thông tin:
        - doc_id: ID định danh (vd: "ethanol")
        - iupac_name: Tên IUPAC quốc tế (vd: "Ethanol")
        - formula: Công thức hóa học (vd: "C2H5OH")
        - type: Loại chất ("element" hoặc "compound")
        - image_path: URL hình ảnh cấu trúc (nếu có)
        - audio_path: Đường dẫn file audio phát âm (nếu có)

        Hoặc thông báo "Không tìm thấy" nếu không có kết quả.

    Example:
        search_compound("hydrogen") → {"doc_id": "hydrogen", "iupac_name": "Hydrogen", ...}
    """
    compounds = _load_data()
    if not compounds:
        return "Lỗi: Không thể tải dữ liệu hợp chất."

    query_lower = query.lower().strip()
    results = []

    for compound in compounds:
        iupac_name = compound.get("iupac_name", "").lower()
        formula = compound.get("formula", "").lower()
        molecular_formula = compound.get("molecular_formula", "").lower()
        common_names = [n.lower() for n in compound.get("common_names", [])]

        # Calculate similarity scores
        name_score = fuzz.token_sort_ratio(query_lower, iupac_name) / 100.0
        formula_score = max(
            fuzz.ratio(query_lower, formula) / 100.0,
            fuzz.ratio(query_lower, molecular_formula) / 100.0
        )
        # Check common names
        common_score = max(
            (fuzz.token_sort_ratio(query_lower, cn) / 100.0 for cn in common_names),
            default=0
        )

        max_score = max(name_score, formula_score, common_score)

        # Higher threshold (0.7) to avoid wrong matches
        if max_score >= 0.7:
            results.append({**compound, "score": round(max_score, 2)})

    if not results:
        return f"Không tìm thấy hợp chất phù hợp với '{query}'"

    # Sort by score and take top result
    results.sort(key=lambda x: x["score"], reverse=True)
    best_match = results[0]

    # Remove score from output
    best_match.pop("score", None)

    logger.info(f"Search '{query}' → found: {best_match.get('iupac_name')}")
    return json.dumps(best_match, ensure_ascii=False, indent=2)
