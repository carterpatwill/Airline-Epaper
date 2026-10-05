#!/usr/bin/env python3
"""
Build the on-device (flash) aircraft data from the OpenSky metadata CSV.

Outputs (all consumed by the firmware, NO SD card required):
  firmware/data/acdb.bin           sorted binary: icao24 -> typecode + registration
  firmware/src/generated/gen_aircraft_types.h typecode -> friendly model name + silhouette id
  firmware/src/generated/gen_airlines.h       callsign ICAO prefix -> airline name

acdb.bin layout (little-endian), binary-searched on-device:
  header 16 B: magic 'ACDB', u32 version, u32 count, u32 recsize(=24)
  records (count), each 24 B, SORTED ascending by icao24:
      u32   icao24            (parsed from the 6-hex string)
      char  typecode[8]       null-padded, truncated
      char  registration[12]  null-padded, truncated

Run from the repo root:
    python3 tools/build_ac_db.py
"""
import csv, os, struct, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV  = os.path.join(ROOT, "data", "aircraft-database-complete-2025-08.csv")
BIN  = os.path.join(ROOT, "firmware", "data", "acdb.bin")
HTYPES = os.path.join(ROOT, "firmware", "src", "generated", "gen_aircraft_types.h")
HAIR   = os.path.join(ROOT, "firmware", "src", "generated", "gen_airlines.h")

TC_LEN, REG_LEN, RECSIZE = 8, 12, 24

# Pull the curated typecode -> base-model map + base list from the prototype.
sys.path.insert(0, os.path.join(ROOT, "prototype"))
from base_models import ICAO_TO_BASE, BASE_IMAGE  # noqa: E402

# Stable id per base model (index into a firmware silhouette table). 0 = Unknown.
BASE_ORDER = list(BASE_IMAGE.keys())
BASE_ID = {name: i + 1 for i, name in enumerate(BASE_ORDER)}   # 1..14
BASE_ENUM = {name: "BASE_" + "".join(c for c in name.upper()
             if c.isalnum() or c == " ").replace(" ", "_") for name in BASE_ORDER}

# Clean display names for the most common commercial typecodes. Falls back to
# the CSV's own model string for anything not listed here.
CURATED = {
    "B737": "Boeing 737-700", "B738": "Boeing 737-800", "B739": "Boeing 737-900",
    "B38M": "Boeing 737 MAX 8", "B39M": "Boeing 737 MAX 9", "B37M": "Boeing 737 MAX 7",
    "B752": "Boeing 757-200", "B753": "Boeing 757-300", "B712": "Boeing 717",
    "B763": "Boeing 767-300", "B764": "Boeing 767-400",
    "B772": "Boeing 777-200", "B77W": "Boeing 777-300ER", "B77L": "Boeing 777-200LR",
    "B788": "Boeing 787-8", "B789": "Boeing 787-9", "B78X": "Boeing 787-10",
    "B744": "Boeing 747-400", "B748": "Boeing 747-8",
    "A319": "Airbus A319", "A320": "Airbus A320", "A321": "Airbus A321",
    "A19N": "Airbus A319neo", "A20N": "Airbus A320neo", "A21N": "Airbus A321neo",
    "A332": "Airbus A330-200", "A333": "Airbus A330-300", "A339": "Airbus A330-900neo",
    "A359": "Airbus A350-900", "A35K": "Airbus A350-1000", "A388": "Airbus A380",
    "BCS1": "Airbus A220-100", "BCS3": "Airbus A220-300",
    "E75L": "Embraer 175", "E75S": "Embraer 175", "E170": "Embraer 170",
    "E190": "Embraer 190", "E195": "Embraer 195",
    "CRJ2": "Bombardier CRJ200", "CRJ7": "Bombardier CRJ700", "CRJ9": "Bombardier CRJ900",
    "DH8D": "Dash 8 Q400", "AT72": "ATR 72", "AT76": "ATR 72-600",
    "C172": "Cessna 172", "C182": "Cessna 182", "SR22": "Cirrus SR22",
    "PC12": "Pilatus PC-12", "C208": "Cessna Caravan",
    "GLF6": "Gulfstream G650", "GLF5": "Gulfstream G550", "GLEX": "Bombardier Global",
    "C56X": "Cessna Citation Excel", "C68A": "Cessna Citation Latitude",
    "E55P": "Embraer Phenom 300", "CL60": "Bombardier Challenger 600",
    "MD11": "McDonnell Douglas MD-11", "DC10": "McDonnell Douglas DC-10",
}


def clean(s):
    return (s or "").strip()


def main():
    if not os.path.exists(CSV):
        sys.exit(f"CSV not found: {CSV}")

    records = []                         # (icao24_int, typecode, registration)
    model_counts = collections.defaultdict(collections.Counter)   # tc -> model text
    tc_counts = collections.Counter()                              # tc -> #aircraft
    airline = collections.defaultdict(collections.Counter)        # icao -> owner name

    with open(CSV, newline="") as f:
        r = csv.reader(f, quotechar="'")
        header = next(r)
        idx = {c.strip().strip("'"): i for i, c in enumerate(header)}
        I = lambda row, name: clean(row[idx[name]]) if idx.get(name) is not None else ""
        for row in r:
            if len(row) < len(header):
                continue
            ic = I(row, "icao24")
            try:
                icv = int(ic, 16)
            except ValueError:
                continue
            tc = I(row, "typecode")[:TC_LEN]
            reg = I(row, "registration")
            if reg == "-UNKNOWN-":
                reg = ""
            reg = reg[:REG_LEN]
            if not tc and not reg:
                continue                 # nothing worth storing
            records.append((icv, tc, reg))

            if tc:
                tc_counts[tc] += 1
                m = I(row, "model")
                if m:
                    model_counts[tc][m] += 1
            # airline: ICAO operator code -> best owner/operator name
            oi = I(row, "operatorIcao")
            if oi and len(oi) == 3 and oi.isalpha():
                name = I(row, "operator") or I(row, "owner")
                if name:
                    airline[oi.upper()][name] += 1

    records.sort(key=lambda t: t[0])
    write_bin(records)
    write_types(tc_counts, model_counts)
    write_airlines(airline)


