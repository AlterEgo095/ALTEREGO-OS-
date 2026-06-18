# ALTEREGO — Ton cerveau numérique externe

> Un collaborateur numérique autonome qui comprend tes objectifs, choisit lui-même les meilleurs outils disponibles, exécute les tâches à ta place, apprend de tes habitudes et te restitue uniquement le résultat.

ALTEREGO n'est pas un GitHub Copilot géant. Ce n'est pas un AutoGPT. Ce n'est pas un CrewAI amélioré.

**ALTEREGO est ton alter ego numérique** — un système qui pilote l'ensemble de ton environnement numérique (projets, serveurs, documents, recherches, communications, automatisations) tout en restant sûr, contrôlable et évolutif.

## La boussole

Chaque nouvelle fonctionnalité doit répondre à une seule question :

> **Est-ce que cela rend mon Alter Ego plus capable de penser, décider et agir à ma place ?**

Si la réponse est **oui**, elle mérite d'être intégrée. Si la réponse est **non**, même si la technologie est impressionnante, elle risque de t'éloigner de la vision initiale.

## Architecture (V1.1 — 11 composants Kernel)

```
                    TOI
                     │
            Tu écris ou tu parles
                     │
                     ▼
           ALTEREGO (Chief Of Staff)
                     │
         Comprend ton intention réelle
                     │
                     ▼
           Décompose automatiquement  (Decision Engine + Planner)
                     │
                     ▼
      Choisit les meilleurs outils   (Capability Registry)
                     │
                     ▼
         Évalue le risque            (Policy Engine)
                     │
                     ▼
         Mesure la confiance         (Confidence Engine)
                     │
                     ▼
      Exécute toutes les missions    (Mission Engine + Plugin Manager)
                     │
                     ▼
      Mémorise et apprend de toi     (Learning Engine + Memory)
                     │
                     ▼
      Revient uniquement avec le résultat
```

### Les 5 piliers

1. **Chief Of Staff** — Le seul interlocuteur. Toujours.
2. **Memory** — Te connaître (projets, habitudes, serveurs, préférences, conversations). Devient progressivement ton cerveau numérique.
3. **Capability Engine** — Ne choisit jamais un plugin. Choisi une **capacité** ("développer du code", "naviguer le web", "envoyer un email"). Le système trouve automatiquement le meilleur outil.
4. **Mission Engine** — Transforme "Construis-moi une plateforme" en un DAG de 9 étapes (Recherche → Architecture → Backend → Frontend → Docker → Tests → Documentation → Déploiement → Monitoring) sans intervention.
5. **Learning Engine** — Après chaque mission : Mission → Résultat → Feedback → Mémoire → Amélioration. Ton Alter Ego devient meilleur chaque semaine.

### Les 3 engines de sécurité (V1.1)

6. **Policy Engine** — Décide pour chaque action : Peut modifier ? Peut supprimer ? Peut déployer ? Peut payer ? Peut envoyer un email ? Peut redémarrer un VPS ?
   - `allow` → exécution automatique
   - `require_approval` → validation utilisateur obligatoire
   - `deny` → jamais exécuté (ex: `rm -rf /`, `DROP DATABASE`, `curl | sh`)

7. **Confidence Engine** — Score 0-100 par mission :
   - `> 95` → automatique
   - `80-95` → validation recommandée
   - `< 80` → validation obligatoire

8. **Learning Engine** — Capture le feedback, infère les préférences, améliore les scores de confiance futurs.

### Departments (V1.1 — config, pas code)

```
departments/
├── engineering.yaml      ← Software engineering (GitHub, Docker, code)
├── research.yaml         ← Research (web, PDFs, knowledge synthesis)
├── infrastructure.yaml   ← Infra (VPS, Docker, deployments, monitoring)
└── personal.yaml         ← Personal (email, telegram, calendar, documents)
```

Engineering est juste un department parmi d'autres. Ajouter un department "finance" ou "education" = créer un fichier YAML. **Aucune modification du Kernel.**

## Quick start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env: set OPENAI_API_KEY or OLLAMA_BASE_URL

# 3. Set filesystem sandbox (SECURITY — important!)
export ALTEREGO_FS_ROOT=/path/to/your/workspace

# 4. Run
alterego chat
```

## V1.1 Plugins (10)

| Plugin | Capability | What it does |
|--------|------------|-------------|
| github | `github` | Clone, PRs, issues, commits |
| docker | `docker` | Containers, logs, stats, build |
| ssh | `ssh` | Remote exec, scp, health checks |
| browser | `browser` | Playwright automation |
| filesystem | `filesystem` | Read/write/list (sandboxed) |
| postgres | `database.sql` | SQL queries |
| mongo | `database.nosql` | MongoDB operations |
| llm | `llm.chat` | LLM chat (OpenAI/Ollama) |
| email | `email` | Send via SMTP |
| telegram | `telegram` | Bot notifications |

**Règle** : aucun autre plugin ne sera développé tant qu'un besoin réel n'est pas identifié.

## Phasing

- **Phase 0** — Architecture physique du dépôt ✓
- **Phase 1** — Kernel 8 composants ✓
- **Phase 1.1** — Policy + Confidence + Learning + Departments ✓
- **Phase 2** — 10 plugins V1 ✓
- **Phase 2.9** — Real world validation (8 scénarios) ✓ (7/8 passés)
- **Phase 3A** — Daily Operations (VPS, documents, recherches, communications) ← *prochaine*
- **Phase 3B** — Software Engineering Department (avec validation humaine obligatoire)

## Discipline fondamentale

1. **Ne jamais développer une fonctionnalité qui existe déjà en open source.**
2. **Ne jamais intégrer un projet open source sans un besoin réel.**
3. **Toute intégration doit être justifiée par un cas d'usage concret.**
4. **L'humain garde toujours le contrôle** — aucune action irréversible sans validation explicite.
5. **Le Builder est une conséquence de l'expérience, pas un point de départ.**

## Ce qu'ALTEREGO n'est pas

- ❌ Un GitHub Copilot géant
- ❌ Un AutoGPT
- ❌ Un CrewAI amélioré
- ❌ Un simple chatbot

## Ce qu'ALTEREGO est

- ✅ Ton cerveau numérique externe
- ✅ Un collaborateur autonome qui apprend de toi
- ✅ Un orchestrateur de tes outils numériques
- ✅ Un système qui te restitue uniquement le résultat

## License

MIT — see [LICENSE](LICENSE).
