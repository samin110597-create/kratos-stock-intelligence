# Real Kratos framework integration — deliberate separation

Upstream: https://github.com/aiappsgbb/kratos-agent (the project examined October 17, 2026).

Upstream is a Microsoft Foundry + GitHub Copilot SDK + Azure-oriented reference architecture. It includes hosted-agent infrastructure, a FastAPI backend and a Next.js frontend. Installing its entire stack is neither required nor economically justified for an initial free private stock research app.

The present repository has an **honestly labeled Kratos-inspired orchestrator** (`kratos/engine.py`), which composes deterministic components. It is not a fork, not connected to Foundry, and does not use Copilot SDK or MCP yet. This distinction matters: avoid marketing generic rules as "Kratos AI predictive accuracy".

For Astra:

1. Audit upstream license, current security advisories, auth requirements, MCP registration API, and runtime cost.
2. Decide between portable local MCP tools serving market, technical, fundamental and audit computations versus a full Foundry deployment. Prefer portable tools with no mandatory Azure subscription.
3. **The agent may explain analyses but must never invent numeric levels**. It must call deterministic verified tools, receive provenance/timestamps, and abstain on failure.
4. Production orchestration should add an LLM explanation boundary, typed JSON schemas, tool permissions and read-only defaults; order execution is out of scope.
5. Require fully auditable calculations and frozen predictions, and automatically test end-to-end outputs against known fixtures.
6. Do not modify or import the Q-State project; compare both on identical out-of-sample data only after explicit user approval.
