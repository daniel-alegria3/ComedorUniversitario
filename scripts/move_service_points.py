#!/usr/bin/env python3
"""Move all top-level `srv_consumir_spN` service points of Comedor.alp into the
`<Presentation>` of the `srv_consumir` ServiceWithArea so they become its children.

The operation is a pure text move: element boundaries are computed from the lxml
parse (sourceline + serialized subtree line count), then the raw line ranges are
cut from their top-level location and pasted, in order, right after the existing
`srv_consumir_sp1..sp8` points and before that service's `</Presentation>` tag.

No line is added or removed (only relocated), and the result is re-validated as
XML before the file is written.
"""

import re
import shutil
import sys
from pathlib import Path

from lxml import etree

ALP = Path(__file__).parent / "Comedor.alp"
NAME_RE = re.compile(r"^srv_consumir_sp\d+$")


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


def main() -> None:
    text = ALP.read_text(encoding="utf-8")
    original_lines = text.splitlines(keepends=True)

    backup = ALP.with_name(ALP.stem + ".alp.bak")
    shutil.copyfile(ALP, backup)
    print(f"Backup written to {backup}")

    root = etree.fromstring(text.encode("utf-8"))

    svc = find_service(root, "ServiceWithArea", "srv_consumir")
    pres = svc.find("Presentation")
    if pres is None:
        raise SystemExit("ERROR: 'srv_consumir' has no <Presentation> child")

    pres_end = end_line(pres)
    assert original_lines[pres_end - 1].strip() == "</Presentation>", (
        f"unexpected line at insertion point: {original_lines[pres_end - 1]!r}"
    )

    blocks = []  # (start_line, end_line, raw_text)
    for sp in root.iter("ServicePoint"):
        if sp.findtext("Name") is None or not NAME_RE.match(sp.findtext("Name")):
            continue
        if svc in sp.iterancestors():
            continue  # already a child of srv_consumir
        start = sp.sourceline
        end = end_line(sp)
        assert original_lines[end - 1].strip() == "</ServicePoint>", (
            f"unexpected block end at line {end}: {original_lines[end - 1]!r}"
        )
        assert start > pres_end, f"block at line {start} is above insertion point"
        blocks.append((start, end, "".join(original_lines[start - 1:end])))

    blocks.sort()
    print(f"Moved {len(blocks)} service points into 'srv_consumir'")

    # Remove blocks (reverse order so line numbers stay valid)…
    new_lines = original_lines[:]
    for start, end, _ in reversed(blocks):
        del new_lines[start - 1:end]

    # …then insert them, in original order, before srv_consumir's </Presentation>.
    idx = pres_end - 1
    assert new_lines[idx].strip() == "</Presentation>"
    new_lines[idx:idx] = [block for _, _, block in blocks]

    new_text = "".join(new_lines)
    assert new_text.count("\n") == text.count("\n"), "newline count changed"

    # Re-validate and re-assert the invariants.
    root2 = etree.fromstring(new_text.encode("utf-8"))
    svc2 = find_service(root2, "ServiceWithArea", "srv_consumir")
    total_sp = 0
    outside = 0
    inside = 0
    for sp in root2.iter("ServicePoint"):
        total_sp += 1
        if sp.findtext("Name") is not None and NAME_RE.match(sp.findtext("Name")):
            if svc2 in sp.iterancestors():
                inside += 1
            else:
                outside += 1
    assert outside == 0, f"{outside} srv_consumir service points still outside"
    assert inside == 8 + len(blocks), f"expected {8 + len(blocks)} inside, got {inside}"
    print(f"Verification: {inside}/{inside + outside} srv_consumir service points "
          f"are children of 'srv_consumir' (total <ServicePoint> in model: {total_sp})")

    ALP.write_text(new_text, encoding="utf-8")
    print("Comedor.alp updated.")


if __name__ == "__main__":
    sys.exit(main())
