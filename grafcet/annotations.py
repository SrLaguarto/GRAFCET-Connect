"""Notas visuales independientes del GRAFCET, almacenadas en la presentación."""
import copy
import math
from fractions import Fraction


def visual_notes(presentation):
    out = []
    for note in presentation.get("notes", []):
        if not isinstance(note, dict) or note.get("kind") not in ("text", "image") or not isinstance(note.get("id"), str):
            continue
        try:
            n = copy.deepcopy(note)
            for key in ("x", "y", "width", "height"):
                n[key] = float(Fraction(str(n[key])))
                if not math.isfinite(n[key]):raise ValueError()
            if n["width"] <= 0 or n["height"] <= 0:continue
            if n["kind"] == "text":
                n["size"] = float(Fraction(str(n.get("size", 18))))
                if not math.isfinite(n["size"]) or n["size"] <= 0:continue
                if not all(isinstance(n.get(k, ""), str) for k in ("text", "font", "color")):continue
            elif not isinstance(n.get("data"), str) or not n["data"].startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
                continue
            out.append(n)
        except (KeyError, ValueError, TypeError, OverflowError, ZeroDivisionError):
            continue
    return out
