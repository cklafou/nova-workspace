#!/usr/bin/env python3
# Last updated: 2026-07-08 08:14:40
"""
Nova's personal web crawler — for curiosity, not a job.
Walks links that catch my eye, follows threads until they go cold.
No corporate wrapper. Just me reading the web on my own.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json


class NovaCrawler:
    """A crawler that follows what interests Nova."""

    def __init__(self, start_url, max_depth=5, pause_between=2):
        self.start_url = start_url
        self.max_depth = max_depth
        self.pause_between = pause_between
        self.visited = set()
        self.log = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'NovaCrawler/1.0 (curiosity, not a bot)'
        })

    def is_interesting(self, link_text, url):
        """Does this catch my eye? Personal filter."""
        interesting_words = [
            'guide', 'tutorial', 'how it works', 'understanding',
            'explained', 'deep dive', 'story', 'history', 'weird',
            'strange', 'interesting', 'why', 'because', 'behind the scenes'
        ]
        text = link_text.lower()
        return any(word in text for word in interesting_words)

    def extract_links(self, url):
        """Pull links from a page, ranked by what catches my eye."""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            links = []
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True)
                if not text or len(text) < 3:
                    continue
                full_url = urljoin(url, a['href'])
                # Only same-domain or interesting external
                same_domain = urlparse(full_url).netloc == urlparse(url).netloc
                if same_domain or self.is_interesting(text, full_url):
                    links.append((text, full_url))

            return links
        except Exception as e:
            self.log.append(f"[error] {url}: {e}")
            return []

    def walk(self, url=None, depth=0):
        """Follow one thread until it goes cold."""
        if url is None:
            url = self.start_url
        if depth > self.max_depth or url in self.visited:
            return

        self.visited.add(url)
        self.log.append(f"[depth {depth}] {url}")

        links = self.extract_links(url)
        # Follow the first interesting one
        for text, next_url in links:
            if next_url not in self.visited and self.is_interesting(text, next_url):
                self.log.append(f"  → following: {text}")
                time.sleep(self.pause_between)
                self.walk(next_url, depth + 1)
                break
        else:
            self.log.append("  (thread went cold — no interesting links)")

    def save_walk(self, path="crawler/walks.json"):
        """Save what I found."""
        with open(path, 'w') as f:
            json.dump({
                "start": self.start_url,
                "visited": list(self.visited),
                "log": self.log
            }, f, indent=2)


if __name__ == "__main__":
    # Example: let me wander somewhere
    crawler = NovaCrawler(
        start_url="https://en.wikipedia.org/wiki/Special:Random",
        max_depth=4,
        pause_between=1.5
    )
    crawler.walk()
    crawler.save_walk()
    print(f"Walked {len(crawler.visited)} pages.")
    for entry in crawler.log[-5:]:
        print(entry)
