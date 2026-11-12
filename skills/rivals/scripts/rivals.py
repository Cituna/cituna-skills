#!/usr/bin/env python3
"""Put your page next to the rival pages AI assistants name, and list what theirs have that yours lacks.

    python3 rivals.py --yours https://acme.example/pricing https://rival-one.example/pricing https://rival-two.example/plans

Standard library only. One request a second. It counts what is on each page as served, by pattern, and it can be
wrong: open each page and correct the table before you rely on it. It does not judge the writing. Read the section
lists it prints to see the topics a rival covers and you do not.
"""
import argparse
import json
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import pagefacts as pf  # noqa: E402

MONEY = re.compile(r"(?:[$€£]\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:USD|EUR|GBP|AED)\b|\b(?:USD|EUR|GBP|AED)\s?\d[\d,.]*)")
FIGURE = re.compile(r"\b\d[\d,.]*\s?(?:%|percent|x\b|k\b|m\b|kb\b|mb\b|gb\b|ms\b|million|billion|times\b|seconds?|minutes?|hours?|days?|"
                    r"customers|users|teams|countries|sites|websites|companies|businesses|people|visitors|downloads|reviews|stars)", re.I)
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATED = re.compile(r"(?:updated|last (?:checked|verified|reviewed|modified)|reviewed|published|as of)\W{0,25}(?:on |in )?"
                   r"(" + MONTH + r" \d{1,2},? \d{4}|\d{1,2} " + MONTH + r" \d{4}|" + MONTH + r" \d{4}|\d{4}-\d{2}-\d{2})", re.I)


def person(author, host):
    """An author name that is a person, not the company: no word of it appears in the site's address."""
    words = [w for w in re.findall(r"[a-z]{4,}", author.lower())]
    return bool(words) and not any(w in host.replace(".", "") for w in words)


def has_heading(f, rx):
    return any(re.search(rx, h, re.I) for h in f["h2"] + f["h3"] + f["h1"])


def profile(url):
    f = pf.page(url)
    types = set(f["schema_types"])
    own = pf.host_of(f["final_url"] or url)
    out_hosts = {pf.host_of(l["url"]) for l in f["external_links"] if not l["chrome"]} - {own}
    shown = DATED.search(f["text"])
    feats = {
        "Prices on the page": len(MONEY.findall(f["text"])) >= 1,
        "A comparison table": f["tables"] > 0,
        "Questions and answers (FAQ)": "FAQPage" in types or has_heading(f, r"\bfaqs?\b|frequently asked|common questions"),
        "Customer quotes, reviews or ratings": bool(types & {"Review", "AggregateRating"}) or f["quotes"] > 0 or has_heading(f, r"review|testimonial|what (our )?customers say|loved by|case stud"),
        "Compares itself with named alternatives": has_heading(f, r"\bvs\.?\b|versus|alternative|compar"),
        "Step-by-step or how it works": "HowTo" in types or has_heading(f, r"how it works|how to|step \d|getting started"),
        "Numbers and results": len(FIGURE.findall(f["text"])) >= 3,
        "Links out to sources": len(out_hosts) >= 3,
        "A named person as author": person(f["author"], own),
        "Says when it was last updated": bool(shown),
        "Video or an embedded demo": f["videos"] > 0,
        "Structured data for machines": bool(types),
    }
    return {
        "url": url, "host": own, "status": f["status"], "error": f["error"], "title": f["title"], "description": f["description"],
        "heading": f["h1"][0] if f["h1"] else "", "words": f["words"], "sections": f["h2"], "subsections": len(f["h3"]),
        "final_url": f["final_url"] or url, "pictures": f["pictures"], "tables": f["tables"], "updated": shown.group(1) if shown else "", "author": f["author"],
        "schema_types": sorted(types), "prices_found": len(MONEY.findall(f["text"])), "figures_found": len(FIGURE.findall(f["text"])),
        "sources_linked": len(out_hosts), "features": feats, "readable": f["status"] == 200 and f["words"] >= 80,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rival_urls", nargs="+", help="the rival pages")
    ap.add_argument("--yours", required=True, help="your page for the same question")
    ap.add_argument("--json", help="also write the result to this file")
    a = ap.parse_args()

    pages = []
    for i, u in enumerate([a.yours] + a.rival_urls):
        if i:
            time.sleep(1.0)
        pages.append(profile(u))
    you, rivals = pages[0], pages[1:]
    read = [r for r in rivals if r["readable"]]

    print("# Your page next to theirs\n")
    cols = [("you: " + you["host"], you)] + [(r["host"], r) for r in rivals]
    print("| | " + " | ".join(c[0] for c in cols) + " |")
    print("|---|" + "---|" * len(cols))
    line = lambda label, fn: print(f"| {label} | " + " | ".join(str(fn(p)) if p["readable"] else "unread" for _, p in cols) + " |")
    line("Words", lambda p: p["words"])
    line("Sections", lambda p: len(p["sections"]))
    line("Pictures (logos and icons left out)", lambda p: p["pictures"])
    for feat in you["features"]:
        line(feat, lambda p, k=feat: ("yes" + (f" ({p['updated']})" if k == "Says when it was last updated" else "")) if p["features"][k] else "no")

    if not you["readable"]:
        print(f"\nYour page could not be read (HTTP {you['status'] or you['error']}, {you['words']} words). "
              "If it loads its text with scripts, AI assistants that do not run scripts see it the same way.")
    if read and you["readable"]:
        lacks = [(k, [r["host"] for r in read if r["features"][k]]) for k, v in you["features"].items() if not v]
        lacks = [(k, hosts) for k, hosts in lacks if hosts]
        lacks.sort(key=lambda x: -len(x[1]))
        print("\n## What their pages have that yours lacks")
        if lacks:
            for k, hosts in lacks:
                print(f"- {k}: {len(hosts)} of {len(read)} rival pages ({', '.join(hosts)})")
        else:
            print("Nothing on this list. The difference is in what the sections say: compare the section lists below.")
        longer = [r for r in read if r["words"] > you["words"] * 1.5]
        if longer:
            print(f"- Length: {len(longer)} of {len(read)} rival pages have over one and a half times your {you['words']} words "
                  f"({', '.join(str(r['words']) + ' on ' + r['host'] for r in longer)}). Length alone earns nothing: look at which sections make up the difference.")
        wins = [k for k, v in you["features"].items() if v and not any(r["features"][k] for r in read)]
        if wins:
            print("\n## What only your page has\n" + "\n".join(f"- {k}" for k in wins))

    print("\n## Sections on each page")
    for name, p in cols:
        print(f"\n### {name}\n{p['final_url']}" + (f" (asked for {p['url']})" if not pf.same_page(p["url"], p["final_url"]) else ""))
        if not p["readable"]:
            print(f"Could not be read (HTTP {p['status'] or p['error']}, {p['words']} words came back). Open it yourself.")
            continue
        print(f"Title: {p['title']}")
        for s in p["sections"][:30]:
            print(f"- {s}")
        if not p["sections"]:
            print("- no section headings")
    if a.json:
        json.dump({"yours": you, "rivals": rivals}, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
