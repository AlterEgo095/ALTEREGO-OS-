"""Compile all 10 audit results into a final report with global maturity score."""
import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
REPORT_PATH = Path(__file__).resolve().parent.parent / "report" / "FINAL_AUDIT_REPORT.md"

# Weights for each audit (sum to 100)
WEIGHTS = {
    "architecture": 12,
    "event_bus": 10,
    "memory": 10,
    "plugin_manager": 12,
    "capability_registry": 10,
    "chief_of_staff": 10,
    "scheduler": 8,
    "security": 15,  # highest weight — critical
    "observability": 8,
    "performance": 5,
}

# Map audit name → filename
AUDIT_FILES = {
    "architecture": "audit_01_architecture.json",
    "event_bus": "audit_02_event_bus.json",
    "memory": "audit_03_memory.json",
    "plugin_manager": "audit_04_plugin_manager.json",
    "capability_registry": "audit_05_capability_registry.json",
    "chief_of_staff": "audit_06_chief_of_staff.json",
    "scheduler": "audit_07_scheduler.json",
    "security": "audit_08_security.json",
    "observability": "audit_09_observability.json",
    "performance": "audit_10_performance.json",
}


def load_results():
    results = {}
    for name, fname in AUDIT_FILES.items():
        path = RESULTS_DIR / fname
        if path.exists():
            results[name] = json.loads(path.read_text())
    return results


def compute_global_score(results):
    """Weighted average of audit scores."""
    total_weight = 0
    weighted_sum = 0
    for name, weight in WEIGHTS.items():
        if name in results:
            score = results[name].get("score", 0)
            weighted_sum += score * weight
            total_weight += weight
    return int(weighted_sum / total_weight) if total_weight else 0


def collect_all_issues(results):
    """All issues across all audits, sorted by severity."""
    all_issues = []
    for name, r in results.items():
        for issue in r.get("issues", []):
            issue["audit"] = name
            all_issues.append(issue)
    # Sort: critical > warning > info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_issues.sort(key=lambda i: severity_order.get(i.get("severity", "info"), 3))
    return all_issues


def count_tests(results):
    total = 0
    passed = 0
    for r in results.values():
        for t in r.get("tests", []):
            total += 1
            if t.get("passed"):
                passed += 1
    return total, passed


