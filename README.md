# Site Link Finder

Crawls an **entire** domain and answers two questions:

1. **Where on the site does this link sit?** — shows every page it appears on.
2. **Which links are broken?** — shows the address, the **reason** and the page holding it.

---

## Running it

Two ways: from source (needs Python) or as a standalone `.exe` (needs nothing).
For sharing with someone else, see [Sharing with a colleague](#sharing-with-a-colleague).

**Double-click `run.bat`** — a browser opens with the interface.

If the .bat file does not work, do the same by hand:

```
python app.py
```

then open http://127.0.0.1:8765

The libraries (`requests`, `beautifulsoup4`, `openpyxl`) are installed once and the
.bat file handles that for you. To finish, close the black console window or press
`Ctrl+C` inside it.

> **Restart the program after a code update.** Python reads `.py` files once, at
> startup. Until the black window is closed and opened again, the old version keeps
> running even though the files on disk are new. Easy to verify: the **version is shown
> on the right of the interface header** and in the console at startup. If it changed,
> the code is fresh.
>
> Starting a second copy while the first is running is safe: it takes the next free
> port and says so in the console. Check the address bar if you have two windows open.

---

## Sharing with a colleague

Send them the **[Releases page](../../releases)** — the latest `SiteLinkFinder.exe`
is attached to every release as a direct download. A single self-contained file,
**12 MB, no Python, no libraries, no installation**.

**What the colleague does:** download the .exe → double-click → a console window opens
→ the browser opens the interface. Reports land in a `results` folder created next to
the .exe. To quit, close the console window.

Two things worth warning them about:

- **Windows SmartScreen** may show "Windows protected your PC" the first time, because
  the file is not code-signed. Click **More info → Run anyway**.
- **The first launch takes a few seconds** — the app unpacks itself into a temp folder.
  Later launches are quicker.

Requirements on their side: Windows 10 or 11, 64-bit, and internet access to reach the
site being scanned. Nothing else.

### Publishing a new version

The .exe is **not stored in git** — GitHub builds it. To ship an update:

```bash
git add -A && git commit -m "what changed" && git push

git tag v2.6          # bump VERSION in app.py to match
git push origin v2.6
```

Pushing the tag starts [the workflow](.github/workflows/release.yml): GitHub spins up a
clean Windows machine, builds the .exe, **launches it from an empty folder to confirm it
really serves the interface**, and only then publishes the release with the file attached.
Progress is visible on the Actions tab; the whole run takes a few minutes.

The release can also be triggered by hand from the Actions tab
(*Build and release Windows exe → Run workflow*).

**Building locally** is still possible with `build_exe.bat` — handy for testing a change
before tagging it. The result lands in `dist\SiteLinkFinder.exe` and is ignored by git;
the `build\` folder is temporary and can be deleted at any time.

---

## Three modes

| Mode | What it does | When you need it |
|---|---|---|
| 🎯 **Find a link** | Crawls the site and shows every page holding the link | "What else points at this old URL before I delete the page?" |
| 💔 **Broken links** | Collects every dead link with a reason | Routine 404 sweep |
| 🗺️ **Site map** | Just the list of all pages with status codes | You need an inventory of pages — the fastest mode |

---

## How to use it

### Find where a link sits

1. Pick **🎯 Find a link**.
2. **Site domain**: `example.com` (`https://` optional).
3. **Which link to find** — any of these forms works:
   - a fragment: `old-page`
   - a path: `/blog/old-page`
   - a full URL: `https://www.example.com/blog/old-page`
4. Press **Start**.

A table appears: page → the found link → **where exactly it sits** → link text.

#### The "Where exactly" column — read it

A link on a site is not always the one you can see. Every match is tagged:

- **👁 On the page** — a normal link or button, you will find it by looking;
- **🔧 Technical** — the link only exists in the code, it is **not visible** on the page.

Technical matches are things like:

| Label | What it means |
|---|---|
| `hreflang in <head> — SEO tag` | points at another language version, meant for Google |
| `canonical in <head>` | the "main" address of the page for search engines |
| `inside page source (script/JSON)` | the link is baked into a script — common for JS-driven buttons |
| `CSS stylesheet`, `site icon` | attached files |

If a match is tagged **🔧 Technical**, looking for it on the page itself is pointless —
open the page source instead (`Ctrl+U` in the browser).

#### Match type — not every match is a link

A search for a URL also matches links that merely *carry* that URL, most often
share buttons:

```
http://www.facebook.com/share.php?u=https://example.com/blog/post
```

That link goes to Facebook; your address just rides along in its query string.
Counting it as an inbound link is how inflated numbers happen, so every match is
labelled:

- **links here** — a real link to the address;
- **not a link here** — the address only appears inside another link;
- **links to itself** — the page's own canonical, hreflang or share button.

The summary shows **how many pages link here**, and separately **how many of those
are canonical**. The second number is what SEO crawlers report: a link from
`/blog/page/18` whose canonical points at `/blog` is discounted, because the site
itself declares that page a duplicate. Such sources are marked
**non-canonical source** in the table.

On a real page this gave *7 pages link here, 5 of them canonical* — and Sitebulb
reported exactly 5 for the same URL.

#### Status of the found link

Under each address you see whether it works: **✓ works** or **✕ 404**.
This catches a common case — the link exists on the site but points at a deleted page.

### Find broken links

1. Pick **💔 Broken links**, enter the domain, press Start.
2. The table shows: page holding the link → the dead link → **reason** →
   **where exactly** it sits → link text.

Both kinds of links are checked:

- **visible ones** — `<a>` links, buttons, form targets;
- **the ones in `<head>`** — `hreflang`, `canonical`, pagination. Those are invisible
  on the page but search engines follow them, so a 404 there is a real defect. They
  are flagged **🔧 Technical** in the "Where exactly" column.

Images, css and scripts are *not* checked unless you tick "Check images and scripts" —
otherwise every missing icon would drown out the actual broken pages.

#### Pages with no internal links (orphan pages)

In this mode the advanced settings offer **"Also find pages with no internal links"**.
It reports pages that exist and open fine, but that **no page on the site links to** —
SEO tools call these *no internal linking URLs*. You can only reach such a page by
knowing its address; search engines give it almost no weight, and more often than not
it is simply a page everyone forgot about.

Two things to know:

- **It needs `sitemap.xml`.** A page discovered by following links is, by definition,
  linked from somewhere — so orphans can only surface where the sitemap lists a page the
  crawl never reached. On a site without a sitemap the report says so instead of lying.
- **Run it without limits.** With a crawl depth or page limit set, pages you simply never
  reached would look like orphans. The log warns you when that is the case.

Only ordinary `<a>` links count as internal linking here — `hreflang` and `canonical`
carry no weight for search engines, so a page reachable only through them still counts
as an orphan. That is exactly why the same wording shows up while searching: if every
match for your link sits in a technical tag, the result is marked **no internal links**.

Reasons are written in plain language:

- `Page not found (404) - broken link` — the classic, needs fixing
- `Domain does not exist / DNS does not resolve` — the target site is gone
- `Forbidden (403) - often bot protection` — **check manually**, the link is often alive,
  the site simply dislikes robots
- `Connection timeout` — no answer from the server, worth a re-check
- `SSL certificate error` — the target site has an HTTPS problem
- `Too many requests (429)` — the site is throttling you: drop threads to 3–5 and retry

By default only links inside your own domain are checked. To also check links pointing
at other sites, tick **"Check external links"** in the advanced settings (slower).

---

## Results

- **In the browser** — filterable, sortable tables. The "Filter the table" box instantly
  narrows rows by any piece of text, and clicking **Status**, **Indexable** or **Links**
  sorts by that column — the first click puts the problems on top. Every address is clickable.
- **Excel** — the "⬇ Download Excel" button. The file is built **only when you click
  the button**; nothing is saved on its own after a scan. Downloaded reports land in
  the `results/` folder ("📁 Results folder" opens it).

The workbook has four sheets: *Summary*, *Where the link was found*, *Broken links*,
*All pages*. Each has an auto-filter, so you can sort right inside Excel.

> The browser shows at most 3000 rows per table so the page stays responsive.
> **Excel always contains everything** — for large result sets, work with the file.

---

## Advanced settings

| Setting | Why |
|---|---|
| **Search the page source too** | Catches links inside scripts and JS-driven buttons with no `<a>` tag. On by default |
| **Use sitemap.xml** | Fast start: takes the ready-made page list |
| **Follow links** | Finds pages that are **missing** from the sitemap. Works together with the sitemap |
| **Include subdomains** | `blog.example.com`, `info.example.com` — needed when a blog or landing pages live on a separate host |
| **Check external links** | Also checks links pointing at other sites |
| **Check images and scripts** | Also finds broken images, css and js. Page links in `<head>` (hreflang, canonical) are checked either way |
| **Also find pages with no internal links** | Only in *Broken links* mode. Lists pages nothing on the site links to. Needs sitemap.xml and an unlimited crawl |
| **List only non-indexable pages** | Narrows the page table to those search engines will skip, with the reason |
| **Threads** | Speed. 10 by default; if the site returns 429, drop to 3–5 |
| **Crawl depth** | `2` = two clicks from the home page, `0` = start pages only |
| **Pause between requests** | `0.2–0.5` sec if the site starts blocking you |
| **Skip addresses containing** | Comma separated: `/tag/, ?page=, /author/` — saves time on pagination |

The **Stop** button interrupts the crawl, but everything gathered so far is kept and
the Excel file can still be built — nothing is lost.

---

## Indexability

Every crawled page gets a verdict on whether a search engine may index it. It costs
nothing — all the signals arrive with the pages already being fetched — so the
**Indexable** column is always there, in every mode.

| Verdict | What it means |
|---|---|
| `Indexable` | nothing stops it from appearing in search |
| `Noindex` | the page itself says "skip me" via `<meta robots>` or the `X-Robots-Tag` header |
| `Canonicalised` | its `canonical` points at a different URL, so that other page gets indexed instead |
| `Blocked by robots.txt` | crawlers are not allowed to fetch it at all |
| `HTTP 404` / `HTTP 5xx` | it does not answer properly |
| `Not a page` | an image or PDF listed in the sitemap — not something to index as a page |

The checks run in the order an engine applies them: a page blocked in `robots.txt` is
never fetched, so its meta tags never matter.

Tick **"List only non-indexable pages"** in the advanced settings to narrow the table
to just those, with the reason spelled out.

The log also points out a specific contradiction: pages listed in `sitemap.xml` that
simultaneously tell engines to skip them. The sitemap says "index this", the page says
"do not" — usually a leftover nobody noticed.

---

## Reading the crawl log

```
Starting queue: 1839 addresses. Crawling ...
  pages crawled: 30, left in queue: 1911, queued 102 more addresses
  pages crawled: 60, left in queue: 1891, queued 10 more addresses
```

This is **only about the crawl queue**, not about matches for your query.
Matches are reported separately, at the end, in the results table.

**Why does the queue grow while pages are being crawled?** That is normal.
The queue is live: after crawling a page the tool sees links to other pages and queues
the ones it has not met yet. Over the first 30 pages, 30 addresses left the queue and
102 were added — hence 1911. The growth then falls off (nearly every link is already
known) and the queue drains to zero.

Those added addresses are exactly the pages that are **not in the sitemap**.
On a real 1800-page site this surfaced over a hundred live pages the sitemap never
listed — `/contact-us` and whole product sections among them. With the sitemap alone
they would never reach the report.

The same address is never downloaded twice: `www`, `http/https`, a trailing slash and
tracking tags (`?utm_source=…`, `?_ga=…`, `?fbclid=…`) all count as one address.
Meaningful parameters (`?page=2`, `?hsLang=en`) are kept — those are different pages.

---

## How long it takes

A site of ~1800 pages: site map takes a couple of minutes, finding a link 2–3 minutes,
broken links the longest — it depends on how many links there are. Progress and the log
are visible in the interface, and you can press Stop at any moment.

To get a quick feel for an unfamiliar site, set **crawl depth** to `1` in the advanced settings.

---

## Command line

When you do not need the interface (for scheduled runs, for example):

```bash
# where a link sits
python cli.py --domain example.com --find "/blog/old-page"

# every broken link
python cli.py --domain example.com --mode broken

# search + broken links in one pass, external links included
python cli.py --domain example.com --find "/old-page" --mode full --check-external

# quick trial run
python cli.py --domain example.com --mode pages --limit 50
```

All flags: `python cli.py --help`

> The CLI also offers `--mode full` (search + broken links in a single crawl) and
> `--limit`. Both were removed from the interface to keep it uncluttered, but kept in
> the CLI for automation. Unlike the interface, the CLI saves the .xlsx immediately.

---

## Files

| File | What it is |
|---|---|
| `run.bat` | One-click launcher |
| `app.py` | Web server: API and static files |
| `core.py` | Engine: crawling, search, link checks, Excel export |
| `cli.py` | Command-line version |
| `static/index.html` | Interface markup |
| `static/css/style.css` | Styles |
| `static/js/app.js` | Front-end logic |
| `results/` | Finished reports |

---

## Troubleshooting

**Suspiciously few pages found** — the site has no sitemap or an incomplete one.
Check that "Follow links" is on and try "Include subdomains".

**Lots of 403 links** — the site is defending against bots. Drop threads to 3 and set a
0.5 sec pause. Such links are usually fine; spot-check a couple by hand.

**Lots of 429** — same thing: 3 threads, 0.5–1 sec pause.

**Takes too long** — set crawl depth to `1`–`2`, or exclude pagination through
"Skip addresses containing".
