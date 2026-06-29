"""
ingest_breakingbad.py — Breaking Bad ingest adapter

Source: the Forever Dreaming fan transcripts (https://transcripts.foreverdreaming.org,
forum f=165). Unlike dialogue-only subtitle rips, these include the *scene directions and
action descriptions* (e.g. "Scene: White Residence." / "(Walt pulls off the gas mask)") plus
speaker labels — the non-spoken behaviour that gives the OCEAN scorer its signal, exactly like
the Friends source. We strip the HTML to plain text, one line per paragraph/scene direction,
matching the shape of the GoT TV-script segments. One segment file per episode:
  <franchise_dir>/state/segments/s{season}e{episode:02d}.txt

The site sits behind an Anubis proof-of-work bot-wall, so it can't be fetched cold. The user
solves the challenge once in a browser and exports the session Cookie header; this adapter
replays it. Two acquisition modes:

  ONLINE  (default): read books/cookies.txt (+ optional books/user_agent.txt) and use it to
          fetch the episode index (topic t=10106), then download each of the 62 episodes.
  OFFLINE (fallback): if no cookie / the wall still blocks us, drop any manually-saved episode
          pages into books/ as *.html and we parse those instead. Season/episode are taken from
          the filename (s01e01.html / 1x01.html) or the page's "NxNN" title.

Place the cookie / saved pages in build/franchises/breakingbad/books/ (gitignored), then:
    python ingest_breakingbad.py <franchise_dir>

Stdlib only (html.parser, re) plus requests. Idempotent: episodes already present in
segments/ are skipped, so an expired cookie mid-run is recoverable by re-exporting and re-running.
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import requests

BASE = "https://transcripts.foreverdreaming.org"
INDEX_URL = f"{BASE}/viewtopic.php?t=10106"  # Breaking Bad transcript index topic (forum f=165)

# Fallback UA — the one observed to clear the wall; overridden by books/user_agent.txt if present.
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Episode links in the index are forum f=165 topics; their anchor text is the *episode title*
# (e.g. "The Pilot"), not an "NxNN" code — so we map the in-order links to seasons by Breaking
# Bad's known per-season episode counts (broadcast order), the same approach as ingest_got.py.
# NB: separators are HTML-entity-encoded in the index (f=165&amp;t=...), so don't require a
# literal '&'/'?' immediately before t=.
EP_LINK_RE = re.compile(r'href="([^"]*f=165[^"]*t=(\d+)[^"]*)"', re.IGNORECASE)
SEASON_EPISODES = {1: 7, 2: 13, 3: 13, 4: 13, 5: 16}  # 62 episodes total

# (season, episode) for the Nth episode in broadcast order, 0-based N.
SEASON_SLOTS = [(s, e) for s, n in SEASON_EPISODES.items() for e in range(1, n + 1)]
# Season/episode from a saved filename (s01e01 / 1x01) or a page title.
FILE_SE_RE = re.compile(r"s(\d{1,2})e(\d{2})", re.IGNORECASE)
TITLE_SE_RE = re.compile(r"\b(\d{1,2})x(\d{2})\b")

# The page is the bot-wall, not a transcript, if it carries the Anubis challenge markers.
CHALLENGE_MARKERS = ("make_challenge", "Javascript is disabled", "anubis")

# Forum boilerplate lines that are neither dialogue nor scene direction.
SKIP_LINE_RE = re.compile(
    r"^(transcribed by|transcript by|submitted and corrected by|submitted by|corrected by|"
    r"original air date|written by|directed by|thanks to|edited by|posted|return to|"
    r"jump to|back to top|all times are)\b",
    re.IGNORECASE,
)

MIN_BYTES = 500  # a real transcript is much larger; below this we treat it as empty/blocked


class TranscriptParser(HTMLParser):
    """Flatten the phpBB post body to one text line per block (dialogue or stage direction).

    Captures only text inside the first <div class="content"> (the post body), tracking div
    depth so nested divs don't end capture early. If no such div is found, ``captured`` stays
    empty and the caller re-parses in whole-document mode.
    """

    _BREAK_TAGS = {"p", "br", "tr", "div", "li"}
    _SKIP_CONTENT = {"head", "title", "script", "style"}

    def __init__(self, whole_document: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._cur: list[str] = []
        self._skip_depth = 0
        self._whole = whole_document
        self._capturing = whole_document
        self._div_depth = 0  # nesting depth once inside the content div

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self._SKIP_CONTENT:
            self._skip_depth += 1
            return
        if tag == "div" and not self._whole:
            cls = dict(attrs).get("class", "") or ""
            if not self._capturing:
                if "content" in cls.split():
                    self._capturing = True
                    self._div_depth = 1
            else:
                self._div_depth += 1
        if self._capturing and tag in self._BREAK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_CONTENT and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._capturing and tag in self._BREAK_TAGS:
            self._flush()
        if tag == "div" and self._capturing and not self._whole:
            self._div_depth -= 1
            if self._div_depth <= 0:
                self._capturing = False

    def handle_data(self, data: str) -> None:
        if self._capturing and self._skip_depth == 0:
            self._cur.append(data)

    def _flush(self) -> None:
        text = " ".join("".join(self._cur).split())
        if text:
            self.lines.append(text)
        self._cur = []

    def get_lines(self) -> list[str]:
        self._flush()
        return self.lines


def _html_to_text(html: str) -> str:
    parser = TranscriptParser()
    parser.feed(html)
    lines = parser.get_lines()
    if not lines:  # no <div class="content"> — saved full page; parse the whole document
        parser = TranscriptParser(whole_document=True)
        parser.feed(html)
        lines = parser.get_lines()
    return "\n".join(ln for ln in lines if not SKIP_LINE_RE.match(ln))


def _is_challenge(html: str) -> bool:
    head = html[:4000].lower()
    return any(m.lower() in head for m in CHALLENGE_MARKERS)


def _load_cookie(books_dir: Path) -> tuple[str | None, str]:
    cookie_file = books_dir / "cookies.txt"
    ua_file = books_dir / "user_agent.txt"
    cookie = None
    if cookie_file.exists():
        cookie = " ".join(cookie_file.read_text(encoding="utf-8").split())
        cookie = cookie or None
    ua = DEFAULT_UA
    if ua_file.exists():
        ua = ua_file.read_text(encoding="utf-8").strip() or DEFAULT_UA
    return cookie, ua


def _make_session(cookie: str | None, ua: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE + "/",
    })
    if cookie:
        s.headers["Cookie"] = cookie
    return s


def _online(franchise_dir: Path, segments_dir: Path, books_dir: Path) -> int:
    cookie, ua = _load_cookie(books_dir)
    if not cookie:
        print("  No books/cookies.txt — skipping online fetch (see OFFLINE fallback).")
        return 0

    session = _make_session(cookie, ua)
    print("  Fetching episode index (with exported cookie)...")
    try:
        idx = session.get(INDEX_URL, timeout=60)
    except requests.RequestException as e:
        print(f"  ERROR fetching index: {e}")
        return 0
    if idx.status_code != 200 or _is_challenge(idx.text):
        print(f"  Index blocked (HTTP {idx.status_code}, bot-wall={_is_challenge(idx.text)}). "
              "Re-export a fresh cookie, or use the OFFLINE fallback.")
        return 0

    # Collect episode topic links in document order, de-duped by topic id (first seen wins),
    # then map the Nth link to the Nth broadcast slot (season, episode).
    ordered_urls: list[str] = []
    seen_ids: set[str] = set()
    for href, tid in EP_LINK_RE.findall(idx.text):
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        url = href if href.startswith("http") else f"{BASE}/{href.lstrip('./')}"
        # The index links are http://; requesting them triggers an http->https redirect that
        # serves the bot-wall. Hitting https directly returns the transcript, so force https.
        ordered_urls.append(url.replace("&amp;", "&").replace("http://", "https://"))

    if len(ordered_urls) != len(SEASON_SLOTS):
        print(f"  WARNING: found {len(ordered_urls)} episode links but expected "
              f"{len(SEASON_SLOTS)} — season mapping may be off; review the roster after.")
    episodes = {SEASON_SLOTS[i]: url for i, url in enumerate(ordered_urls)
                if i < len(SEASON_SLOTS)}
    print(f"  {len(episodes)} episode links mapped from index.")

    downloaded = 0
    for (season, ep), url in sorted(episodes.items()):
        out_file = segments_dir / f"s{season}e{ep:02d}.txt"
        if out_file.exists():
            continue
        try:
            resp = session.get(url, timeout=60)
        except requests.RequestException as ex:
            print(f"  ERROR s{season}e{ep:02d}: {ex}")
            continue
        if resp.status_code != 200 or _is_challenge(resp.text):
            print(f"  BLOCKED s{season}e{ep:02d} (HTTP {resp.status_code}) — cookie may have expired.")
            continue
        text = _html_to_text(resp.text)
        if len(text.encode("utf-8")) < MIN_BYTES:
            print(f"  EMPTY s{season}e{ep:02d}: {len(text)} chars — skipping")
            continue
        out_file.write_text(text, encoding="utf-8")
        print(f"  OK    s{season}e{ep:02d}  ({len(text)} chars)")
        downloaded += 1
    return downloaded


def _offline(segments_dir: Path, books_dir: Path) -> int:
    """Parse any manually-saved *.html episode pages in books/."""
    html_files = sorted(books_dir.glob("*.html")) + sorted(books_dir.glob("*.htm"))
    if not html_files:
        return 0
    print(f"  OFFLINE: parsing {len(html_files)} saved HTML page(s) from books/...")
    written = 0
    for f in html_files:
        html = f.read_text(encoding="utf-8", errors="ignore")
        if _is_challenge(html):
            print(f"  SKIP  {f.name}: saved page is the bot-wall, not a transcript.")
            continue
        m = FILE_SE_RE.search(f.stem) or TITLE_SE_RE.search(f.stem) or TITLE_SE_RE.search(html[:4000])
        if not m:
            print(f"  SKIP  {f.name}: could not determine season/episode (name it s01e01.html).")
            continue
        season, ep = int(m.group(1)), int(m.group(2))
        out_file = segments_dir / f"s{season}e{ep:02d}.txt"
        if out_file.exists():
            continue
        text = _html_to_text(html)
        if len(text.encode("utf-8")) < MIN_BYTES:
            print(f"  EMPTY s{season}e{ep:02d} from {f.name}: {len(text)} chars — skipping")
            continue
        out_file.write_text(text, encoding="utf-8")
        print(f"  OK    s{season}e{ep:02d}  ({len(text)} chars)  <- {f.name}")
        written += 1
    return written


def run(franchise_dir: Path) -> None:
    segments_dir = franchise_dir / "state" / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)
    books_dir = franchise_dir / "books"
    books_dir.mkdir(parents=True, exist_ok=True)

    downloaded = _online(franchise_dir, segments_dir, books_dir)
    downloaded += _offline(segments_dir, books_dir)

    total = len(list(segments_dir.glob("*.txt")))
    if total == 0:
        print(
            "\nNo segments produced. Export the Forever Dreaming cookie to "
            f"{books_dir / 'cookies.txt'} (and optional user_agent.txt), or save episode\n"
            "pages there as s01e01.html, then re-run."
        )
    else:
        print(f"\nIngest complete: {downloaded} new this run. {total} segments total in {segments_dir}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_breakingbad.py <franchise_dir>")
        sys.exit(1)
    run(Path(sys.argv[1]))
