#!/usr/bin/env python3
"""Write the rmpp project lists of the site from GitHub: no page to edit when a project appears.

The projects are the public repositories of lorancecall with the topic `rmpp`. rmpp/projects.json holds their
texts (en/ko), tags, nesting (`parent`) and order; a project not in it appears after the others with its GitHub
description. Rewrites what is between the markers
  <!-- rmpp:cards -->...<!-- /rmpp:cards -->   in rmpp/index.html and rmpp/ko.html (the cards)
  <!-- rmpp:tree -->...<!-- /rmpp:tree -->     in index.html and ko.html (the project tree)

  python3 scripts/rmpp_projects.py           rewrite the pages
  python3 scripts/rmpp_projects.py --check   exit 1 if a page would change
"""
import argparse
import html
import json
import os
import pathlib
import re
import sys
import urllib.request

OWNER, TOPIC = "lorancecall", "rmpp"
ROOT = pathlib.Path(__file__).resolve().parent.parent
URL = "https://github.com/{}/{}"


def repos():
    found, page = {}, 1
    while True:
        req = urllib.request.Request(f"https://api.github.com/users/{OWNER}/repos?per_page=100&type=owner&page={page}",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "rmpp-site"})
        if os.environ.get("GITHUB_TOKEN"):
            req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")
        batch = json.loads(urllib.request.urlopen(req, timeout=60).read())
        if not batch:
            return found
        for r in batch:
            if not r["private"] and not r["fork"] and not r["archived"] and TOPIC in r.get("topics", []):
                found[r["name"]] = r
        page += 1


def plan(found, meta):
    """[(name, info)] in tree order and the card order."""
    info = {}
    for name, r in found.items():
        m = dict(meta["projects"].get(name, {}))
        desc = html.escape(r.get("description") or "")
        for k in ("card_en", "card_ko", "tree_en", "tree_ko"):
            m.setdefault(k, desc)
        if m.get("parent") not in found:
            m.pop("parent", None)
        info[name] = m

    def key(order):
        return lambda n: (order.index(n) if n in order else len(order), n)
    tree = sorted(info, key=key(meta.get("order", [])))
    cards = sorted([n for n in info if info[n].get("card", True) is not False], key=key(meta.get("card_order", meta.get("order", []))))
    return info, tree, cards


def render_cards(info, cards, lang):
    out = []
    for n in cards:
        m = info[n]
        tag = f'<span class="tag">{m["tag"]}</span>' if m.get("tag") else ""
        out.append(f'    <a class="card" href="{URL.format(OWNER, n)}"><h3>{n}{tag}</h3>\n      <p>{m["card_" + lang]}</p></a>')
    return "\n".join(out)


def render_tree(info, tree, lang):
    def item(n, indent):
        m = info[n]
        tag = m.get("tag") or m.get("tag_tree")
        tag = f'<span class="tag">{tag}</span>' if tag else ""
        pad = " " * indent
        s = (f'{pad}<li><span class="node"><a class="name" href="{URL.format(OWNER, n)}">{n}</a>{tag}\n'
             f'{pad}  <span class="desc">{m["tree_" + lang]}</span></span>')
        kids = [k for k in tree if info[k].get("parent") == n]
        if kids:
            s += f"\n{pad}  <ul>\n" + "\n".join(item(k, indent + 4) for k in kids) + f"\n{pad}  </ul>\n{pad}</li>"
        else:
            s += "</li>"
        return s
    return "\n".join(item(n, 8) for n in tree if not info[n].get("parent"))


def replace(text, marker, body):
    pat = re.compile(rf"(<!-- rmpp:{marker} -->\n).*?(\n *<!-- /rmpp:{marker} -->)", re.S)
    if not pat.search(text):
        sys.exit(f"marker rmpp:{marker} missing")
    return pat.sub(lambda m: m.group(1) + body + m.group(2), text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    meta = json.loads((ROOT / "rmpp" / "projects.json").read_text(encoding="utf-8"))
    info, tree, cards = plan(repos(), meta)
    pages = {"rmpp/index.html": ("cards", "en"), "rmpp/ko.html": ("cards", "ko"),
             "index.html": ("tree", "en"), "ko.html": ("tree", "ko")}
    changed = []
    for page, (marker, lang) in pages.items():
        f = ROOT / page
        old = f.read_text(encoding="utf-8")
        body = render_cards(info, cards, lang) if marker == "cards" else render_tree(info, tree, lang)
        new = replace(old, marker, body)
        if new != old:
            changed.append(page)
            if not args.check:
                f.write_text(new, encoding="utf-8", newline="\n")
    print("projects:", ", ".join(tree))
    print("changed:", ", ".join(changed) or "nothing")
    if args.check and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
