# CHANGELOG — ALTEREGO OS

## V2.1 (2026-06-18) — Connecté à la vie réelle

### Added
- **Digital Twin V2** (Étape 1) — graphe de connaissances complet de l'utilisateur
  - 17 types d'entités : identity, company, project, repository, server, application, document, client, goal, habit, calendar_event, skill, preference, history, roadmap, decision, relation
  - Relations typées entre entités (belongs_to, hosted_on, depends_on, created_by...)
  - `add_relation()`, `get_relations()`, `get_related()` pour naviguer le graphe
  - Convenience methods : `add_company()`, `add_project()`, `add_server()`, `add_application()`, `add_decision()`, `add_skill()`, `add_roadmap()`, `add_calendar_event()`, `add_habit()`
  - `describe()` affiche le profil complet
  - CLI: `alterego twin-v2`

- **Life Timeline** (Étape 4) — historique vivant d'ALTEREGO
  - Enregistre tous les événements importants (mission_created, mission_completed, goal_reached, error, decision, learning, habit, preference)
  - `record()`, `get_events()`, `get_today()`, `get_recent()`, `get_critical()`, `summary()`
  - Filtrage par type, sévérité, plage de dates
  - CLI: `alterego timeline summary|today|recent|critical`

- **Long Term Memory** (Étape 3) — raisonnement sur plusieurs mois
  - `search_conversations()`, `search_missions()`, `search_decisions()` — recherche par mot-clé
  - `compare_periods()` — comparer deux périodes (missions, conversations, succès)
  - `detect_trends()` — détecter tendances (volume, succès, activité)
  - `find_old_idea()` — retrouver une ancienne idée/discussion/décision
  - `historical_summary()` — synthèse sur N jours
  - CLI: `alterego remember "SQLite"`

- **Unified Workspace** (Étape 2) — interface unique pour tous les outils
  - `overview()` — tous les plugins connectés, santé, capacités
  - `status()` — santé de chaque connexion
  - `list_resources()` — ressources GitHub, Docker, filesystem, Digital Twin
  - `search()` — recherche cross-outils
  - `describe()` — vue humaine lisible
  - CLI: `alterego workspace`

### Changed
- Kernel expose désormais **22 composants** (18 + DigitalTwinV2 + LifeTimeline + LongTermMemory + UnifiedWorkspace)
- `kernel_factory.py` câble les 4 nouveaux composants
- CLI: 4 nouvelles commandes (`timeline`, `workspace`, `remember`, `twin-v2`)

### Tested
- Digital Twin V2 : 9 entités créées + 3 relations → graphe navigable ✓
- Life Timeline : 4 événements enregistrés avec sévérités → résumé généré ✓
- Long Term Memory : recherche "SQLite" → 2 conversations + 1 décision retrouvées ✓
- Trends : increasing/improving détectés ✓

### Components count
- **22 Kernel components**
- **11 Departments**
- **10 Plugins**
- **75 tests unitaires**

---

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
