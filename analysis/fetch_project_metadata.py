"""
Fetch project metadata (start dates, methodology, status) from carbon registries.

Covers:
  - Verra VCS: REST API at registry.verra.org
  - ACCU (Australian): CER public register (web scrape / CSV)
  - ACR (American Carbon Registry): APX registry
  - CAR (Climate Action Reserve): APX registry

Outputs: data/registry_metadata/project_metadata.csv
"""

import csv
import json
import struct
import time
import re
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

ZENODO_DIR = Path(__file__).parent.parent / "data" / "zenodo"
OUT_DIR = Path(__file__).parent.parent / "data" / "registry_metadata"
OUT_DIR.mkdir(exist_ok=True)
OUT_FILE = OUT_DIR / "project_metadata.csv"

# ────────────────────────────────────────────────
# 1.  Read UIDs from shapefile .dbf
# ────────────────────────────────────────────────

def read_dbf_uids(dbf_path):
    with open(dbf_path, "rb") as f:
        data = f.read()

    num_records = struct.unpack("<I", data[4:8])[0]
    header_size = struct.unpack("<H", data[8:10])[0]
    record_size = struct.unpack("<H", data[10:12])[0]

    fields = []
    pos = 32
    while pos < header_size - 1:
        field = data[pos:pos + 32]
        if field[0] == 0x0D:
            break
        name = field[:11].decode("latin-1").rstrip("\x00")
        ftype = chr(field[11])
        length = field[16]
        fields.append((name, ftype, length))
        pos += 32

    rows = []
    for i in range(num_records):
        rstart = header_size + i * record_size
        record = data[rstart:rstart + record_size]
        row = {}
        offset = 1
        for name, ftype, length in fields:
            val = record[offset:offset + length].decode("latin-1", errors="replace").strip()
            row[name] = val
            offset += length
        rows.append(row)
    return rows


# ────────────────────────────────────────────────
# 2.  Verra API (VCS projects)
# ────────────────────────────────────────────────

VERRA_API = "https://registry.verra.org/uiapi/resource/resourceSummary/{id}?format=json"


def fetch_verra(project_id_str):
    """project_id_str: 'VCS1122' → numeric ID = '1122'"""
    num_id = project_id_str.replace("VCS", "").strip()
    url = VERRA_API.format(id=num_id)
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=15) as r:
            d = json.load(r)
    except (URLError, HTTPError, json.JSONDecodeError):
        return None

    result = {
        "uid": project_id_str,
        "registry": "VCS",
        "name": d.get("resourceName", ""),
        "country": "",
        "start_date": "",
        "methodology": "",
        "status": "",
    }

    for attr in d.get("attributes", []):
        code = attr.get("code", "")
        vals = attr.get("values", [])
        val = vals[0]["value"] if vals else ""
        if code == "GID_0" or code == "COUNTRY":
            result["country"] = val

    for ps in d.get("participationSummaries", []):
        if ps.get("programCode") != "VCS":
            continue
        for attr in ps.get("attributes", []):
            code = attr.get("code", "")
            vals = attr.get("values", [])
            val = vals[0]["value"] if vals else ""
            if code == "CREDIT_PERIOD_INFO":
                # Format: "1st, 22/05/2009 - 21/05/2047"
                m = re.search(r"(\d{2}/\d{2}/\d{4})", val)
                if m:
                    result["start_date"] = m.group(1)
            elif code == "METHODOLOGY":
                result["methodology"] = val
            elif code == "STATUS" or code == "REGISTRATION_STATUS":
                result["status"] = val
            elif code == "PROJECT_COUNTRY" or code == "COUNTRY":
                if not result["country"]:
                    result["country"] = val

    return result


# ────────────────────────────────────────────────
# 3.  ACR (American Carbon Registry) — APX API
# ────────────────────────────────────────────────

ACR_BASE = "https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111"


def fetch_acr(project_id_str):
    """project_id_str: 'ACR266'"""
    num_id = project_id_str.replace("ACR", "").strip()
    # APX doesn't have a clean JSON API; return stub
    return {
        "uid": project_id_str,
        "registry": "ACR",
        "name": "",
        "country": "",
        "start_date": "",
        "methodology": "",
        "status": "",
    }


# ────────────────────────────────────────────────
# 4.  CAR (Climate Action Reserve)
# ────────────────────────────────────────────────

def fetch_car(project_id_str):
    return {
        "uid": project_id_str,
        "registry": "CAR",
        "name": "",
        "country": "",
        "start_date": "",
        "methodology": "",
        "status": "",
    }


