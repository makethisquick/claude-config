#!/usr/bin/env python3
"""Check a client report before it is sent.

There is no LibreOffice or pandoc on this machine, so the document cannot be
rendered to images. This checks everything that CAN be checked mechanically —
and the point of the banned-term sweep is that one stray account id or the word
"waste" undoes the trust the rest of the report builds.

Exit 1 on anything that should block sending.
"""
import re, sys, zipfile

# Terms that must never reach a client. Separated so the message can explain WHY.
BANNED = {
 "internal identifiers": [r"\bgclid\b", r"\bgbraid\b", r"\bwbraid\b", r"\butm_[a-z]+\b",
                          r"\bad_group\b", r"\bcampaign_id\b", r"\bcustomer_id\b", r"\bMCC\b",
                          r"\blaunch\.json\b", r"\breport\.json\b", r"\bGAQL\b", r"\bAPI\b",
                          r"\b\d{3}-\d{3}-\d{4}\b(?!.{0,40}(call|phone|reach|dial))"],
 "tooling names":       [r"\bFluent ?Forms?\b", r"\bElementor\b", r"\bWPMU\b", r"\bWordPress\b",
                         r"\bRank ?Math\b", r"\bmatplotlib\b", r"\bClaude\b"],
 "unglossed jargon":    [r"\bimpression share\b", r"\bquality score\b", r"\bmatch type\b",
                         r"\bnegative keyword\b", r"\bbid modifier\b", r"\bad rank\b"],
 "tone":                [r"\bwaste(d|ful)?\b", r"\bjunk\b", r"\bgarbage\b", r"\bstupid\b"],
}
# a glossary entry legitimately defines a jargon term, so allow it there
GLOSSARY_OK = {"unglossed jargon"}

def text_of(docx):
    z = zipfile.ZipFile(docx)
    xml = z.read("word/document.xml").decode("utf-8")
    return xml, " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)), z

def main():
    if len(sys.argv) < 2: sys.exit("usage: verify.py <report.docx>")
    f = sys.argv[1]
    xml, txt, z = text_of(f)
    problems, notes = [], []

    # structure: every part must be well-formed XML
    import xml.dom.minidom as MD
    for n in z.namelist():
        if n.endswith((".xml",".rels")):
            try: MD.parseString(z.read(n))
            except Exception as e: problems.append(f"malformed XML in {n}: {str(e)[:70]}")

    paras = len(re.findall(r"<w:p[ >]", xml)); tables = xml.count("<w:tbl>")
    pics  = xml.count("<pic:pic"); words = len(txt.split())
    media = [n for n in z.namelist() if n.startswith("word/media/") and not n.endswith("/")]
    sig = bytes([0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a])
    bad_png = [m for m in media if m.endswith(".png") and z.read(m)[:8] != sig]
    if bad_png: problems.append(f"corrupt image(s): {bad_png}")
    rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
    used = set(re.findall(r'r:embed="([^"]+)"', xml)); have = set(re.findall(r'Id="([^"]+)"', rels))
    if not used <= have: problems.append(f"image reference(s) do not resolve: {sorted(used-have)}")
    if pics != len(media): notes.append(f"{pics} image placements vs {len(media)} embedded files")
    if re.findall(r"<w:t[^>]*>[^<]*[•\n][^<]*</w:t>", xml):
        problems.append("literal bullet or newline inside a text run — use numbering/separate paragraphs")

    # language sweep
    low = txt.lower()
    for cat, pats in BANNED.items():
        for p in pats:
            for m in re.finditer(p, txt, re.I):
                ctx = txt[max(0,m.start()-45):m.start()+45].replace("\n"," ")
                if cat in GLOSSARY_OK and re.search(r"—\s*$", txt[max(0,m.start()-60):m.start()]):
                    continue  # it's a glossary definition line
                problems.append(f"{cat}: '{m.group(0)}'  …{ctx}…")

    print(f"  structure : {paras} paragraphs, {tables} tables, {pics} images, {words} words")
    print(f"  images    : {len(media)} embedded, all valid PNG" if not bad_png else f"  images    : PROBLEM")
    for n in notes: print(f"  note      : {n}")
    if problems:
        print(f"\n  ✗ {len(problems)} problem(s) — do not send until resolved:")
        for p in problems[:25]: print(f"      {p}")
        sys.exit(1)
    print("\n  ✓ passes every mechanical check.")
    print("  ! Cannot render the document on this machine (no LibreOffice/pandoc),")
    print("    so layout is UNVERIFIED. Ask the user to open it once before sending.")

if __name__ == "__main__": main()
