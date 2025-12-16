"""Isomer generation tool using RDKit."""

import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
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

# S3 configuration
_S3_BUCKET = os.getenv("S3_BUCKET", "chemistry-chatbot-assets")
_S3_REGION = os.getenv("S3_REGION", "ap-southeast-1")
_S3_BASE_URL = os.getenv("S3_BASE_URL", f"https://{_S3_BUCKET}.s3.{_S3_REGION}.amazonaws.com")


def _s3_file_exists(s3_key: str) -> bool:
    """Check if file exists in S3."""
    try:
        s3_client = boto3.client("s3", region_name=_S3_REGION)
        s3_client.head_object(Bucket=_S3_BUCKET, Key=s3_key)
        return True
    except ClientError:
        return False


def _upload_to_s3(filepath: Path, s3_key: str) -> str | None:
    """Upload file to S3 and return public URL."""
    try:
        s3_client = boto3.client("s3", region_name=_S3_REGION)
        s3_client.upload_file(
            str(filepath),
            _S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": "image/png"}
        )
        url = f"{_S3_BASE_URL}/{s3_key}"
        logger.info(f"Uploaded to S3: {url}")
        return url
    except ClientError as e:
        logger.warning(f"S3 upload failed: {e}")
        return None


def _make_safe_smiles(smiles: str) -> str:
    """Convert SMILES to filename-safe string."""
    return (smiles
        .replace('=', 'e').replace('/', 'f').replace('\\', 'b')
        .replace('(', 'o').replace(')', 'c').replace('@', 'a').replace('#', 't'))


def _get_stereo_info(mol) -> str:
    """Get stereo type string for a molecule."""
    stereo_info = []
    chiral = Chem.FindMolChiralCenters(mol, includeUnassigned=False)
    if chiral:
        stereo_info.append(f"chiral: {chiral}")
    for bond in mol.GetBonds():
        if bond.GetBondType() == Chem.BondType.DOUBLE:
            s = bond.GetStereo()
            if s in {Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOZ}:
                stereo_info.append(s.name)
    return ", ".join(stereo_info) or "unspecified"


@tool
def generate_isomers(smiles_list: list[str], formula: str = None) -> str:
    """Tạo ảnh grid chứa tất cả đồng phân từ danh sách SMILES.

    Args:
        smiles_list: Danh sách SMILES (VD: ["CCCC", "CC(C)C"] cho C4H10)
        formula: CTPT để validate (VD: "C4H10"). Nếu có, SMILES sai CTPT sẽ bị lọc.

    Returns:
        JSON chứa danh sách compounds với đồng phân lập thể và image_path

    Example:
        generate_isomers(["CCCC", "CC(C)C"], formula="C4H10") → ảnh grid n-butane + isobutane
        generate_isomers(["CCCO", "CC(O)C", "COCC"], formula="C3H8O") → ảnh grid 3 đồng phân
    """
    if not smiles_list:
        return json.dumps({"error": "Danh sách SMILES rỗng"}, ensure_ascii=False)

    # Validate SMILES and filter by formula if provided
    valid_smiles = []
    filtered_out = []

    for smiles in smiles_list:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            filtered_out.append({"smiles": smiles, "reason": "SMILES không hợp lệ"})
            continue

        mol_formula = rdMolDescriptors.CalcMolFormula(Chem.AddHs(mol))

        # Validate against expected formula if provided
        if formula and mol_formula != formula:
            filtered_out.append({
                "smiles": smiles,
                "reason": f"CTPT sai: {mol_formula} (expected {formula})"
            })
            continue

        valid_smiles.append(smiles)

    if not valid_smiles:
        return json.dumps({
            "error": "Không có SMILES hợp lệ sau khi validate",
            "filtered_out": filtered_out
        }, ensure_ascii=False, indent=2)

    # Canonicalize valid SMILES
    canonical_list = []
    for smiles in valid_smiles:
        mol = Chem.MolFromSmiles(smiles)
        canonical_list.append(Chem.MolToSmiles(mol, canonical=True))

    # Sort for consistent cache key, join safe SMILES
    canonical_list.sort()
    safe_names = [_make_safe_smiles(s) for s in canonical_list]
    filename = f"isomers_{'_'.join(safe_names)}.png"
    s3_key = f"isomers/{filename}"
    s3_url = f"{_S3_BASE_URL}/{s3_key}"

    # Process all valid molecules
    all_compounds = []
    all_mols = []
    all_legends = []
    opts = StereoEnumerationOptions(tryEmbedding=True, unique=True, maxIsomers=16)

    for smiles in valid_smiles:
        mol = Chem.MolFromSmiles(smiles)
        mol_formula = rdMolDescriptors.CalcMolFormula(Chem.AddHs(mol))
        canonical = Chem.MolToSmiles(mol, canonical=True)

        isomers = []
        for iso_mol in EnumerateStereoisomers(mol, options=opts):
            iso_smiles = Chem.MolToSmiles(iso_mol, isomericSmiles=True)
            stereo_type = _get_stereo_info(iso_mol)
            isomers.append({"smiles": iso_smiles, "stereo_type": stereo_type})

            AllChem.Compute2DCoords(iso_mol)
            all_mols.append(iso_mol)
            # Only show stereo type if specified (E/Z, R/S)
            if stereo_type != "unspecified":
                all_legends.append(f"{canonical}\n({stereo_type})")
            else:
                all_legends.append(canonical)

        all_compounds.append({
            "input_smiles": smiles,
            "canonical_smiles": canonical,
            "formula": mol_formula,
            "stereoisomers": isomers,
        })

    # Check S3 cache
    if _s3_file_exists(s3_key):
        logger.info(f"S3 cache hit: {s3_url}")
        result = {
            "total_compounds": len(all_compounds),
            "total_stereoisomers": len(all_mols),
            "compounds": all_compounds,
            "image_path": s3_url,
        }
        if filtered_out:
            result["filtered_out"] = filtered_out
        return json.dumps(result, ensure_ascii=False, indent=2)

    # Generate grid image
    image_path = None
    if all_mols:
        filepath = _IMAGE_DIR / filename
        img = Draw.MolsToGridImage(
            all_mols,
            molsPerRow=min(len(all_mols), 4),
            subImgSize=(300, 300),
            legends=all_legends,
            returnPNG=False,
        )
        img.save(str(filepath))
        logger.info(f"Generated isomer image: {filepath}")
        image_path = _upload_to_s3(filepath, s3_key) or f"isomers/{filename}"

    result = {
        "total_compounds": len(all_compounds),
        "total_stereoisomers": len(all_mols),
        "compounds": all_compounds,
        "image_path": image_path,
    }
    if filtered_out:
        result["filtered_out"] = filtered_out

    logger.info(f"Generated grid for {len(valid_smiles)} compounds → {len(all_mols)} stereoisomers")
    return json.dumps(result, ensure_ascii=False, indent=2)