# ────────────────────────────────────────────────
# 5.  ACCU (Australian Carbon Credit Unit Scheme)
#     Public CSV at: https://cer.gov.au/markets/reports-and-data/accu-project-and-contract-register
# ────────────────────────────────────────────────

ACCU_CSV_URL = (
    "https://cer.gov.au/sites/default/files/2025-01/ACCU-project-and-contract-register.xlsx"
)

_accu_cache = {}

def load_accu_registry():
    """Download and cache ACCU project register."""
    if _accu_cache:
        return _accu_cache
    cache_file = OUT_DIR / "accu_register.json"
    if cache_file.exists():
        with open(cache_file) as f:
            _accu_cache.update(json.load(f))
        return _accu_cache

    # Try to get the ACCU project list via the CER website
    # The IDs in our dataset are like 'ACCUEOP100278' → ERF project ID 100278
    # CER API: https://cer.gov.au/sites/default/files/... (xlsx, not always stable)
    # Fallback: return empty and note manual download needed
    print("NOTE: ACCU registry not auto-downloaded. See: https://cer.gov.au/markets/reports-and-data/accu-project-and-contract-register")
    return {}


def fetch_accu(project_id_str):
    """project_id_str: 'ACCUEOP100278'"""
    load_accu_registry()
    num_id = project_id_str.replace("ACCUEOP", "").strip()
    cached = _accu_cache.get(num_id, {})
    return {
        "uid": project_id_str,
        "registry": "ACCU",
        "name": cached.get("name", ""),
        "country": "AUS",
        "start_date": cached.get("start_date", ""),
        "methodology": cached.get("methodology", ""),
        "status": cached.get("status", ""),
    }


# ────────────────────────────────────────────────
# 6.  Main
# ────────────────────────────────────────────────

def classify_uid(uid):
    if uid.startswith("VCS"):
        return "VCS"
    elif uid.startswith("ACCUEOP"):
        return "ACCU"
    elif uid.startswith("ACR"):
        return "ACR"
    elif uid.startswith("CAR") or uid.startswith("RE"):
        return "CAR"
    else:
        return "UNKNOWN"


def main():
    # Extract shapefile path
    import zipfile, tempfile, os

    dbf_path = None
    zip_path = ZENODO_DIR / "REDD.zip"
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.endswith(".dbf") and not n.startswith("__")]
        if names:
            tmpdir = Path(tempfile.mkdtemp())
            z.extract(names[0], tmpdir)
            dbf_path = tmpdir / names[0]

    rows = read_dbf_uids(dbf_path)
    unique_uids = {r["UID"]: r.get("GID_0", "") for r in rows if r.get("UID")}

    print(f"Found {len(unique_uids)} unique project UIDs")

    results = []
    vcs_uids = [u for u in unique_uids if classify_uid(u) == "VCS"]
    other_uids = [u for u in unique_uids if classify_uid(u) != "VCS"]

    # Fetch VCS (most of the dataset, ~112 projects) with rate limiting
    print(f"\nFetching {len(vcs_uids)} VCS projects from Verra API...")
    for i, uid in enumerate(sorted(vcs_uids)):
        if i % 10 == 0:
            print(f"  {i}/{len(vcs_uids)} — {uid}")
        rec = fetch_verra(uid)
        if rec:
            rec["gid0_shapefile"] = unique_uids.get(uid, "")
            results.append(rec)
        else:
            results.append({
                "uid": uid, "registry": "VCS",
                "name": "", "country": unique_uids.get(uid, ""),
                "start_date": "", "methodology": "", "status": "",
                "gid0_shapefile": unique_uids.get(uid, ""),
            })
        time.sleep(0.3)  # polite rate limiting

    # Other registries
    print(f"\nProcessing {len(other_uids)} non-VCS projects...")
    for uid in sorted(other_uids):
        reg = classify_uid(uid)
        if reg == "ACCU":
            rec = fetch_accu(uid)
        elif reg == "ACR":
            rec = fetch_acr(uid)
        elif reg == "CAR":
            rec = fetch_car(uid)
        else:
            rec = {"uid": uid, "registry": reg, "name": "", "country": "",
                   "start_date": "", "methodology": "", "status": ""}
        rec["gid0_shapefile"] = unique_uids.get(uid, "")
        results.append(rec)

    # Write CSV
    fieldnames = ["uid", "registry", "name", "country", "gid0_shapefile",
                  "start_date", "methodology", "status"]
    with open(OUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved {len(results)} records → {OUT_FILE}")
    have_dates = sum(1 for r in results if r.get("start_date"))
    print(f"Start dates found: {have_dates}/{len(results)}")


if __name__ == "__main__":
    main()
