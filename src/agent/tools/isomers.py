"""Isomer generation tool using RDKit."""

import hashlib
import json
from pathlib import Path

from langchain_core.tools import tool
from rdkit import Chem
from rdkit.Chem import AllChem, Draw, rdMolDescriptors
from rdkit.Chem.EnumerateStereoisomers import (
    EnumerateStereoisomers,
    StereoEnumerationOptions,
)

from ...core.logging import setup_logging

logger = setup_logging(__name__)

_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "isomers"
_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


@tool
def generate_isomers(smiles: str) -> str:
    """Tạo danh sách đồng phân lập thể và ảnh cấu trúc từ SMILES.

    Args:
        smiles: Cấu trúc SMILES của hợp chất (VD: "CC=CC", "CC(O)CC")

    Returns:
        JSON chứa danh sách đồng phân với SMILES, loại lập thể và image_path

    Example:
        generate_isomers("CC=CC") → E/Z isomers của but-2-ene + ảnh grid
    """
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return json.dumps({"error": f"SMILES không hợp lệ: '{smiles}'"}, ensure_ascii=False)

    # Get formula
    formula = rdMolDescriptors.CalcMolFormula(Chem.AddHs(mol))

    # Enumerate stereoisomers
    opts = StereoEnumerationOptions(tryEmbedding=True, unique=True, maxIsomers=16)
    isomers = []
    mols = []
    legends = []

    for iso_mol in EnumerateStereoisomers(mol, options=opts):
        iso_smiles = Chem.MolToSmiles(iso_mol, isomericSmiles=True)

        # Determine stereo type
        chiral = Chem.FindMolChiralCenters(iso_mol, includeUnassigned=False)
        stereo_info = []
        if chiral:
            stereo_info.append(f"chiral: {chiral}")
        for bond in iso_mol.GetBonds():
            if bond.GetBondType() == Chem.BondType.DOUBLE:
                s = bond.GetStereo()
                if s in {Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ}:
                    stereo_info.append(s.name)

        stereo_type = ", ".join(stereo_info) or "unspecified"
        isomers.append({"smiles": iso_smiles, "stereo_type": stereo_type})

        AllChem.Compute2DCoords(iso_mol)
        mols.append(iso_mol)
        legends.append(stereo_type)

    # Generate grid image
    image_path = None
    if mols:
        content_hash = hashlib.md5(smiles.encode()).hexdigest()[:8]
        filename = f"{formula}_{content_hash}.png"
        filepath = _IMAGE_DIR / filename

        img = Draw.MolsToGridImage(
            mols,
            molsPerRow=min(len(mols), 4),
            subImgSize=(300, 300),
            legends=legends,
            returnPNG=False,
        )
        img.save(str(filepath))
        image_path = f"isomers/{filename}"
        logger.info(f"Generated isomer image: {filepath}")

    result = {
        "formula": formula,
        "total": len(isomers),
        "isomers": isomers,
        "image_path": image_path,
    }

    logger.info(f"SMILES '{smiles}' → {len(isomers)} isomers")
    return json.dumps(result, ensure_ascii=False, indent=2)
