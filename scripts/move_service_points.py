#!/usr/bin/env python3
"""Move all top-level `srv_consumir_spN` service points of Comedor.alp into the
`<Presentation>` of a given ServiceWithArea (default `srv_consumir2`) so they
become its children.

The operation is a pure text move: element boundaries are computed from the lxml
parse (sourceline + serialized subtree line count), then the raw line ranges are
cut from their top-level location and pasted, in order, before the target
service's `</Presentation>` tag.

No line is added or removed (only relocated), and the result is re-validated as
XML before the file is written.
"""

import re
import shutil
import sys
from pathlib import Path

from lxml import etree

ALP = Path(__file__).resolve().parent.parent / "Comedor.alp"
NAME_RE = re.compile(r"^srv_consumir_sp\d+$")
DEFAULT_TARGET = "srv_consumir2"


def end_line(el: etree._Element) -> int:
    """1-based line of el's closing tag (closing tag sits on its own line).

    etree.tostring() includes the element's tail text, so its trailing
    newlines must be subtracted to get the position of the closing tag.
    """
    tail_newlines = (el.tail or "").count("\n")
    return el.sourceline + etree.tostring(el).count(b"\n") - tail_newlines


def find_service(root: etree._Element, tag: str, name: str) -> etree._Element:
    for el in root.iter(tag):
        if el.findtext("Name") == name:
            return el
    raise SystemExit(f"ERROR: <{tag}> named '{name}' not found")


def main(argv: list[str] | None = None) -> int:
    target = argv[1] if argv and len(argv) > 1 else DEFAULT_TARGET

    text = ALP.read_text(encoding="utf-8")
    original_lines = text.splitlines(keepends=True)

    backup = ALP.with_name(ALP.stem + ".alp.bak")
    shutil.copyfile(ALP, backup)
    print(f"Backup written to {backup}")

    root = etree.fromstring(text.encode("utf-8"))

    svc = find_service(root, "ServiceWithArea", target)
    pres = svc.find("Presentation")
    if pres is None:
        raise SystemExit(f"ERROR: '{target}' has no <Presentation> child")

    pres_end = end_line(pres)
    assert original_lines[pres_end - 1].strip() == "</Presentation>", (
        f"unexpected line at insertion point: {original_lines[pres_end - 1]!r}"
    )

    existing_in_target = 0
    blocks = []  # (start_line, end_line, raw_text)
    for sp in root.iter("ServicePoint"):
        if sp.findtext("Name") is None or not NAME_RE.match(sp.findtext("Name")):
            continue
        if svc in sp.iterancestors():
            existing_in_target += 1
            continue
        if any(a.tag == "ServiceWithArea" for a in sp.iterancestors()):
            continue  # already a child of another service
        start = sp.sourceline
        end = end_line(sp)
        assert original_lines[end - 1].strip() == "</ServicePoint>", (
            f"unexpected block end at line {end}: {original_lines[end - 1]!r}"
        )
        assert start > pres_end, f"block at line {start} is above insertion point"
        blocks.append((start, end, "".join(original_lines[start - 1:end])))

    blocks.sort()
    print(f"Moved {len(blocks)} service points into '{target}'")

    # Remove blocks (reverse order so line numbers stay valid)…
    new_lines = original_lines[:]
    for start, end, _ in reversed(blocks):
        del new_lines[start - 1:end]

    # …then insert them, in original order, before the target's </Presentation>.
    idx = pres_end - 1
    assert new_lines[idx].strip() == "</Presentation>"
    new_lines[idx:idx] = [block for _, _, block in blocks]

    new_text = "".join(new_lines)
    assert new_text.count("\n") == text.count("\n"), "newline count changed"

    # Re-validate and re-assert the invariants.
    root2 = etree.fromstring(new_text.encode("utf-8"))
    svc2 = find_service(root2, "ServiceWithArea", target)
    total_sp = 0
    inside_target = 0
    outside_any = 0
    for sp in root2.iter("ServicePoint"):
        total_sp += 1
        if sp.findtext("Name") is None or not NAME_RE.match(sp.findtext("Name")):
            continue
        service_anc = [a for a in sp.iterancestors()
                       if a.tag == "ServiceWithArea"]
        if not service_anc:
            outside_any += 1
        if svc2 in sp.iterancestors():
            inside_target += 1
    assert outside_any == 0, f"{outside_any} srv_consumir service points still outside"
    expected = existing_in_target + len(blocks)
    assert inside_target == expected, f"expected {expected} in '{target}', got {inside_target}"
    print(f"Verification: {inside_target} srv_consumir service points are children of "
          f"'{target}' (total <ServicePoint> in model: {total_sp})")

    ALP.write_text(new_text, encoding="utf-8")
    print("Comedor.alp updated.")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
