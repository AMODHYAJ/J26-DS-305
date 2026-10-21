
from pathlib import Path
import zipfile

raw = Path(__file__).resolve().parent / "data" / "raw"
zip_path = raw / "NCRE_Control_History.zip"

if not zip_path.exists():
    print("Control ZIP not found:", zip_path)
else:
    with zipfile.ZipFile(zip_path) as archive:
        files = [
            name for name in archive.namelist()
            if name.lower().endswith((".xlsx", ".xls"))
        ]

    print("Excel files inside original ZIP:", len(files))
    print("\nFirst 20 files:")
    for name in files[:20]:
        print(name)
