# CHANGELOG — ALTEREGO OS

## V2.0 (2026-06-18) — ALTEREGO devient un collaborateur vivant

### Added
- **Goal Engine** (Étape 1) — l'utilisateur exprime des objectifs, pas des tâches
  - Goal → Objectives → Projects → Missions → Tasks → Capabilities → Plugins → Execution → Validation → Learning → Memory
  - Décomposition automatique par LLM (2-5 objectifs par goal)
  - Suivi persistant (status: active/paused/completed/abandoned)
  - Progression mesurée (fraction d'objectifs complétés)
  - CLI: `alterego goal create "Mon objectif"`, `alterego goal list`, `alterego goal progress`

- **Daily Assistant** (Étape 2) — rapports automatiques
  - Morning Brief (activité récente, objectifs actifs, initiatives en attente)
  - Evening Report (missions du jour, réussites/échecs, progrès objectifs)
  - Weekly Review (stats hebdomadaires, taux de succès, tendances)
  - Progress Report (rapport détaillé sur un objectif)
  - CLI: `alterego brief`, `alterego evening`, `alterego weekly`

- **Context Engine** (Étape 3) — contexte permanent
  - Active goals, active project, active server
  - Recent conversations (continuité)
  - User preferences
  - Known projects and servers
  - Recent missions
  - `get_context_summary()` injecté dans le Decision Engine
  - CLI: `alterego context`

### Changed
- Kernel `__init__.py` expose désormais **18 composants** (15 + GoalEngine + DailyAssistant + ContextEngine)
- `kernel_factory.py` câble les 3 nouveaux engines
- CLI: 5 nouvelles commandes (`goal`, `brief`, `evening`, `weekly`, `context`)

### Components count
- **18 Kernel components**
- **11 Departments**
- **10 Plugins**
- **75 tests unitaires**

---

## V1.3 (2026-06-18) — Initiative Engine + Digital Twin

### Added
- **Initiative Engine** (Règle 10) — ALTEREGO ne répond plus seulement aux ordres, il détecte proactivement :
  - Missions bloquées (stale missions > 5 min)
  - Patterns d'échec récurrents (même capacité qui échoue 3+ fois)
  - Habitudes utilisateur (langue détectée, patterns de conversation)
  - Lacunes de connaissances (pas de serveurs/projets enregistrés)
  - Croissance mémoire excessive (> 10 000 enregistrements)
  - 5 détecteurs, scan à la demande, auto-création de missions (désactivé par défaut)
- **Digital Twin** (Règle 9) — ALTEREGO apprend à connaître l'utilisateur :
  - Profil structuré (préférences, projets, serveurs, objectifs, habitudes)
  - Inférence automatique (langue, méthode de travail)
  - `register project/server/objective` via CLI
  - `twin describe` affiche ce qu'ALTEREGO sait de vous
  - Couche au-dessus de Memory (pas de nouvelle base de données)
- CLI : `alterego initiatives`, `alterego twin`, `alterego register`

### Changed
- Kernel `__init__.py` expose désormais 15 composants (13 + InitiativeEngine + DigitalTwin)
- `kernel_factory.py` câble InitiativeEngine + DigitalTwin

### Components count
- **15 Kernel components** (ChiefOfStaff, MissionEngine, DecisionEngine, Planner, Memory, EventBus, CapabilityRegistry, PluginManager, PolicyEngine, ConfidenceEngine, LearningEngine, DepartmentLoader, ValidationPipeline, InitiativeEngine, DigitalTwin)
- **11 Departments** (engineering, research, infrastructure, personal, marketing, education, automation, finance, content, monitoring, security)
- **10 Plugins** (github, docker, ssh, browser, filesystem, postgres, mongo, llm, email, telegram)
- **75 tests unitaires**

---

## V1.2 (2026-06-18) — Validation Pipeline + 11 Departments

### Added
- **Validation Pipeline** (8 étapes obligatoires) : LLM → Critic → Validator → Security → Tests → Repair → Final → Delivery
  - Détecte secrets (sk-*, ghp_*, AKSA*, private keys)
  - Détecte patterns dangereux (rm -rf, DROP DATABASE, eval, exec, XSS)
  - Repair loop (max 3 tentatives avec feedback LLM)
  - Delivery gate (score >= 60% requis)
  - Intégré au MissionEngine (chaque sortie LLM validée)
- **7 departments supplémentaires** : marketing, education, automation, finance, content, monitoring, security
- Missions réelles validées avec GLM-4 (fichier créé, validation 100%)

---

## V1.1 (2026-06-18) — Policy + Confidence + Learning + Departments

### Added
- **Policy Engine** — 17 règles par défaut + patterns interdits (rm -rf /, DROP DATABASE, curl|sh)
  - allow / require_approval / deny par (capability, method, params)
- **Confidence Engine** — score 0-100 par mission (5 facteurs : plan validity, length, capability avail, historical success, policy risk)
- **Learning Engine** — capture feedback post-mission, infère préférences, stats par capacité
- **Department Loader** — 4 departments YAML initiaux (engineering, research, infrastructure, personal)
- **Software Engineering Department** — pipeline safe avec HumanApprovalGate bloquant
- **Kernel Factory** — wiring propre des 13 composants
- Filesystem sandbox (ALTEREGO_FS_ROOT) — path traversal protection
- Memory corruption recovery (backup + recreate)
- LLM plugin v0.2 (pure httpx, no SDK) + z-ai CLI fallback
- Planner V1.1 (JSON strict prompt, markdown fence stripping, temperature 0.1)

---

## V1.0 (2026-06-18) — Kernel initial + 10 plugins

### Added
- **8 Kernel components** : ChiefOfStaff, MissionEngine, DecisionEngine, Planner, Memory (SQLite), EventBus (asyncio), CapabilityRegistry, PluginManager
- **10 Plugins** : github, docker, ssh, browser, filesystem, postgres, mongo, llm, email, telegram
- **Base contracts** : BaseBridge, BasePlugin, BaseCapability (ABCs)
- **CLI** : `alterego run/chat/plugins/health`
- **75 tests unitaires** (base, event_bus, memory, capability_registry, plugin_manager, planner, filesystem, end_to_end)
- **10 audits** validés (score global 91/100)
- **Phase 2.9** : 7/8 scénarios réels validés (VPS, GitHub, PDF, Web, Memory, continuous)
