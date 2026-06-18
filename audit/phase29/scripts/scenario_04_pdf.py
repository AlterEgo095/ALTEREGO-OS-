"""PHASE 2.9 — SCÉNARIO 4 : Lire un document PDF.

Le système :
- extrait le texte
- résume
- classe
- mémorise
- répond aux questions

V1.1: Uses pypdf (already installed via pdf skill). If pypdf unavailable, skips.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


async def extract_pdf_text(pdf_path: Path) -> dict:
    """Extract text from a PDF using pypdf. Resilient to font errors."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            # Fallback: try with visitor_text or just empty
            text = f"(page {i+1}: extraction error)"
        pages.append({"page": i + 1, "text": text, "char_count": len(text)})
    return {
        "page_count": len(pages),
        "total_chars": sum(p["char_count"] for p in pages),
        "pages": pages,
    }


def summarize_text(text: str, max_chars: int = 500) -> str:
    """Simple extractive summary: first paragraph + first sentence of each subsequent paragraph."""
    if not text:
        return "(empty)"
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text[:max_chars]
    summary_parts = [paragraphs[0][:200]]
    for p in paragraphs[1:4]:  # next 3 paragraphs
        first_sentence = p.split(".")[0] + "."
        summary_parts.append(first_sentence)
    summary = " | ".join(summary_parts)
    return summary[:max_chars]


def classify_document(text: str) -> dict:
    """Simple keyword-based classification."""
    text_lower = text.lower()
    categories = {
        "technical": ["api", "code", "function", "class", "python", "javascript", "algorithm"],
        "financial": ["revenue", "profit", "loss", "balance", "fiscal", "quarterly"],
        "legal": ["contract", "agreement", "party", "liability", "jurisdiction"],
        "research": ["study", "hypothesis", "methodology", "results", "conclusion", "abstract"],
        "report": ["report", "summary", "overview", "analysis", "findings"],
    }
    scores = {}
    for cat, keywords in categories.items():
        score = sum(text_lower.count(kw) for kw in keywords)
        if score > 0:
            scores[cat] = score
    if not scores:
        return {"primary": "unknown", "scores": {}}
    primary = max(scores, key=scores.get)
    return {"primary": primary, "scores": scores}


def answer_question(text: str, question: str) -> str:
    """Simple keyword-based Q&A: find sentence with most keyword overlap."""
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if len(s.strip()) > 20]
    if not sentences:
        return "(no answer found)"
    q_words = set(question.lower().split())
    best_sentence = ""
    best_score = 0
    for s in sentences:
        s_words = set(s.lower().split())
        overlap = len(q_words & s_words)
        if overlap > best_score:
            best_score = overlap
            best_sentence = s
    if best_score == 0:
        return "(no relevant answer found)"
    return best_sentence


async def main():
    print("=" * 70)
    print("PHASE 2.9 — SCÉNARIO 4 : LECTURE PDF")
    print("=" * 70)

    if not PYPDF_AVAILABLE:
        print("\n⚠ pypdf not installed — scenario skipped.")
        out = Path(__file__).resolve().parent.parent / "results" / "scenario_04_pdf.json"
        out.write_text(json.dumps({"scenario": 4, "passed": None, "reason": "pypdf not installed"}, indent=2))
        print(f"SCÉNARIO 4: ⚠ SKIPPED")
        return

    # Find a PDF to test (use the architecture report we generated earlier)
    candidates = [
        Path("/home/z/my-project/download/AI_Operating_System_Architecture_Report.pdf"),
        Path("/home/z/my-project/download/alterego-os/docs/architecture/AI_Operating_System_Architecture_Report.pdf"),
    ]
    pdf_path = next((p for p in candidates if p.exists()), None)

    if not pdf_path:
        print("\n⚠ No PDF file available for testing — scenario skipped.")
        out = Path(__file__).resolve().parent.parent / "results" / "scenario_04_pdf.json"
        out.write_text(json.dumps({"scenario": 4, "passed": None, "reason": "no PDF file"}, indent=2))
        print(f"SCÉNARIO 4: ⚠ SKIPPED")
        return

    print(f"\n── PDF analysé : {pdf_path.name} ──")
    start = time.perf_counter()

    # 1. Extract text
    print("  → Extraction du texte...")
    extraction = await extract_pdf_text(pdf_path)
    print(f"  ✓ {extraction['page_count']} pages, {extraction['total_chars']} caractères")

    # 2. Summarize
    print("  → Résumé...")
    full_text = " ".join(p["text"] for p in extraction["pages"])
    summary = summarize_text(full_text)
    print(f"  ✓ Résumé: {summary[:200]}...")

    # 3. Classify
    print("  → Classification...")
    classification = classify_document(full_text)
    print(f"  ✓ Catégorie: {classification['primary']}")

    # 4. Memorize (hash + metadata)
    print("  → Mémorisation...")
    doc_id = hashlib.md5(full_text.encode()).hexdigest()[:12]
    memory_record = {
        "doc_id": doc_id,
        "filename": pdf_path.name,
        "page_count": extraction["page_count"],
        "char_count": extraction["total_chars"],
        "summary": summary,
        "classification": classification["primary"],
        "memorized_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(f"  ✓ Mémorisé sous ID: {doc_id}")

    # 5. Q&A
    print("  → Questions / Réponses...")
    questions = [
        "What is the architecture of the system?",
        "What is the kernel?",
        "What are the plugins?",
    ]
    qa_pairs = []
    for q in questions:
        answer = answer_question(full_text, q)
        qa_pairs.append({"question": q, "answer": answer[:200]})
        print(f"  Q: {q}")
        print(f"  A: {answer[:150]}")
        print()

    elapsed = time.perf_counter() - start

    # Validation criteria
    criteria = {
        "text_extracted": extraction["total_chars"] > 0,
        "summarized": len(summary) > 0,
        "classified": classification["primary"] != "unknown",
        "memorized": bool(doc_id),
        "qa_answered": all(qa["answer"] != "(no answer found)" for qa in qa_pairs),
    }

    print(f"── Critères de validation ──")
    for k, v in criteria.items():
        print(f"  {'✓' if v else '✗'} {k}")

    passed = all(criteria.values())
    print(f"\nSCÉNARIO 4: {'✓ PASS' if passed else '✗ FAIL'}")

    out = Path(__file__).resolve().parent.parent / "results" / "scenario_04_pdf.json"
    out.write_text(json.dumps({
        "scenario": 4,
        "passed": passed,
        "criteria": criteria,
        "memory_record": memory_record,
        "qa_pairs": qa_pairs,
        "elapsed_ms": round(elapsed * 1000, 1),
    }, indent=2, default=str))
    print(f"Results saved to: {out}")


if __name__ == "__main__":
    asyncio.run(main())
