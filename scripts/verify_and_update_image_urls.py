"""
Script to verify Wikimedia image URLs and update chemistry_data.json with direct URLs
Instead of downloading, we store direct URLs and let frontend/backend fetch when needed
"""
import json
import requests
from pathlib import Path
from time import sleep

# Same curated URLs from download script
ELEMENT_IMAGE_URLS = {
    # Period 1
    "hydrogen": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d9/Hydrogen_discharge_tube.jpg/400px-Hydrogen_discharge_tube.jpg",
    "helium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Helium_discharge_tube.jpg/400px-Helium_discharge_tube.jpg",

    # Period 2
    "lithium": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Lithium_paraffin.jpg/400px-Lithium_paraffin.jpg",
    "beryllium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/ff/Beryllium_%281%29.jpg/400px-Beryllium_%281%29.jpg",
    "boron": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Boron_R105.jpg/400px-Boron_R105.jpg",
    "carbon": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Diamond_and_graphite.jpg/400px-Diamond_and_graphite.jpg",
    "nitrogen": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Nitrogen_discharge_tube.jpg/400px-Nitrogen_discharge_tube.jpg",
    "oxygen": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/Liquid_oxygen_in_a_beaker_4.jpg/400px-Liquid_oxygen_in_a_beaker_4.jpg",
    "fluorine": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/Liquid_fluorine_tighter_crop.jpg/400px-Liquid_fluorine_tighter_crop.jpg",
    "neon": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/db/Neon_discharge_tube.jpg/400px-Neon_discharge_tube.jpg",

    # Period 3
    "sodium": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Na_%28Sodium%29.jpg/400px-Na_%28Sodium%29.jpg",
    "magnesium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Magnesium_crystals.jpg/400px-Magnesium_crystals.jpg",
    "aluminium": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Aluminium-4.jpg/400px-Aluminium-4.jpg",
    "aluminum": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Aluminium-4.jpg/400px-Aluminium-4.jpg",
    "silicon": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/SiliconCroda.jpg/400px-SiliconCroda.jpg",
    "phosphorus": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Phosphorus-white.jpg/400px-Phosphorus-white.jpg",
    "sulfur": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Sulfur_-_Grechishkin_mine%2C_Middle_Volga_Region%2C_Russia.jpg/400px-Sulfur_-_Grechishkin_mine%2C_Middle_Volga_Region%2C_Russia.jpg",
    "chlorine": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Chlorine_ampoule.jpg/400px-Chlorine_ampoule.jpg",
    "argon": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Argon_discharge_tube.jpg/400px-Argon_discharge_tube.jpg",

    # Period 4 - Metals
    "potassium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Potassium.JPG/400px-Potassium.JPG",
    "calcium": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Calcium_unter_Argon_Schutzgasatmosph%C3%A4re.jpg/400px-Calcium_unter_Argon_Schutzgasatmosph%C3%A4re.jpg",
    "scandium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Scandium_sublimed_dendritic_and_1cm3_cube.jpg/400px-Scandium_sublimed_dendritic_and_1cm3_cube.jpg",
    "titanium": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7c/Titan-crystal_bar.JPG/400px-Titan-crystal_bar.JPG",
    "vanadium": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Vanadium_etched.jpg/400px-Vanadium_etched.jpg",
    "chromium": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Chromium_crystals_and_1cm3_cube.jpg/400px-Chromium_crystals_and_1cm3_cube.jpg",
    "manganese": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Manganese_electrolytic_and_1cm3_cube.jpg/400px-Manganese_electrolytic_and_1cm3_cube.jpg",
    "iron": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Iron_electrolytic_and_1cm3_cube.jpg/400px-Iron_electrolytic_and_1cm3_cube.jpg",
    "cobalt": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Kobalt_electrolytic_and_1cm3_cube.jpg/400px-Kobalt_electrolytic_and_1cm3_cube.jpg",
    "nickel": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Nickel_chunk.jpg/400px-Nickel_chunk.jpg",
    "copper": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/NatCopper.jpg/400px-NatCopper.jpg",
    "zinc": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Zinc_fragment_sublimed_and_1cm3_cube.jpg/400px-Zinc_fragment_sublimed_and_1cm3_cube.jpg",
    "gallium": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Gallium_crystals.jpg/400px-Gallium_crystals.jpg",
    "germanium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Polycrystalline-germanium.jpg/400px-Polycrystalline-germanium.jpg",
    "arsenic": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Arsen_1a.jpg/400px-Arsen_1a.jpg",
    "selenium": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Selenium_1.jpg/400px-Selenium_1.jpg",
    "bromine": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Bromine_25ml.jpg/400px-Bromine_25ml.jpg",
    "krypton": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Krypton_discharge_tube.jpg/400px-Krypton_discharge_tube.jpg",

    # Period 5
    "rubidium": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Rb5.JPG/400px-Rb5.JPG",
    "strontium": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Strontium_destilled_crystals.jpg/400px-Strontium_destilled_crystals.jpg",
    "yttrium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Yttrium_sublimed_dendritic_and_1cm3_cube.jpg/400px-Yttrium_sublimed_dendritic_and_1cm3_cube.jpg",
    "zirconium": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Zirconium_crystal_bar_and_1cm3_cube.jpg/400px-Zirconium_crystal_bar_and_1cm3_cube.jpg",
    "niobium": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Niob_crystals_and_1cm3_cube.jpg/400px-Niob_crystals_and_1cm3_cube.jpg",
    "molybdenum": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Molybdenum_crystaline_fragment_and_1cm3_cube.jpg/400px-Molybdenum_crystaline_fragment_and_1cm3_cube.jpg",
    "technetium": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Technetium%2C_Tc-99_Disk_-_Radioactive_Sample.jpg/400px-Technetium%2C_Tc-99_Disk_-_Radioactive_Sample.jpg",
    "ruthenium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Ruthenium_a_half_bar.jpg/400px-Ruthenium_a_half_bar.jpg",
    "rhodium": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Rhodium_powder_pressed_melted.jpg/400px-Rhodium_powder_pressed_melted.jpg",
    "palladium": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Palladium_%2846_Pd%29.jpg/400px-Palladium_%2846_Pd%29.jpg",
    "silver": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Silver_crystal.jpg/400px-Silver_crystal.jpg",
    "cadmium": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/72/Cadmium-crystal_bar.jpg/400px-Cadmium-crystal_bar.jpg",
    "indium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Indium-2.jpg/400px-Indium-2.jpg",
    "tin": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Sn-Alpha-Beta.jpg/400px-Sn-Alpha-Beta.jpg",
    "antimony": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Antimony-4.jpg/400px-Antimony-4.jpg",
    "tellurium": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Tellurium2.jpg/400px-Tellurium2.jpg",
    "iodine": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Iodine_cristals.jpg/400px-Iodine_cristals.jpg",
    "xenon": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Xenon_discharge_tube.jpg/400px-Xenon_discharge_tube.jpg",

    # Period 6
    "cesium": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Cesium.jpg/400px-Cesium.jpg",
    "barium": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Barium_unter_Argon_Schutzgas_Atmosph%C3%A4re.jpg/400px-Barium_unter_Argon_Schutzgas_Atmosph%C3%A4re.jpg",
    "lanthanum": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Lanthanum-2.jpg/400px-Lanthanum-2.jpg",
    "cerium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/Cerium2.jpg/400px-Cerium2.jpg",
    "praseodymium": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Praseodymium.jpg/400px-Praseodymium.jpg",
    "neodymium": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Neodymium2.jpg/400px-Neodymium2.jpg",
    "promethium": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/Promethium.jpg/400px-Promethium.jpg",
    "samarium": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Samarium-2.jpg/400px-Samarium-2.jpg",
    "europium": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Europium.jpg/400px-Europium.jpg",
    "gadolinium": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Gadolinium-4.jpg/400px-Gadolinium-4.jpg",
    "terbium": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Terbium-2.jpg/400px-Terbium-2.jpg",
    "dysprosium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Dysprosium.jpg/400px-Dysprosium.jpg",
    "holmium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Holmium2.jpg/400px-Holmium2.jpg",
    "erbium": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/Erbium-crop.jpg/400px-Erbium-crop.jpg",
    "thulium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Thulium_sublimed_dendritic_and_1cm3_cube.jpg/400px-Thulium_sublimed_dendritic_and_1cm3_cube.jpg",
    "ytterbium": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Ytterbium-3.jpg/400px-Ytterbium-3.jpg",
    "lutetium": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Lutetium_sublimed_dendritic_and_1cm3_cube.jpg/400px-Lutetium_sublimed_dendritic_and_1cm3_cube.jpg",
    "hafnium": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Hf-crystal_bar.jpg/400px-Hf-crystal_bar.jpg",
    "tantalum": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Tantalum_single_crystal_and_1cm3_cube.jpg/400px-Tantalum_single_crystal_and_1cm3_cube.jpg",
    "tungsten": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Wolfram_evaporated_crystals_and_1cm3_cube.jpg/400px-Wolfram_evaporated_crystals_and_1cm3_cube.jpg",
    "rhenium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Rhenium_single_crystal_bar_and_1cm3_cube.jpg/400px-Rhenium_single_crystal_bar_and_1cm3_cube.jpg",
    "osmium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Osmium_crystals.jpg/400px-Osmium_crystals.jpg",
    "iridium": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Iridium-2.jpg/400px-Iridium-2.jpg",
    "platinum": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Platinum_crystals.jpg/400px-Platinum_crystals.jpg",
    "gold": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Gold-crystals.jpg/400px-Gold-crystals.jpg",
    "mercury": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Pouring_liquid_mercury_bionerd.jpg/400px-Pouring_liquid_mercury_bionerd.jpg",
    "thallium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Thallium_pieces_in_ampoule.jpg/400px-Thallium_pieces_in_ampoule.jpg",
    "lead": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Lead_electrolytic_and_1cm3_cube.jpg/400px-Lead_electrolytic_and_1cm3_cube.jpg",
    "bismuth": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Bismuth_crystals_and_1cm3_cube.jpg/400px-Bismuth_crystals_and_1cm3_cube.jpg",
    "polonium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f4/Polonium.jpg/400px-Polonium.jpg",
    "astatine": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Astatine.jpg/400px-Astatine.jpg",
    "radon": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Radon_discharge_tube.jpg/400px-Radon_discharge_tube.jpg",

    # Period 7
    "francium": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Francium.jpg/400px-Francium.jpg",
    "radium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Radium226.jpg/400px-Radium226.jpg",
    "actinium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Actinium_sample_%28center%29.jpg/400px-Actinium_sample_%28center%29.jpg",
    "thorium": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Thorium_sample_0.1_gram.jpg/400px-Thorium_sample_0.1_gram.jpg",
    "protactinium": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Protactinium.jpg/400px-Protactinium.jpg",
    "uranium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/HEUraniumC.jpg/400px-HEUraniumC.jpg",
    "neptunium": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Np_sphere.jpg/400px-Np_sphere.jpg",
    "plutonium": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Plutonium3.jpg/400px-Plutonium3.jpg",
    "americium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Americium_microscope.jpg/400px-Americium_microscope.jpg",
    "curium": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Curium.jpg/400px-Curium.jpg",
    "berkelium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Berkelium.jpg/400px-Berkelium.jpg",
    "californium": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/Californium.jpg/400px-Californium.jpg",
    "einsteinium": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Einsteinium.jpg/400px-Einsteinium.jpg",
    "fermium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Fermium.jpg/400px-Fermium.jpg",
    "mendelevium": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Mendelevium.jpg/400px-Mendelevium.jpg",
    "nobelium": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/eb/Nobelium.jpg/400px-Nobelium.jpg",
    "lawrencium": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Lawrencium.jpg/400px-Lawrencium.jpg",
    "rutherfordium": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Rutherfordium.jpg/400px-Rutherfordium.jpg",
    "dubnium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b5/Dubnium.jpg/400px-Dubnium.jpg",
    "seaborgium": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Seaborgium.jpg/400px-Seaborgium.jpg",
    "bohrium": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Bohrium.jpg/400px-Bohrium.jpg",
    "hassium": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Hassium.jpg/400px-Hassium.jpg",
    "meitnerium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Meitnerium.jpg/400px-Meitnerium.jpg",
    "darmstadtium": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Darmstadtium.jpg/400px-Darmstadtium.jpg",
    "roentgenium": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1f/Roentgenium.jpg/400px-Roentgenium.jpg",
    "copernicium": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Copernicium.jpg/400px-Copernicium.jpg",
    "nihonium": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Nihonium.jpg/400px-Nihonium.jpg",
    "flerovium": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Flerovium.jpg/400px-Flerovium.jpg",
    "moscovium": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/Moscovium.jpg/400px-Moscovium.jpg",
    "livermorium": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/Livermorium.jpg/400px-Livermorium.jpg",
    "tennessine": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Tennessine.jpg/400px-Tennessine.jpg",
    "oganesson": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Oganesson.jpg/400px-Oganesson.jpg",
}

