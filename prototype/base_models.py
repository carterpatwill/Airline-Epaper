#!/usr/bin/env python3
"""
Map an ICAO aircraft type designator (e.g. 'B738', 'A320') to a base model.

Scope: 14 base models -- commercial aircraft, business/private jets, plus
piston/light, seaplanes, and vintage prop airliners (one per silhouette image
in plane-images/). Military and helicopters are still out of scope and resolve
to "Unknown".

The tracker's adsbdb lookup returns a compact ICAO type code per aircraft
(tracker.py -> lookup_type). This module turns that code into one of the
base "silhouette" categories so a logo can be stacked on the right base.

Usage:
    from base_models import base_model_for
    base_model_for("B738")   # -> "Classic narrow-body"
    base_model_for("E55P")   # -> "Business jet"
    base_model_for("R44")    # -> "Unknown"  (helicopter, out of scope)
"""

# ICAO type designator -> base model.
# Codes are the ICAO doc-8643 designators adsbdb returns (uppercase).
ICAO_TO_BASE = {
    # ---- 1. Classic narrow-body (single-aisle) ----------------------------
    # The most common shape overhead: 737 / A320 families + 757/717/MD-80.
    "B731": "Classic narrow-body", "B732": "Classic narrow-body",
    "B733": "Classic narrow-body", "B734": "Classic narrow-body",
    "B735": "Classic narrow-body", "B736": "Classic narrow-body",
    "B737": "Classic narrow-body", "B738": "Classic narrow-body",
    "B739": "Classic narrow-body",
    "B37M": "Classic narrow-body", "B38M": "Classic narrow-body",
    "B39M": "Classic narrow-body", "B3XM": "Classic narrow-body",
    "A318": "Classic narrow-body", "A319": "Classic narrow-body",
    "A320": "Classic narrow-body", "A321": "Classic narrow-body",
    "A19N": "Classic narrow-body", "A20N": "Classic narrow-body",
    "A21N": "Classic narrow-body",
    "B752": "Classic narrow-body", "B753": "Classic narrow-body",
    "B712": "Classic narrow-body",  # 717
    "MD81": "Classic narrow-body", "MD82": "Classic narrow-body",
    "MD83": "Classic narrow-body", "MD87": "Classic narrow-body",
    "MD88": "Classic narrow-body", "MD90": "Classic narrow-body",

    # ---- 2. Small narrow-body / large regional ----------------------------
    "BCS1": "Small narrow-body", "BCS3": "Small narrow-body",  # A220-100/300
    "A221": "Small narrow-body", "A223": "Small narrow-body",
    "E290": "Small narrow-body", "E295": "Small narrow-body",  # E190-E2/E195-E2

    # ---- 3. Regional jet --------------------------------------------------
    "E170": "Regional jet", "E75L": "Regional jet", "E75S": "Regional jet",
    "E175": "Regional jet", "E190": "Regional jet", "E195": "Regional jet",
    "E135": "Regional jet", "E35L": "Regional jet",  # ERJ135 / Legacy 600/650
    "E145": "Regional jet", "E45X": "Regional jet",
    "CRJ1": "Regional jet", "CRJ2": "Regional jet", "CRJ7": "Regional jet",
    "CRJ9": "Regional jet", "CRJX": "Regional jet",
    "SU95": "Regional jet",  # Sukhoi Superjet 100

    # ---- 4. Turboprop -----------------------------------------------------
    # Commercial/regional turboprops.
    "AT43": "Turboprop", "AT45": "Turboprop", "AT72": "Turboprop",
    "AT75": "Turboprop", "AT76": "Turboprop",
    "DH8A": "Turboprop", "DH8B": "Turboprop", "DH8C": "Turboprop",
    "DH8D": "Turboprop",  # Dash 8 / Q400
    "SF34": "Turboprop", "SB20": "Turboprop",
    "B190": "Turboprop",  # Beech 1900
    "F50": "Turboprop", "DHC6": "Turboprop", "JS41": "Turboprop",
    "SW4": "Turboprop", "C208": "Turboprop",  # Metroliner / Caravan (regional freight)

    # ---- 5. Twin-aisle wide-body ------------------------------------------
    "B762": "Twin-aisle wide-body", "B763": "Twin-aisle wide-body",
    "B764": "Twin-aisle wide-body",
    "B772": "Twin-aisle wide-body", "B773": "Twin-aisle wide-body",
    "B77L": "Twin-aisle wide-body", "B77W": "Twin-aisle wide-body",
    "B778": "Twin-aisle wide-body", "B779": "Twin-aisle wide-body",  # 777X
    "B788": "Twin-aisle wide-body", "B789": "Twin-aisle wide-body",
    "B78X": "Twin-aisle wide-body",  # 787-10
    "A332": "Twin-aisle wide-body", "A333": "Twin-aisle wide-body",
    "A338": "Twin-aisle wide-body", "A339": "Twin-aisle wide-body",  # A330neo
    "A359": "Twin-aisle wide-body", "A35K": "Twin-aisle wide-body",

    # ---- 6. Four-engine wide-body -----------------------------------------
    "A342": "Four-engine wide-body", "A343": "Four-engine wide-body",
    "A345": "Four-engine wide-body", "A346": "Four-engine wide-body",

    # ---- 7. Tri-jet -------------------------------------------------------
    # Mostly cargo now (MD-11F with FedEx/UPS/Lufthansa Cargo).
    "DC10": "Tri-jet", "MD11": "Tri-jet",
    "B722": "Tri-jet",  # 727 (rare)

    # ---- 8. Jumbo (hump) --------------------------------------------------
    # Still common as freighters (747-8F, 747-400F).
    "B741": "Jumbo (hump)", "B742": "Jumbo (hump)", "B743": "Jumbo (hump)",
    "B744": "Jumbo (hump)", "B748": "Jumbo (hump)", "B74S": "Jumbo (hump)",
    "B74R": "Jumbo (hump)", "B74F": "Jumbo (hump)",

    # ---- 9. Double-deck ---------------------------------------------------
    "A388": "Double-deck",

    # ---- 10. Business jet -------------------------------------------------
    # Heavy coverage: this is a top category near GA/reliever airports.
    # Cessna Citation
    "C500": "Business jet", "C501": "Business jet", "C510": "Business jet",
    "C525": "Business jet", "C25A": "Business jet", "C25B": "Business jet",
    "C25C": "Business jet", "C550": "Business jet", "C551": "Business jet",
    "C560": "Business jet", "C56X": "Business jet", "C650": "Business jet",
    "C680": "Business jet", "C68A": "Business jet", "C700": "Business jet",
    "C750": "Business jet",
    # Embraer executive
    "E50P": "Business jet", "E55P": "Business jet",  # Phenom 100 / 300
    "E545": "Business jet", "E550": "Business jet",  # Praetor 500 / 600
    # Gulfstream
    "GLF2": "Business jet", "GLF3": "Business jet", "GLF4": "Business jet",
    "GLF5": "Business jet", "GLF6": "Business jet", "GALX": "Business jet",
    "G280": "Business jet",
    # Bombardier Learjet / Challenger / Global
    "LJ31": "Business jet", "LJ35": "Business jet", "LJ40": "Business jet",
    "LJ45": "Business jet", "LJ60": "Business jet", "LJ70": "Business jet",
    "LJ75": "Business jet",
    "CL30": "Business jet", "CL35": "Business jet", "CL60": "Business jet",
    "GL5T": "Business jet", "GL7T": "Business jet", "GLEX": "Business jet",
    # Dassault Falcon
    "FA10": "Business jet", "FA20": "Business jet", "FA50": "Business jet",
    "F2TH": "Business jet", "FA7X": "Business jet", "FA8X": "Business jet",
    "F900": "Business jet",
    # Hawker / Beechjet
    "H25A": "Business jet", "H25B": "Business jet", "H25C": "Business jet",
    "HA4T": "Business jet", "BE40": "Business jet",
    # Others increasingly common
    "PC24": "Business jet",  # Pilatus PC-24
    "HDJT": "Business jet",  # HondaJet
    "SF50": "Business jet",  # Cirrus Vision Jet

    # ---- 11. Cargo / freighter --------------------------------------------
    # Most freighters share a code with the passenger version and get
    # classified by silhouette above. Dedicated outsized freighters here.
    "A124": "Cargo / freighter",  # Antonov An-124
    "A225": "Cargo / freighter",  # Antonov An-225
    "B77F": "Cargo / freighter",  # some feeds tag the 777F this way

    # ---- 12. Piston / light aircraft --------------------------------------
    # Small single/twin private planes. Common near GA fields.
    "C152": "Piston / light", "C172": "Piston / light",
    "C182": "Piston / light", "C206": "Piston / light", "C210": "Piston / light",
    "P28A": "Piston / light", "P28B": "Piston / light",
    "PA28": "Piston / light", "PA32": "Piston / light", "PA44": "Piston / light",
    "BE33": "Piston / light", "BE35": "Piston / light", "BE36": "Piston / light",
    "BE58": "Piston / light", "BE20": "Piston / light",  # King Air (turboprop)
    "SR20": "Piston / light", "SR22": "Piston / light",
    "DA40": "Piston / light", "DA42": "Piston / light", "M20P": "Piston / light",

    # ---- 13. Seaplane / floatplane ----------------------------------------
    "DHC2": "Seaplane / floatplane",  # Beaver
    "DHC3": "Seaplane / floatplane",  # Otter
    "CNGT": "Seaplane / floatplane",  # (feed-specific tags)
    "A5": "Seaplane / floatplane",    # ICON A5

    # ---- 14. Prop airliner / vintage --------------------------------------
    "DC3": "Prop airliner / vintage", "DC6": "Prop airliner / vintage",
    "CVLT": "Prop airliner / vintage", "CVLP": "Prop airliner / vintage",
    "L188": "Prop airliner / vintage",  # Lockheed Electra

    # ---- 15. Helicopter ---------------------------------------------------
    # Common civil/EMS/news/police rotorcraft.
    "R22": "Helicopter", "R44": "Helicopter", "R66": "Helicopter",
    "EN28": "Helicopter",  # Enstrom 280
    "B06": "Helicopter", "B06T": "Helicopter", "B407": "Helicopter",
    "B412": "Helicopter", "B427": "Helicopter", "B429": "Helicopter",
    "B430": "Helicopter", "B47G": "Helicopter", "B505": "Helicopter",
    "A109": "Helicopter", "A119": "Helicopter", "A139": "Helicopter",
    "A169": "Helicopter", "A189": "Helicopter",
    "EC20": "Helicopter", "EC25": "Helicopter", "EC30": "Helicopter",
    "EC35": "Helicopter", "EC45": "Helicopter", "EC55": "Helicopter",
    "EC75": "Helicopter", "H160": "Helicopter",
    "AS50": "Helicopter", "AS55": "Helicopter", "AS65": "Helicopter",
    "AS32": "Helicopter", "AS3B": "Helicopter", "GAZL": "Helicopter",
    "MD50": "Helicopter", "MD52": "Helicopter", "MD60": "Helicopter",
    "H500": "Helicopter", "H50": "Helicopter",
    "S76": "Helicopter", "S92": "Helicopter", "S61": "Helicopter",
    "S64": "Helicopter", "S330": "Helicopter",
    "BK17": "Helicopter", "NH90": "Helicopter", "PUMA": "Helicopter",
    "UH1": "Helicopter", "H60": "Helicopter", "H64": "Helicopter",
    "LYNX": "Helicopter", "W3": "Helicopter", "EXPL": "Helicopter",
}


