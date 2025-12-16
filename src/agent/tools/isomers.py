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

    # Get formula and canonical SMILES
    formula = rdMolDescriptors.CalcMolFormula(Chem.AddHs(mol))
    canonical_smiles = Chem.MolToSmiles(mol, canonical=True)

    # Make SMILES filename-safe: = → e, / → f, \ → b, ( → o, ) → c, @ → a, # → t
    safe_smiles = (canonical_smiles
        .replace('=', 'e').replace('/', 'f').replace('\\', 'b')
        .replace('(', 'o').replace(')', 'c').replace('@', 'a').replace('#', 't'))

    # Unique filename: formula + safe_smiles
    filename = f"{formula.lower()}_{safe_smiles}.png"
    s3_key = f"isomers/{filename}"
    s3_url = f"{_S3_BASE_URL}/{s3_key}"

    # Check if already exists in S3 (cache hit)
    if _s3_file_exists(s3_key):
        logger.info(f"S3 cache hit: {s3_url}")
        # Still need to enumerate isomers for the response data
        opts = StereoEnumerationOptions(tryEmbedding=True, unique=True, maxIsomers=16)
        isomers = []
        for iso_mol in EnumerateStereoisomers(mol, options=opts):
            iso_smiles = Chem.MolToSmiles(iso_mol, isomericSmiles=True)
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

        return json.dumps({
            "formula": formula,
            "total": len(isomers),
            "isomers": isomers,
            "image_path": s3_url,
        }, ensure_ascii=False, indent=2)

    # Cache miss - generate image
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

    # Generate grid image and upload to S3
    image_path = None
    if mols:
        filepath = _IMAGE_DIR / filename

        img = Draw.MolsToGridImage(
            mols,
            molsPerRow=min(len(mols), 4),
            subImgSize=(300, 300),
            legends=legends,
            returnPNG=False,
        )
        img.save(str(filepath))
        logger.info(f"Generated isomer image: {filepath}")

        # Upload to S3
        image_path = _upload_to_s3(filepath, s3_key) or f"isomers/{filename}"

    result = {
        "formula": formula,
        "total": len(isomers),
        "isomers": isomers,
        "image_path": image_path,
    }

    logger.info(f"SMILES '{smiles}' → {len(isomers)} isomers")
    return json.dumps(result, ensure_ascii=False, indent=2)