def write_bin(records):
    with open(BIN, "wb") as f:
        f.write(b"ACDB")
        f.write(struct.pack("<III", 1, len(records), RECSIZE))
        for icv, tc, reg in records:
            f.write(struct.pack("<I", icv))
            f.write(tc.encode("ascii", "ignore").ljust(TC_LEN, b"\0")[:TC_LEN])
            f.write(reg.encode("ascii", "ignore").ljust(REG_LEN, b"\0")[:REG_LEN])
    size = os.path.getsize(BIN)
    print(f"acdb.bin : {len(records):,} records, {size/1e6:.1f} MB")


def name_for(tc, model_counts):
    if tc in CURATED:
        return CURATED[tc]
    if model_counts.get(tc):
        return model_counts[tc].most_common(1)[0][0]
    return tc


def write_types(tc_counts, model_counts):
    # Every typecode that is either curated, mapped to a silhouette, or seen a
    # meaningful number of times. Keeps the table small but complete for reality.
    keep = set(CURATED) | set(ICAO_TO_BASE)
    keep |= {tc for tc, n in tc_counts.items() if n >= 20}
    rows = sorted(keep)
    with open(HTYPES, "w") as f:
        f.write("// AUTO-GENERATED by tools/build_ac_db.py -- do not edit.\n")
        f.write("// typecode -> friendly model name + silhouette base id.\n#pragma once\n\n")
        f.write("enum AcBase : uint8_t {\n  BASE_UNKNOWN = 0,\n")
        for name in BASE_ORDER:
            f.write(f"  {BASE_ENUM[name]} = {BASE_ID[name]},\n")
        f.write("};\n\n")
        f.write("struct AcType { const char* code; const char* name; uint8_t base; };\n")
        f.write("// Sorted by code for binary search.\n")
        f.write(f"static const AcType AC_TYPES[] = {{\n")
        for tc in rows:
            base = BASE_ID.get(ICAO_TO_BASE.get(tc, ""), 0)
            nm = name_for(tc, model_counts).replace('"', "'")
            f.write(f'  {{"{tc}", "{nm}", {base}}},\n')
        f.write("};\n")
        f.write(f"static const size_t AC_TYPES_N = {len(rows)};\n\n")
        f.write("// base id -> silhouette label (art file in plane-images/).\n")
        f.write("static const char* AC_BASE_LABEL[] = {\n  \"Unknown\",\n")
        for name in BASE_ORDER:
            f.write(f'  "{name}",\n')
        f.write("};\n")
    print(f"gen_aircraft_types.h : {len(rows)} typecodes")


# Curated major carriers guarantee clean names for common US/intl flights even
# if the CSV aggregation is thin. Merged over the CSV-derived table.
CURATED_AIRLINES = {
    "UAL": "United Airlines", "AAL": "American Airlines", "DAL": "Delta Air Lines",
    "SWA": "Southwest Airlines", "ASA": "Alaska Airlines", "JBU": "JetBlue",
    "NKS": "Spirit Airlines", "FFT": "Frontier Airlines", "HAL": "Hawaiian Airlines",
    "SKW": "SkyWest", "ENY": "Envoy Air", "RPA": "Republic Airways",
    "EDV": "Endeavor Air", "AAY": "Allegiant Air", "FDX": "FedEx",
    "UPS": "UPS Airlines", "ACA": "Air Canada", "AMX": "Aeromexico",
    "BAW": "British Airways", "DLH": "Lufthansa", "AFR": "Air France",
    "KLM": "KLM", "UAE": "Emirates", "QTR": "Qatar Airways", "ANA": "All Nippon",
    "JAL": "Japan Airlines", "SIA": "Singapore Airlines", "CPA": "Cathay Pacific",
    "VOI": "Volaris", "WJA": "WestJet", " QXE": "Horizon Air",
}


def write_airlines(airline):
    table = {}
    for icao, names in airline.items():
        table[icao] = names.most_common(1)[0][0]
    for k, v in CURATED_AIRLINES.items():
        table[k.strip()] = v                 # curated wins
    rows = sorted(table.items())
    with open(HAIR, "w") as f:
        f.write("// AUTO-GENERATED by tools/build_ac_db.py -- do not edit.\n")
        f.write("// 3-letter ICAO callsign prefix -> airline name.\n#pragma once\n\n")
        f.write("struct Airline { const char* code; const char* name; };\n")
        f.write("// Sorted by code for binary search.\n")
        f.write("static const Airline AIRLINES[] = {\n")
        for code, name in rows:
            nm = name.replace('"', "'")
            f.write(f'  {{"{code}", "{nm}"}},\n')
        f.write("};\n")
        f.write(f"static const size_t AIRLINES_N = {len(rows)};\n")
    print(f"gen_airlines.h : {len(rows)} airlines")
    for c in ("UAL", "AAL", "SWA", "DAL", "SKW", "ASA"):
        print(f"    {c} -> {table.get(c, '(MISSING)')}")


if __name__ == "__main__":
    main()