# Base model name -> silhouette file in plane-images/. One image per model.
BASE_IMAGE = {
    "Classic narrow-body":     "ClassicNarrowBody.png",
    "Small narrow-body":       "SmallNarrowBody.png",
    "Regional jet":            "RegionalJet.png",
    "Turboprop":               "TurboProp.png",
    "Twin-aisle wide-body":    "TwinEngine.png",
    "Four-engine wide-body":   "4engineWidebody.png",
    "Tri-jet":                 "TriJet.png",
    "Jumbo (hump)":            "Jumbo.png",
    "Double-deck":             "DoubleDecker.png",
    "Business jet":            "BussniessJet.png",
    "Cargo / freighter":       "Cargo.png",
    "Piston / light":          "Piston.png",
    "Seaplane / floatplane":   "Waterplane.png",
    "Prop airliner / vintage": "Propariliner.png",
    "Helicopter":              "Helicopter.png",
}


def image_for(base_model):
    """Return the silhouette filename for a base model, or '' if none."""
    return BASE_IMAGE.get(base_model, "")


def base_model_for(icao_type):
    """Return the base model for an ICAO type code, or 'Unknown' if unmapped.

    Case-insensitive; strips surrounding whitespace. Empty / missing input
    returns 'Unknown' rather than raising, so it's safe to call on every
    plane whether or not adsbdb has resolved its type yet. Out-of-scope
    aircraft (piston, helicopter, military, glider) also return 'Unknown'.
    """
    code = (icao_type or "").strip().upper()
    return ICAO_TO_BASE.get(code, "Unknown")


if __name__ == "__main__":
    # Quick self-check / demo.
    samples = ["B738", "A20N", "B38M", "BCS3", "E175", "CRJ9", "AT72",
               "B77W", "B789", "A359", "A343", "MD11", "B744", "A388",
               "C56X", "E55P", "CL60", "GLF6",
               "C172", "R44", "F16", "ZZZZ"]  # last four are out of scope
    width = max(len(s) for s in samples)
    for code in samples:
        print(f"{code:<{width}}  ->  {base_model_for(code)}")
