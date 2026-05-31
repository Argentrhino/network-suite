import csv
from pathlib import Path

OUI_DB = {}

def load_oui_database():
    csv_path = Path(__file__).parent / "data" / "oui.csv"

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            raw = row.get("Assignment", "").strip().upper()
            if len(raw) != 6:
                continue

            # Convert "286FB9" → "28:6F:B9"
            oui = ":".join([raw[i:i+2] for i in range(0, 6, 2)])

            vendor = row.get("Organization Name", "").strip()
            if not vendor:
                vendor = "Unknown"

            OUI_DB[oui] = vendor

    print("Loaded OUI entries:", len(OUI_DB))


def lookup_vendor(mac: str) -> str:
    if not mac or mac == "-":
        return "-"

    mac = mac.upper().replace("-", ":")
    oui = mac[:8]

    return OUI_DB.get(oui, "Unknown")
