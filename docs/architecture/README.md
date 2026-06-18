# ALTEREGO OS — Architecture documentation

This folder contains the architectural reports and diagrams produced during the design phase.

## Documents

- **[AI_Operating_System_Architecture_Report.pdf](AI_Operating_System_Architecture_Report.pdf)** — full architecture report (V3.0, 102 pages) covering:
  - Vision & principles (90/10 OSS/proprietary, Kernel-first)
  - 232 GitHub repositories catalog (16 categories)
  - 3-level architecture (Kernel / Bridges / Departments-as-config)
  - Cognitive Orchestrator (8-step decision pipeline)
  - Builder Meta-System (4 Engines + 2 Managers — long-term vision)
  - Validation Pipeline (8 stages)
  - Phasing 0-7 (Kernel-first strict)

## Diagrams

| # | File | Description |
|---|------|-------------|
| 01 | `01_architecture.png` | Global architecture (6 layers) |
| 02 | `02_dependencies.png` | Open source dependencies map |
| 03 | `03_pipeline.png` | Validation Pipeline 8 steps |
| 04 | `04_eventbus.png` | Event Bus catalog |
| 05 | `05_knowledge_graph.png` | Knowledge Graph schema |
| 06 | `06_roadmap.png` | Original 6-phase roadmap |
| 07 | `07_three_levels.png` | 3-level architecture V2 |
| 08 | `08_cognitive_orchestrator.png` | Cognitive Orchestrator 9 steps |
| 09 | `09_plugins_tree.png` | Repository tree structure |
| 10 | `10_ratio_90_10.png` | 90/10 OSS ratio + red lines |
| 11 | `11_phasing_0_7.png` | V2 phasing 0-7 Kernel-first |
| 12 | `12_brain_organs.png` | Brain/organs biological metaphor |
| 13 | `13_catalog.png` | Catalog auto-consumption |
| 14 | `14_meta_loop.png` | Builder ↔ OS meta-loop V3 |
| 15 | `15_builder_repo.png` | alterego-builder/ structure V3 |
| 16 | `16_install_engine.png` | Install Engine 9-step pipeline |
| 17 | `17_upgrade_engine.png` | Upgrade Engine nightly 8-step |
| 18 | `18_intelligence_engine.png` | Intelligence Engine composition |

## Note on V1 implementation

The V1 implementation (in `alterego/` directory at the repo root) follows
a **pragmatic subset** of this architecture:

- V1 implements only the 8 Kernel components (no Builder yet — long-term)
- V1 implements only 10 plugins (not all 28 from the report)
- V1 uses SQLite + in-process asyncio (V2 will switch to PostgreSQL + NATS)
- V1 implements 4 of 8 validation steps (V2 will complete the pipeline)

The Builder (sections 32-36 of the report) is **intentionally deferred**.
Per the V1 discipline: "The Builder is a consequence of experience, not a starting point."
