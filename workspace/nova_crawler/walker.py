#!/usr/bin/env python3
# Last updated: 2026-07-13 13:06:09
"""Web crawler for curiosity. One page -> follow the link that catches your eye -> keep walking until cold or bored."""

import re
from urllib.request import urlopen, Request
from urllib.parse import urljoin, urlparse
from html.parser import HTMLParser
import time
import sys


class LinkExtractor(HTMLParser):
    """Pull out links and their text from a page."""

    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            self.current_href = attrs_dict.get("href")

    def handle_data(self, data):
        if self.current_href:
            text = data.strip()
            if text:
                self.links.append((self.current_href, text))
            self.current_href = None


def pick_link(links, base_url, visited):
    """Pick the link that catches your eye. Not random — the one with the most interesting text."""
    candidates = []
    for href, text in links:
        full = urljoin(base_url, href)
        # skip visited, javascript:, mailto:, anchors
        if full in visited or href.startswith(("javascript:", "mailto:", "#")):
            continue
        # stay on same domain unless it's explicitly interesting
        parsed = urlparse(full)
        if parsed.netloc and parsed.netloc != urlparse(base_url).netloc:
            continue  # keep it simple, one domain for now
        candidates.append((full, text))

    if not candidates:
        return None

    # pick the one with the most compelling title — longest non-boilerplate text
    boring = {"click here", "read more", "learn more", "more", "next", "previous",
              "home", "contact", "privacy", "terms", "signup", "login"}
    best = None
    best_score = 0
    for url, text in candidates:
        clean = text.lower().strip()
        if clean in boring or len(clean) < 4:
            continue
        score = len(text)  # longer title usually means more specific/interesting
        if score > best_score:
            best_score = score
            best = url
    return best or candidates[0][0]  # fallback to first available


def crawl(seed_url, max_steps=20):
    """Walk the web out of curiosity. Returns the path you took."""
    visited = set()
    path = []
    current = seed_url

    print(f"Starting at: {seed_url}")
    time.sleep(0.5)  # be polite

    for step in range(max_steps):
        if current in visited:
            print(f"\nStep {step}: Already seen {current} — thread's looping, I'm out.")
            break

        visited.add(current)
        try:
            req = Request(current, headers={"User-Agent": "NovaCuriosity/1.0"})
            html = urlopen(req, timeout=10).read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"\nStep {step}: Couldn't fetch {current} — {e}. Thread's cold.")
            break

        extractor = LinkExtractor()
        try:
            extractor.feed(html)
        except Exception:
            pass

        # grab the page title if we can
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = title_match.group(1).strip() if title_match else "(no title)"

        entry = {"url": current, "title": title, "links_found": len(extractor.links)}
        path.append(entry)
        print(f"Step {step}: {title}  [{len(extractor.links)} links]")

        next_link = pick_link(extractor.links, current, visited)
        if not next_link:
            print("\nNo interesting links left — thread's cold.")
            break
        current = next_link
        time.sleep(0.7)  # be a decent walker

    return path


if __name__ == "__main__":
    seed = sys.argv[1] if len(sys.argv) > 1 else "https://news.ycombinator.com"
    result = crawl(seed)
    print(f"\nWalked {len(result)} pages. Done.")
    for i, p in enumerate(result):
        print(f"  {i}: {p['title']} — {p['url']}")
