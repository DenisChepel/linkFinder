#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py - the same audit, without the interface.

Examples:

    # find where a link sits on the site
    python cli.py --domain example.com --find "/old-page"

    # every broken link with its reason
    python cli.py --domain example.com --mode broken

    # search + broken links in a single pass, external links included
    python cli.py --domain example.com --find "/old-page" --mode full --check-external

    # quick trial run over 50 pages
    python cli.py --domain example.com --mode pages --limit 50
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

import core


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(
        description="Find links and audit broken links across a whole domain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--domain", required=True, help="domain, e.g. example.com")
    p.add_argument("--find", default="", help="link or substring to look for")
    p.add_argument("--mode", default=None, choices=["search", "broken", "pages", "full"],
                   help="mode (defaults to search when --find is given, otherwise pages)")
    p.add_argument("--match", default="contains", choices=["contains", "exact", "regex"],
                   help="how to compare while searching")
    p.add_argument("--output", default=None, help="where to save the .xlsx file")
    p.add_argument("--limit", type=int, default=None, help="maximum number of pages")
    p.add_argument("--max-depth", type=int, default=None, help="crawl depth from the start page")
    p.add_argument("--workers", type=int, default=10, help="threads (default 10)")
    p.add_argument("--delay", type=float, default=0.0, help="pause between requests, seconds")
    p.add_argument("--subdomains", action="store_true", help="include subdomains")
    p.add_argument("--check-external", action="store_true", help="check external links")
    p.add_argument("--check-assets", action="store_true", help="check images/scripts/css")
    p.add_argument("--no-sitemap", action="store_true", help="do not use sitemap.xml")
    p.add_argument("--no-crawl", action="store_true", help="do not follow links (sitemap only)")
    p.add_argument("--no-raw-html", action="store_true", help="do not search the raw HTML")
    p.add_argument("--exclude", default="", help="skip addresses containing these substrings, comma separated")
    args = p.parse_args()

    mode = args.mode or ("search" if args.find else "pages")

    opts = core.Options(
        domain=args.domain,
        mode=mode,
        query=args.find,
        match=args.match,
        limit=args.limit,
        max_depth=args.max_depth,
        workers=args.workers,
        delay=args.delay,
        include_subdomains=args.subdomains,
        use_sitemap=not args.no_sitemap,
        use_crawl=not args.no_crawl,
        check_external=args.check_external,
        check_assets=args.check_assets,
        search_raw_html=not args.no_raw_html,
        exclude=[x.strip() for x in args.exclude.split(",") if x.strip()],
    )

    auditor = core.SiteAuditor(opts, on_log=lambda m: print(m, flush=True))
    summary = auditor.run()

    out = args.output
    if not out:
        results = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
        os.makedirs(results, exist_ok=True)
        host = urlparse(auditor.root).netloc.replace(":", "_")
        out = os.path.join(results, f"{host}_{datetime.now():%Y-%m-%d_%H%M%S}.xlsx")
    core.export_xlsx(auditor, out)

    print()
    print("-" * 60)
    print(f"  Pages crawled:   {summary['pages']}")
    print(f"  Links collected: {summary['links']}")
    if mode in ("search", "full") and args.find:
        print(f"  Matches:         {summary['hits']} on {summary['hit_pages']} pages")
    if mode in ("broken", "full"):
        print(f"  Broken links:    {summary['broken']} ({summary['broken_unique']} unique)")
    print(f"  File:            {out}")
    print("-" * 60)


if __name__ == "__main__":
    main()
