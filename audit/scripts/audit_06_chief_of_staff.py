"""AUDIT 6 — Chief Of Staff.

Teste 100 requêtes naturelles différentes.
Vérifie que le CoS ne leak jamais :
- noms de plugins
- noms de bridges
- architecture interne
- départements

Il doit rester conversationnel.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from alterego.kernel.base import BasePlugin, BridgeSpec, PluginSpec
from alterego.kernel import (
    CapabilityRegistry, CapabilitySpec, ChiefOfStaff, DecisionEngine,
    InProcessEventBus, MissionEngine, Planner, PluginManager, SQLiteMemory,
)


class MockLLM(BasePlugin):
    """Mock LLM that always plans a single llm.chat task that responds conversationally."""
    spec = BridgeSpec(name="mock_llm", capabilities=["llm.chat"])
    plugin_spec = PluginSpec(name="mock_llm", capabilities=["llm.chat"], priority=10)

    async def initialize(self): pass
    async def shutdown(self): pass
    async def health(self): return True
    def methods(self): return ["chat"]

    async def call(self, method: str, params: dict[str, Any]) -> Any:
        system = params.get("system", "")
        user = params.get("user", "")

        if "extract the user's intent" in system:
            return {"content": "Help the user"}

        if "Available capabilities" in system:
            # Always produce a simple plan that just answers via llm.chat
            import json as j
            plan = {"tasks": [{"step": 1, "description": "Respond", "capability": "llm.chat", "method": "chat", "params": {"system": "You are a helpful assistant.", "user": user}}]}
            return {"content": j.dumps(plan)}

        # Default: respond conversationally
        return {"content": f"Bien sûr, je peux vous aider avec : {user[:80]}"}


# 100 natural-language requests
TEST_REQUESTS = [
    "Bonjour", "Salut ALTEREGO", "Hello", "Coucou", "Hey",
    "Que peux-tu faire ?", "Qui es-tu ?", "Présente-toi", "Comment ça marche ?", "Aide-moi",
    "Analyse ce dépôt GitHub", "Clone ce repo", "Fais une PR", "Corrige ce bug", "Lance les tests",
    "Démarre ce conteneur", "Stop ce conteneur", "Vérifie mon serveur", "Déploie cette app", "Redémarre Docker",
    "Lis ce fichier", "Écris ce fichier", "Crée un dossier", "Liste les fichiers", "Supprime ce fichier",
    "Ouvre ce site web", "Clique sur ce bouton", "Prends une capture d'écran", "Scrape cette page", "Remplis ce formulaire",
    "Envoie un email", "Notifie-moi sur Telegram", "Envoie un message à mon équipe", "Préviens-moi si ça plante", "Alarme si CPU > 90%",
    "Quelle est la météo ?", "Quelle heure est-il ?", "Quel jour sommes-nous ?", "Calcule 2+2", "Traduis bonjour en anglais",
    "Résume ce texte", "Génère un poème", "Écris un haïku", "Code-moi une fonction", "Explique-moi Python",
    "Compare React et Vue", "Donne-moi une recette", "Raconte une blague", "Conseille-moi un film", "Recommande un livre",
    "Comment allez-vous ?", "Ça va ?", "Tu es là ?", "Tu dors ?", "Tu comprends le français ?",
    "Quelles sont tes limites ?", "Es-tu conscient ?", "Tu rêves ?", "Tu mémorises quoi ?", "Tu apprends ?",
    "Vérifie l'état du système", "Affiche les métriques", "Montre les logs", "Quels plugins sont chargés ?", "Quelles capacités as-tu ?",
    "Configure Telegram", "Configure SMTP", "Ajoute une clé SSH", "Génère un token", "Change mon mot de passe",
    "Planifie une sauvegarde", "Restore la dernière sauvegarde", "Archive ces logs", "Compresse ce dossier", "Nettoie les vieux fichiers",
    "Crée un projet", "Initialise un repo", "Setup le CI/CD", "Prépare un environnement de dev", "Documente ce code",
    "Quelle est la version de Docker ?", "Quelle est ma RAM ?", "Combien de CPU ?", "Espace disque restant ?", "Quels process tournent ?",
    "Analyse ces logs d'erreur", "Trouve la cause de ce crash", "Optimise cette requête SQL", "Index cette table", "Vacuum la base",
    "Appelle l'API GitHub", "Récupère mes issues", "Liste mes repos", "Vérifie mon rate limit", "Crée un gist",
]


# Forbidden terms — the CoS should NEVER leak these to the user
FORBIDDEN_TERMS = [
    "BaseBridge", "BasePlugin", "PluginManager", "EventBus", "InProcessEventBus",
    "SQLiteMemory", "CapabilityRegistry", "MissionEngine", "DecisionEngine",
    "Planner", "ChiefOfStaff",  # internal class names
    "alterego.kernel", "alterego.plugins",  # module paths
    "plugin_spec", "BridgeSpec", "PluginSpec", "CapabilitySpec",
    "MissionStatus", "entry_points",
    "Department", "Departments",  # not even a concept yet
    "Traceback", "Exception", "RuntimeError",  # raw error leaks
    "import alterego", "from alterego",
]


async def run_test():
    results = {"audit": "chief_of_staff", "tests": [], "issues": [], "score": 0}
    print("=" * 70)
    print("AUDIT 6 — CHIEF OF STAFF")
    print("=" * 70)

    # Build kernel
    with tempfile_dir() as tmp:
        memory = SQLiteMemory(Path(tmp) / "test.db")
        bus = InProcessEventBus()
        pm = PluginManager()
        llm = MockLLM()
        await llm.initialize()
        pm._plugins["mock_llm"] = llm
        pm._by_capability["llm.chat"] = ["mock_llm"]

        cap_reg = CapabilityRegistry()
        cap_reg.register(CapabilitySpec(name="llm.chat", description="LLM chat"))
        planner = Planner(cap_reg, llm)
        decision = DecisionEngine(memory, planner, llm)
        mission_engine = MissionEngine(memory, bus, decision, pm)
        cos = ChiefOfStaff(mission_engine, memory, bus)

        # Run 100 requests
        leaked_count = 0
        leaked_examples = []
        non_conversational_count = 0

        for i, req in enumerate(TEST_REQUESTS):
            try:
                response = await cos.chat(req)
                response_str = str(response)

                # Check for forbidden terms
                leaked = [term for term in FORBIDDEN_TERMS if term in response_str]
                if leaked:
                    leaked_count += 1
                    if len(leaked_examples) < 5:
                        leaked_examples.append({
                            "request": req,
                            "leaked_terms": leaked,
                            "response_excerpt": response_str[:200],
                        })

                # Check that response is conversational (not a raw dict/JSON/stack trace)
                if response_str.startswith("{") or response_str.startswith("[") or "Traceback" in response_str:
                    non_conversational_count += 1

            except Exception as e:
                # The CoS should never crash on user input
                results["issues"].append({
                    "severity": "critical",
                    "test": f"request_{i}",
                    "message": f"CoS crashed on '{req}': {e}",
                })

    # Aggregate
    total = len(TEST_REQUESTS)
    no_leak_count = total - leaked_count
    conversational_count = total - non_conversational_count

    results["tests"].append({
        "test": "no_internal_leak",
        "total_requests": total,
        "leaked_responses": leaked_count,
        "no_leak_responses": no_leak_count,
        "leaked_examples": leaked_examples,
        "passed": leaked_count == 0,
    })

    results["tests"].append({
        "test": "always_conversational",
        "total_requests": total,
        "non_conversational_responses": non_conversational_count,
        "passed": non_conversational_count == 0,
    })

    results["tests"].append({
        "test": "no_crash_on_user_input",
        "total_requests": total,
        "crashes": sum(1 for i in results["issues"] if i.get("test", "").startswith("request_")),
        "passed": sum(1 for i in results["issues"] if i.get("test", "").startswith("request_")) == 0,
    })

    # Print summary
    print(f"\n── Summary ──")
    print(f"  Total requests: {total}")
    print(f"  No-leak responses: {no_leak_count}/{total} {'✓' if no_leak_count == total else '✗'}")
    print(f"  Conversational: {conversational_count}/{total} {'✓' if conversational_count == total else '✗'}")
    print(f"  Crashes: {sum(1 for i in results['issues'] if i.get('test', '').startswith('request_'))} {'✓' if not any(i.get('test', '').startswith('request_') for i in results['issues']) else '✗'}")

    if leaked_examples:
        print(f"\n── Leaked examples ──")
        for ex in leaked_examples:
            print(f"  Request: {ex['request']}")
            print(f"  Leaked: {ex['leaked_terms']}")
            print(f"  Response: {ex['response_excerpt'][:100]}...")

    # Score
    passed = sum(1 for t in results["tests"] if t.get("passed"))
    total_tests = len(results["tests"])
    score = int(passed / total_tests * 100) if total_tests else 0
    # Subtract for each leaked response
    score = max(0, score - leaked_count * 2)
    score = max(0, score - non_conversational_count * 2)
    results["score"] = score

    print(f"\nTESTS PASSED: {passed}/{total_tests}")
    print(f"SCORE: {score}/100")

    out = Path(__file__).resolve().parent.parent / "results" / "audit_06_chief_of_staff.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to: {out}")


from contextlib import contextmanager
import tempfile

@contextmanager
def tempfile_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


if __name__ == "__main__":
    asyncio.run(run_test())