def generate_report():
    results = load_results()
    global_score = compute_global_score(results)
    all_issues = collect_all_issues(results)
    total_tests, passed_tests = count_tests(results)

    critical_issues = [i for i in all_issues if i.get("severity") == "critical"]
    warning_issues = [i for i in all_issues if i.get("severity") == "warning"]
    info_issues = [i for i in all_issues if i.get("severity") == "info"]

    lines = []
    lines.append("# ALTEREGO OS V1 — AUDIT COMPLET")
    lines.append("")
    lines.append(f"**Score global de maturité : {global_score}/100**")
    lines.append("")
    lines.append(f"Tests exécutés : **{passed_tests}/{total_tests}** ({int(passed_tests/total_tests*100)}%)")
    lines.append(f"Problèmes critiques : **{len(critical_issues)}**")
    lines.append(f"Warnings : **{len(warning_issues)}**")
    lines.append(f"Infos : **{len(info_issues)}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Score par audit
    lines.append("## Scores par audit")
    lines.append("")
    lines.append("| # | Audit | Score | Poids | Score pondéré | Statut |")
    lines.append("|---|-------|-------|-------|---------------|--------|")
    audit_names_fr = {
        "architecture": "Architecture",
        "event_bus": "Event Bus",
        "memory": "Memory",
        "plugin_manager": "Plugin Manager",
        "capability_registry": "Capability Registry",
        "chief_of_staff": "Chief Of Staff",
        "scheduler": "Scheduler",
        "security": "Sécurité",
        "observability": "Observabilité",
        "performance": "Performance",
    }
    for i, (name, _) in enumerate(AUDIT_FILES.items(), 1):
        if name not in results:
            continue
        score = results[name].get("score", 0)
        weight = WEIGHTS[name]
        weighted = round(score * weight / 100, 1)
        status = "✅ PASS" if score >= 90 else ("⚠️ WARN" if score >= 70 else "❌ FAIL")
        lines.append(f"| {i} | {audit_names_fr[name]} | **{score}**/100 | {weight}% | {weighted} | {status} |")
    lines.append(f"| | **GLOBAL** | **{global_score}**/100 | 100% | **{global_score}** | {'✅ PASS' if global_score >= 90 else '❌ FAIL'} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    if global_score >= 90:
        lines.append("✅ **AUDIT RÉUSSI** — Le Kernel V1 est prêt pour la Phase 3.")
    elif global_score >= 75:
        lines.append(f"⚠️ **AUDIT PARTIEL** — Score {global_score}/100. Phase 3 possible mais avec debt technique à adresser en V2.")
    else:
        lines.append(f"❌ **AUDIT ÉCHOUÉ** — Score {global_score}/100. La Phase 3 ne doit pas commencer tant que les problèmes critiques ne sont pas résolus.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Problèmes critiques
    if critical_issues:
        lines.append("## 🚨 Problèmes critiques (à résoudre avant Phase 3)")
        lines.append("")
        for i, issue in enumerate(critical_issues, 1):
            lines.append(f"### {i}. [{issue['audit']}] {issue.get('category', issue.get('test', 'N/A'))}")
            lines.append("")
            lines.append(f"**{issue.get('message', '')}**")
            lines.append("")
            if "details" in issue:
                lines.append("```")
                lines.append(json.dumps(issue["details"], indent=2, default=str)[:500])
                lines.append("```")
                lines.append("")
        lines.append("---")
        lines.append("")

    # Warnings
    if warning_issues:
        lines.append("## ⚠️ Warnings (dette technique V2)")
        lines.append("")
        lines.append("| Audit | Catégorie | Message |")
        lines.append("|-------|-----------|---------|")
        for issue in warning_issues:
            msg = issue.get("message", "")[:120]
            lines.append(f"| {issue['audit']} | {issue.get('category', issue.get('test', 'N/A'))} | {msg} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Détails par audit
    lines.append("## Détails par audit")
    lines.append("")
    for name, _ in AUDIT_FILES.items():
        if name not in results:
            continue
        r = results[name]
        lines.append(f"### AUDIT — {audit_names_fr[name]} (score: {r.get('score', 0)}/100)")
        lines.append("")
        tests = r.get("tests", [])
        passed = sum(1 for t in tests if t.get("passed"))
        lines.append(f"**Tests**: {passed}/{len(tests)} réussis")
        lines.append("")
        lines.append("| Test | Statut | Détails clés |")
        lines.append("|------|--------|--------------|")
        for t in tests:
            test_name = t.get("test", "N/A")
            status = "✅" if t.get("passed") else "❌"
            details = []
            for k, v in t.items():
                if k not in {"test", "passed"} and not isinstance(v, (list, dict)):
                    details.append(f"{k}={v}")
            detail_str = " · ".join(details[:3])
            lines.append(f"| {test_name} | {status} | {detail_str} |")
        lines.append("")

    # Recommandations V2
    lines.append("---")
    lines.append("")
    lines.append("## Roadmap V2 (post-Phase 3)")
    lines.append("")
    lines.append("Basé sur les problèmes identifiés, voici les priorités V2 :")
    lines.append("")
    lines.append("### 🔴 Priorité 1 (critique — bloquer avant prod)")
    lines.append("")
    lines.append("1. **Filesystem sandbox** — path traversal critique")
    lines.append("   - Configurer `filesystem.root` dans config")
    lines.append("   - `Path.resolve()` + check prefix avant toute opération")
    lines.append("   - Per-mission scratch directory")
    lines.append("")
    lines.append("2. **Memory corruption recovery** — wrap `_init_db` dans try/except")
    lines.append("   - Backup automatique du DB corrompu")
    lines.append("   - Recreate schema si corruption détectée")
    lines.append("")
    lines.append("3. **Validation Pipeline complet** — 8 étapes au lieu de 4")
    lines.append("   - Tests (pytest + Playwright)")
    lines.append("   - Repair loop (max 3 retries)")
    lines.append("   - Final validation + Delivery gate")
    lines.append("")
    lines.append("### 🟡 Priorité 2 (important — avant scale)")
    lines.append("")
    lines.append("4. **Scheduler avec retry + timeout built-in**")
    lines.append("   - `tenacity` pour retries (exponential backoff)")
    lines.append("   - `asyncio.wait_for(default 30s)` dans `_execute_task`")
    lines.append("   - PriorityQueue optionnelle")
    lines.append("")
    lines.append("5. **Observability** — metrics + structured logs")
    lines.append("   - `prometheus_client` : 10+ compteurs/histogrammes")
    lines.append("   - Log formatter JSON avec correlation IDs")
    lines.append("   - Endpoint `/metrics` + `/health`")
    lines.append("")
    lines.append("6. **Memory async** — SQLite → aiosqlite")
    lines.append("   - Ne bloque plus l'event loop")
    lines.append("   - Prépare migration PostgreSQL (interface inchangée)")
    lines.append("")
    lines.append("7. **LLM output sanitization**")
    lines.append("   - Allowlist de (capability, method) autorisées pour le LLM")
    lines.append("   - Schema validation des params par (capability, method)")
    lines.append("   - Détection de prompt injection (regex + LLM-as-judge)")
    lines.append("")
    lines.append("### 🟢 Priorité 3 (long terme)")
    lines.append("")
    lines.append("8. **Event Bus → NATS JetStream** (persistance + replay)")
    lines.append("9. **Memory → PostgreSQL** (asyncpg)")
    lines.append("10. **Plugin sandboxing** — subprocess/conteneur pour plugins non sûrs")
    lines.append("11. **Plugin signing** — GPG/sigstore pour l'approvisionnement")
    lines.append("12. **Builder** — extraction des patterns répétitifs observés en Phase 3+")
    lines.append("")
    lines.append("### Composants identifiés comme inutiles en V1")
    lines.append("")
    lines.append("Après audit, aucun composant V1 n'est inutile. Tous les 8 composants Kernel et les 10 plugins sont justifiés et utilisés.")
    lines.append("")
    lines.append("### Couplages identifiés")
    lines.append("")
    lines.append("- **Aucun couplage critique** — le découplage Kernel↔Plugins est exemplaire (0 violation)")
    lines.append("- **Couplage mineur** : `MissionEngine` dépend de `DecisionEngine` qui dépend de `Planner` qui dépend de `LLMPlugin`. Acceptable en V1 car le Planner a besoin d'un LLM pour fonctionner.")
    lines.append("")
    lines.append("### Bugs identifiés")
    lines.append("")
    lines.append("- **Aucun bug bloquant** dans le code V1.")
    lines.append("- **Bug de robustesse** : `Memory._init_db` peut crasher si le DB est corrompu (Pas de try/except).")
    lines.append("- **Bug de sécurité** : `FilesystemPlugin` permet le path traversal (pas de sandbox).")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(f"**Score global : {global_score}/100**")
    lines.append("")
    if global_score >= 90:
        lines.append("✅ Le Kernel V1 constitue une base solide. Phase 3 autorisée.")
    elif global_score >= 75:
        lines.append(f"⚠️ Le Kernel V1 est fonctionnel mais avec debt technique. Score {global_score}/100 — sous le seuil de 90 requis.")
        lines.append("")
        lines.append("**Recommandation** :")
        lines.append("- Corriger les 3 problèmes critiques (filesystem sandbox, memory corruption, validation pipeline)")
        lines.append("- Réexécuter l'audit")
        lines.append("- Si score ≥ 90 → Phase 3")
        lines.append("- Sinon → itérer sur les warnings")
    else:
        lines.append(f"❌ Le Kernel V1 n'est pas prêt. Score {global_score}/100.")
        lines.append("")
        lines.append("**Action requise** : résoudre tous les problèmes critiques avant toute Phase 3.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Rapport généré automatiquement par `audit/scripts/compile_report.py`*")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines))
    print(f"Report written to: {REPORT_PATH}")
    print(f"\n=== GLOBAL SCORE: {global_score}/100 ===")
    print(f"Tests: {passed_tests}/{total_tests} passed")
    print(f"Critical: {len(critical_issues)} · Warnings: {len(warning_issues)} · Infos: {len(info_issues)}")


if __name__ == "__main__":
    generate_report()
