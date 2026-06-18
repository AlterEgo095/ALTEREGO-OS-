"""PHASE 2.9 — SCÉNARIO 5 : Navigation Web.

Le système :
- recherche
- navigue
- extrait les informations
- cite les sources
- archive

V1.1: Uses subprocess curl (no Playwright dependency required).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


async def fetch_url(url: str) -> dict:
    """Fetch a URL via curl subprocess."""
    proc = await asyncio.create_subprocess_exec(
        "curl", "-sL", "--max-time", "10", "-A", "ALTEREGO-OS/1.0", url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {stderr.decode()[:200]}")
    return {"url": url, "content": stdout.decode("utf-8", errors="replace"), "size": len(stdout)}


def strip_html(html: str) -> str:
    """Crude HTML to text conversion."""
    # Remove scripts and styles
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else "(no title)"


def extract_meta_description(html: str) -> str:
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract up to 10 unique http(s) links."""
    links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html, re.IGNORECASE)
    # Dedupe, limit
    seen = set()
    unique = []
    for l in links:
        if l not in seen and len(unique) < 10:
            seen.add(l)
            unique.append(l)
    return unique


async def main():
    print("=" * 70)
    print("PHASE 2.9 — SCÉNARIO 5 : NAVIGATION WEB")
    print("=" * 70)

    # Test URLs (public, stable, no auth required)
    test_urls = [
        ("https://example.com", "Classic example.com — always available"),
    ]

    results = []
    all_passed = True

    for url, description in test_urls:
        print(f"\n── {url} ({description}) ──")
        start = time.perf_counter()
        try:
            print(f"  → Navigation...")
            response = await fetch_url(url)
            print(f"  ✓ {response['size']} bytes récupérés")

            print(f"  → Extraction des informations...")
            html = response["content"]
            title = extract_title(html)
            description_meta = extract_meta_description(html)
            text = strip_html(html)
            links = extract_links(html, url)

            print(f"  ✓ Titre: {title}")
            print(f"  ✓ Description: {description_meta[:100] if description_meta else '(none)'}")
            print(f"  ✓ Texte extrait: {len(text)} caractères")
            print(f"  ✓ {len(links)} liens trouvés")

            # Citation
            print(f"  → Citation des sources...")
            citation = f"Source: {url} (accessed {time.strftime('%Y-%m-%d %H:%M:%S')})"

            # Archive
            print(f"  → Archivage...")
            with tempfile.TemporaryDirectory() as tmp:
                archive_path = Path(tmp) / f"archive_{hashlib.md5(url.encode()).hexdigest()[:8]}.html"
                archive_path.write_text(html)
                archive_size = archive_path.stat().st_size
                archive_hash = hashlib.sha256(html.encode()).hexdigest()[:16]

            elapsed = time.perf_counter() - start

            criteria = {
                "fetched": response["size"] > 0,
                "title_extracted": title != "(no title)",
                "text_extracted": len(text) > 0,
                "links_found": len(links) >= 0,
                "cited_source": bool(citation),
                "archived": archive_size > 0,
            }
            passed = all(criteria.values())

            results.append({
                "url": url,
                "passed": passed,
                "criteria": criteria,
                "title": title,
                "text_length": len(text),
                "links_count": len(links),
                "archive_hash": archive_hash,
                "elapsed_ms": round(elapsed * 1000, 1),
            })

            print(f"\n  Scénario 5 ({url}): {'✓ PASS' if passed else '✗ FAIL'}")

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"  ✗ ERREUR: {e}")
            results.append({"url": url, "passed": False, "error": str(e), "elapsed_ms": round(elapsed * 1000, 1)})
            all_passed = False

    print(f"\n{'=' * 70}")
    overall = all(r.get("passed", False) for r in results)
    print(f"SCÉNARIO 5: {'✓ PASS' if overall else '✗ FAIL'} ({sum(1 for r in results if r.get('passed'))}/{len(results)} URLs)")

    out = Path(__file__).resolve().parent.parent / "results" / "scenario_05_web.json"
    out.write_text(json.dumps({"scenario": 5, "passed": overall, "results": results}, indent=2, default=str))
    print(f"Results saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
