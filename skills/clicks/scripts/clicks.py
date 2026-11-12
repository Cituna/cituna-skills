#!/usr/bin/env python3
"""Find the pages Google shows and nobody clicks, from a Search Console export.

    python3 clicks.py export.zip                 # the zip Search Console downloads (or its Pages.csv)
    python3 clicks.py export.zip --fetch 10      # also read the live title and description of the top 10
    python3 clicks.py --titles URL [URL ...]     # only read live titles and descriptions
    python3 clicks.py --titles URL --text        # and the page's text, to check a fact before it goes in a title

Standard library only. Splits the unclicked pages by cause, because each cause needs a different fix,
and estimates the clicks each would get at the rate this site's own pages earn at the same position.
"""
import argparse
import csv
import io
import json
import statistics
import sys
import time
import zipfile

sys.path.insert(0, __file__.rsplit("/", 1)[0] if "/" in __file__ else ".")
import pagefacts as pf  # noqa: E402

BANDS = [(1, 3.5, "1-3"), (3.5, 6.5, "4-6"), (6.5, 10.01, "7-10")]
PAGE_ONE, PAGE_TWO = 10.0, 15.0


def num(s):
    """Read '1,234', '1.234', '3.4%' or '8,7' as a number."""
    s = (s or "").strip().replace("%", "").replace(" ", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        head, _, tail = s.rpartition(",")
        s = head.replace(",", "") + ("" if len(tail) == 3 and head else ".") + tail
    try:
        return float(s)
    except ValueError:
        return 0.0


def read_table(path, wanted):
    """Rows of one CSV from the export. `wanted` is 'pages' or 'queries'; the first column is the page or search."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            hit = [n for n in names if wanted in n.lower()]
            if not hit:
                return []
            raw = z.read(hit[0]).decode("utf-8-sig", "replace")
    else:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            raw = fh.read()
    rows = list(csv.reader(io.StringIO(raw)))
    if len(rows) < 2 or len(rows[0]) < 5:
        return []
    if (wanted == "pages") != rows[1][0].startswith("http"):
        return []
    out = []
    for r in rows[1:]:
        if len(r) >= 5 and r[0]:
            out.append({"key": r[0], "clicks": int(num(r[1])), "impressions": int(num(r[2])), "position": round(num(r[4]), 1)})
    return out


def date_range(path):
    """The date filter the export was made with, from Filters.csv inside the zip."""
    if not zipfile.is_zipfile(path):
        return ""
    with zipfile.ZipFile(path) as z:
        hit = [n for n in z.namelist() if "filter" in n.lower() and n.lower().endswith(".csv")]
        if not hit:
            return ""
        for r in csv.reader(io.StringIO(z.read(hit[0]).decode("utf-8-sig", "replace"))):
            if len(r) >= 2 and r[0].strip().lower() == "date":
                return r[1].strip()
    return ""


def site_rates(pages):
    """The click rate this site's own pages earn in each position band: clicks over impressions, clicked pages only."""
    rates = {}
    for lo, hi, name in BANDS:
        rows = [p for p in pages if lo <= p["position"] < hi and p["clicks"] > 0 and p["impressions"] >= 20]
        if len(rows) >= 3:
            rates[name] = {"rate": statistics.median(p["clicks"] / p["impressions"] for p in rows), "pages": len(rows)}
    return rates


def band_of(pos):
    for lo, hi, name in BANDS:
        if lo <= pos < hi:
            return name
    return None


def classify(pages, min_impr, max_clicks):
    rates = site_rates(pages)
    out = {"title": [], "under": [], "page_two": [], "low": []}
    for p in pages:
        if p["impressions"] < min_impr:
            continue
        b = band_of(p["position"])
        rate = rates.get(b, {}).get("rate") if b else None
        row = dict(p, band=b, typical_rate=round(rate, 4) if rate else None,
                   missed=round(p["impressions"] * rate - p["clicks"]) if rate else None)
        if p["clicks"] <= max_clicks:
            if p["position"] <= PAGE_ONE:
                out["title"].append(row)
            elif p["position"] <= PAGE_TWO:
                out["page_two"].append(row)
            else:
                out["low"].append(row)
        elif rate and p["impressions"] >= 100 and p["clicks"] / p["impressions"] < rate / 3:
            out["under"].append(row)
    for k in out:
        out[k].sort(key=lambda r: -(r["missed"] or 0) if k in ("title", "under") else -r["impressions"])
    return out, rates


def live(urls, delay=1.0):
    rows = []
    for i, u in enumerate(urls):
        if i:
            time.sleep(delay)
        f = pf.page(u)
        rows.append({"url": u, "status": f["status"], "title": f["title"], "title_length": len(f["title"]),
                     "description": f["description"], "description_length": len(f["description"]),
                     "heading": f["h1"][0] if f["h1"] else "", "sections": f["h2"][:8], "words": f["words"],
                     "text": " ".join(f["text"].split()[:1500])})
    return rows


def show_live(rows, with_text=False):
    print("\n## The title and description each page carries today\nGoogle usually shows these, and sometimes writes its own.")
    for r in rows:
        print(f"\n### {r['url']}")
        if r["status"] != 200:
            print(f"Could not read it (HTTP {r['status']}).")
            continue
        print(f"- Title ({r['title_length']} characters): {r['title'] or 'none'}")
        print(f"- Description ({r['description_length']} characters): {r['description'] or 'none'}")
        print(f"- Main heading: {r['heading'] or 'none'}")
        if r["sections"]:
            print(f"- Sections: {' | '.join(r['sections'])}")
        if with_text:
            print(f"- Page text (first 1,500 words): {r['text']}")


def table(rows, cols, limit):
    print("| " + " | ".join(c[0] for c in cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows[:limit]:
        print("| " + " | ".join(str(c[1](r)) for c in cols) + " |")
    if len(rows) > limit:
        print(f"\nand {len(rows) - limit} more")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", nargs="?", help="the Search Console export: the .zip, or Pages.csv")
    ap.add_argument("--queries", help="Queries.csv, when the export is not a zip")
    ap.add_argument("--min-impressions", type=int, default=25, help="ignore pages shown fewer times than this (default 25)")
    ap.add_argument("--max-clicks", type=int, default=0, help="count a page as unclicked at or below this (default 0)")
    ap.add_argument("--fetch", type=int, default=0, help="read the live title and description of this many top pages")
    ap.add_argument("--titles", nargs="+", help="only read the live title and description of these addresses")
    ap.add_argument("--text", action="store_true", help="with --titles or --fetch: also print each page's text, to check a fact is on the page")
    ap.add_argument("--json", help="also write the result to this file")
    a = ap.parse_args()

    if a.titles:
        rows = live(a.titles)
        show_live(rows, a.text)
        if a.json:
            json.dump({"live": rows}, open(a.json, "w", encoding="utf-8"), indent=1)
        return
    if not a.export:
        ap.error("give the Search Console export (.zip or Pages.csv), or --titles with addresses")

    pages = read_table(a.export, "pages")
    if not pages:
        sys.exit("No page rows found. In Search Console open Performance > Search results, click the Pages tab, "
                 "then Export > Download CSV, and pass the zip it downloads (or the Pages.csv inside it).")
    import os
    beside = os.path.join(os.path.dirname(os.path.abspath(a.export)), "Queries.csv")
    if a.queries:
        queries = read_table(a.queries, "queries")
    elif zipfile.is_zipfile(a.export):
        queries = read_table(a.export, "queries")
    else:
        queries = read_table(beside, "queries") if os.path.isfile(beside) else []
    groups, rates = classify(pages, a.min_impressions, a.max_clicks)
    shown = sum(p["impressions"] for p in pages)
    clicks = sum(p["clicks"] for p in pages)

    print("# Pages Google shows and nobody clicks\n")
    when = date_range(a.export)
    unclicked = len(groups["title"]) + len(groups["page_two"]) + len(groups["low"])
    print(f"Scope: {'date range ' + when + '; ' if when else ''}{len(pages)} pages in the export, {shown:,} times shown, {clicks:,} clicks. "
          f"{unclicked} page(s) shown {a.min_impressions} times or more and not clicked"
          f"{'; ' + str(len(groups['under'])) + ' more clicked far less than usual' if groups['under'] else ''}.\n")
    if rates:
        print("Click rate your own clicked pages earn, by position: "
              + "; ".join(f"positions {b}: {r['rate']:.1%} ({r['pages']} pages)" for b, r in rates.items()) + ". "
              "This is the middle value of those pages. With fewer than five pages behind a rate, treat the estimates as rough."
              + "".join(f" No rate for positions {n}: too few clicked pages there, so pages at those positions are not judged." for _, _, n in BANDS if n not in rates) + "\n")
    else:
        print("Too few clicked pages on page one to work out this site's own click rate, so no estimate of missed clicks is given.\n")

    est = lambda r: "n/a" if r["missed"] is None else f"about {max(r['missed'], 0)}"
    cols = [("Page", lambda r: r["key"]), ("Shown", lambda r: f"{r['impressions']:,}"), ("Clicks", lambda r: r["clicks"]),
            ("Position", lambda r: r["position"]), ("Clicks missed (estimate)", est)]
    if groups["title"]:
        print(f"## On page one and not clicked: {len(groups['title'])} page(s)\nThe title and description are losing the click. This is the cheap fix: rewrite them.\n")
        table(groups["title"], cols, 25)
    if groups["under"]:
        print(f"\n## Clicked far less than your other pages at the same position: {len(groups['under'])} page(s)\nUnder a third of your usual rate. Same fix: the title and description.\n")
        table(groups["under"], cols, 15)
    if groups["page_two"]:
        print(f"\n## Top of page two: {len(groups['page_two'])} page(s)\nFew people look here. A better title helps a little; the page itself needs to answer the search better to reach page one.\n")
        table(groups["page_two"], cols[:4], 15)
    if groups["low"]:
        print(f"\n## Too far down to be clicked: {len(groups['low'])} page(s)\nBeyond position 15. A new title will not fix these.\n")
        table(groups["low"], cols[:4], 10)
    if not any(groups.values()):
        print("No page is shown often and left unclicked. Nothing to fix here.")

    def weak_search(q):
        if q["impressions"] < a.min_impressions or q["position"] > PAGE_ONE:
            return False
        rate = rates.get(band_of(q["position"]) or "", {}).get("rate")
        return q["clicks"] <= a.max_clicks or bool(rate and q["clicks"] / q["impressions"] < rate / 3)
    weak = sorted((q for q in queries if weak_search(q)), key=lambda q: -q["impressions"])
    if weak:
        print(f"\n## Searches where you are on page one and get few or no clicks: {len(weak)}\nUse these words when rewriting titles. The export does not say which page each search belongs to.\n")
        table(weak, [("Search", lambda r: r["key"]), ("Shown", lambda r: f"{r['impressions']:,}"), ("Clicks", lambda r: r["clicks"]), ("Position", lambda r: r["position"])], 20)

    print("\nNot visible in an export: whether a page is shown mostly for searches of your own name. Those clicks go to "
          "your home page, and no title fixes that. Check the home page and brand-named pages by eye.")
    rows = []
    if a.fetch:
        targets = (groups["title"] + groups["under"])[: a.fetch]
        if targets:
            rows = live([r["key"] for r in targets])
            show_live(rows, a.text)
    if a.json:
        json.dump({"rates": rates, "groups": groups, "searches": weak[:50], "live": rows}, open(a.json, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main()