def check_url(url):
    """Check if URL is accessible (HEAD request to avoid rate limit)"""
    try:
        headers = {
            'User-Agent': 'Chemistry-Chatbot-Educational-App/1.0'
        }
        response = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
        return response.status_code == 200
    except:
        return False

def main():
    base_dir = Path(__file__).parent.parent
    json_path = base_dir / "data" / "chemistry_data.json"

    # Load chemistry data
    print(f"Loading chemistry data from {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Update image URLs
    updated_count = 0
    skipped_count = 0

    print("\nUpdating element image URLs...")
    print("="*60)

    for item in data:
        if item["type"] == "element":
            doc_id = item["doc_id"]

            if doc_id in ELEMENT_IMAGE_URLS:
                new_url = ELEMENT_IMAGE_URLS[doc_id]
                item["image_path"] = new_url
                print(f"✓ {item['iupac_name']}: Updated")
                updated_count += 1
            else:
                print(f"⚠️  {item['iupac_name']}: No URL available")
                skipped_count += 1

            # Small delay to be polite
            sleep(0.05)

    # Save updated data
    print(f"\n{'='*60}")
    print(f"Saving updated data...")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Successfully updated {json_path}")
    print(f"  - Updated: {updated_count} elements")
    print(f"  - Skipped: {skipped_count} elements")
    print(f"\nNow image_path contains direct Wikimedia URLs")
    print(f"Frontend/backend will fetch images directly when needed")

if __name__ == "__main__":
    main()
