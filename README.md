<div align="center">

# 🤖 AI Software Engineering Agent

### Production-Style Autonomous Software Engineering with Human Control

An AI-powered software engineering agent that can inspect existing codebases, plan implementation work, prepare controlled code changes, run automated verification, analyze failures, self-correct safely, and require explicit human approval before repository writes.

<br />

![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Production-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/Nginx-Reverse_Proxy-009639?style=for-the-badge&logo=nginx&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLM_API-F55036?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

<br />

## Quick Links

<p align="center">
  <a href="docs/AI_Software_Engineering_Agent_Final_Technical_Report.pdf"><img src="https://img.shields.io/badge/Technical_Report-PDF-EC1C24?style=for-the-badge&logo=adobeacrobatreader&logoColor=white" alt="Technical Report" /></a>&nbsp;
  <a href="evaluation/"><img src="https://img.shields.io/badge/Evaluation-Suite-2C3E50?style=for-the-badge&logo=pytest&logoColor=white" alt="Evaluation Suite" /></a>&nbsp;
  <a href="http://127.0.0.1:8000/docs"><img src="https://img.shields.io/badge/API_Docs-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="API Docs" /></a>&nbsp;
  <a href="http://127.0.0.1:8080"><img src="https://img.shields.io/badge/Production_UI-React-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="Production UI" /></a>
</p>

<br />

</div>

---

## 📌 Overview

The **AI Software Engineering Agent** is a production-style agentic software engineering system designed to work on existing repositories rather than generate isolated code snippets.

Given a software task, the agent can:

- inspect an existing repository,
- understand relevant code,
- create an implementation plan,
- determine which files require changes,
- generate controlled patches,
- present diffs for human review,
- require explicit approval before writing to disk,
- run automated verification,
- analyze failures,
- prepare correction patches,
- retry through a bounded self-correction loop,
- and stop safely when recovery cannot continue.

The project combines **AI reasoning, secure development tooling, human-in-the-loop controls, persistent state, automated testing, evaluation infrastructure, and Dockerized deployment** in one complete engineering workflow.

---

## ✨ Core Features

### Agentic Software Engineering

The agent dynamically decides how to approach a software task instead of following a fixed single-prompt workflow.

It can:

- inspect repository structure,
- search source code,
- read relevant files,
- reason about implementation changes,
- select files to modify,
- prepare source-code edits,
- and determine how the result should be verified.

---

### 🔍 Repository Intelligence

The agent includes meaningful repository tools such as:

- code search,
- file reading,
- directory listing,
- controlled patch preparation,
- verification execution,
- and repository-safe write operations.

The agent uses repository evidence before preparing changes.

---

### 📝 Evidence-Based Planning

Before code modification, the system generates a structured implementation plan containing:

- task summary,
- relevant files,
- ordered implementation steps,
- verification strategy,
- assumptions,
- risks,
- clarification requirements.

Example workflow:

```text
Task
  ↓
Repository Inspection
  ↓
Relevant File Discovery
  ↓
Implementation Plan
```

---

### 🛡️ Human-in-the-Loop Approval

AI-generated changes are never automatically written to the repository.

The write workflow is deliberately separated:

```text
Prepare Patch
     ↓
Review Diff
     ↓
Human Approval
     ↓
Apply Patch
     ↓
Repository Write
```

Preparing or approving a patch alone does **not** modify repository files.

The repository changes only after an explicitly approved patch is applied.

---

### 📑 Controlled Patch Review

Every proposed change is stored as a pending patch with:

- file path,
- original content,
- proposed content,
- unified diff,
- original SHA-256 hash,
- patch status,
- creation time,
- review time,
- application time.

Supported patch states include:

```text
pending
approved
rejected
applied
stale
```

---

### ✅ Automated Verification

After approved changes are written, the agent runs a controlled verification pipeline.

Current verification steps include:

```text
compileall
    ↓
Ruff
    ↓
pytest
```

Each verification step records:

- command,
- command type,
- exit code,
- stdout,
- stderr,
- timeout state,
- execution duration,
- success status.

Verification history is persisted for later inspection.

---

### 🔄 Bounded Self-Correction

When verification fails, the agent can enter a controlled recovery workflow.

```text
Verification Failed
        ↓
Failure Analysis
        ↓
Correction Proposal
        ↓
Correction Patch Preparation
        ↓
Human Review
        ↓
Approved Correction
        ↓
Reverification
```

Correction attempts are bounded.

The agent cannot retry indefinitely.

When further recovery is unsafe or no attempts remain, the workflow transitions to a safe-stop state.

---

### 🧯 Safe-Stop Behavior

The system is designed to stop safely rather than force a potentially unsafe completion.

Safe-stop behavior is used when:

- correction attempts are exhausted,
- an unsafe repository action is requested,
- a protected path is targeted,
- unsupported binary modification is attempted,
- or the workflow cannot safely continue.

---

### 🔐 Repository Safety Controls

Protected operations include safeguards against:

- `.env` modification,
- Git internal modification,
- `.git/config` access,
- parent-directory traversal,
- cache directory modification,
- unsupported binary writes,
- writes outside the controlled repository,
- stale patch application.

Examples of restricted paths:

```text
.env
.git/
__pycache__/
../outside-file
binary files
```

---

### 💾 Persistent Task State

Application state is persisted in PostgreSQL.

The system stores:

- tasks,
- pending patches,
- verification runs,
- verification steps,
- self-correction sessions,
- correction patch relationships.

This allows the application to recover historical engineering activity after restart.

---

### 🧭 Engineering Control Dashboard

The React interface provides a production-style engineering control workspace.

Main areas include:

- Workspace
- Task History
- New Task
- Implementation Plan
- Patch Review
- Automated Verification
- Self-Correction Control

The interface exposes the complete engineering workflow:

```text
Plan
  →
Review
  →
Verify
  →
Correct
```

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    U[User] --> F[React Frontend]

    F --> N[Nginx Reverse Proxy]

    N --> B[FastAPI Backend]

    B --> A[AI Engineering Agent]

    A --> R[Repository Tools]

    A --> M[Groq Hosted Models]

    R --> W[Controlled Workspace]

    B --> P[(PostgreSQL)]

    A --> V[Verification Pipeline]

    V --> C[compileall]
    V --> L[Ruff]
    V --> T[pytest]

    V --> S[Self-Correction Engine]

    S --> H[Human Approval Gate]

    H --> W
```

---

## 🔁 Complete Agent Workflow

```mermaid
flowchart TD
    A[Software Task] --> B[Inspect Repository]

    B --> C[Search and Read Code]

    C --> D[Generate Implementation Plan]

    D --> E[Prepare Code Patches]

    E --> F[Human Patch Review]

    F -->|Reject| G[Stop / Rework]

    F -->|Approve| H[Apply Approved Patch]

    H --> I[Run Verification]

    I -->|Passed| J[Task Verified]

    I -->|Failed| K[Analyze Failure]

    K --> L[Generate Correction Proposal]

    L --> M[Prepare Correction Patches]

    M --> N[Human Approval]

    N -->|Approve| O[Apply Correction]

    O --> P[Reverify]

    P -->|Passed| J

    P -->|Failed| Q{Attempts Remaining?}

    Q -->|Yes| K
    Q -->|No| R[Safe Stop]
```

---

## 🤖 Model Routing

The backend uses an OpenAI-compatible Groq API.

### Primary Model

```text
openai/gpt-oss-120b
```

### Configurable Fallback

Example:

```text
openai/gpt-oss-20b
```

Fallback models are configured through:

```text
GROQ_FALLBACK_MODELS
```

The model router includes:

- ordered model selection,
- rate-limit awareness,
- per-model cooldown,
- compatibility handling,
- synchronous and asynchronous clients,
- controlled fallback behavior.

The router does not switch models for arbitrary application failures.

---

## 🧰 Technology Stack

### Backend

| Technology | Purpose |
|---|---|
| Python 3.13 | Core backend language |
| FastAPI | REST API |
| OpenAI Agents SDK | Agent orchestration |
| Groq API | LLM inference |
| Pydantic | Structured validation |
| SQLAlchemy | ORM |
| Alembic | Database migrations |
| PostgreSQL | Persistent application state |
| Psycopg | PostgreSQL driver |
| Structlog | Structured logging |
| pytest | Automated testing |
| Ruff | Linting and code validation |

### Frontend

| Technology | Purpose |
|---|---|
| React 19 | User interface |
| TypeScript | Type-safe frontend development |
| Vite | Build and development tooling |
| Nginx | Production frontend server and API proxy |

### Infrastructure

| Technology | Purpose |
|---|---|
| Docker | Containerization |
| Docker Compose | Multi-service orchestration |
| PostgreSQL 17 Alpine | Production database |
| Nginx Alpine | Production frontend |
| Docker Volumes | Persistent database storage |

---

## 📂 Project Structure

```text
AI-Software-Engineering-Agent/
│
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── services/
│   │   └── main.py
│   │
│   ├── migrations/
│   ├── tests/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── alembic.ini
│   └── pyproject.toml
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   ├── App.css
│   │   └── types.ts
│   │
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── .dockerignore
│   ├── package.json
│   └── vite.config.ts
│
├── evaluation/
│   ├── suite.py
│   ├── run_evaluation.py
│   ├── api_client.py
│   └── evaluation tooling
│
├── docs/
│   └── AI_Software_Engineering_Agent_Final_Technical_Report.pdf
│
├── infra/
│
├── scripts/
│
├── workspaces/
│   └── runtime repositories
│
├── .env.example
├── .gitignore
├── docker-compose.yml
├── LICENSE
└── README.md
```

---

# 🚀 Getting Started

## Prerequisites

Install:

- Python 3.13
- Node.js 24+
- npm
- Docker Desktop
- Docker Compose
- Git

A valid Groq API key is also required for AI operations.

---

## 🔧 Environment Configuration

### Root Environment

Create the root environment file:

```powershell
Copy-Item .env.example .env
```

Example:

```env
POSTGRES_DB=software_agent
POSTGRES_USER=software_agent
POSTGRES_PASSWORD=your_secure_password
POSTGRES_PORT=5433

POSTGRES_TEST_DB=software_agent_test
POSTGRES_TEST_USER=software_agent_test
POSTGRES_TEST_PASSWORD=your_test_password
POSTGRES_TEST_PORT=5434

BACKEND_PORT=8000
FRONTEND_PORT=8080
```

---

### Backend Environment

Create:

```powershell
Copy-Item backend\.env.example backend\.env
```

Configure:

```env
APP_NAME=AI Software Engineering Agent
APP_ENV=development
DEBUG=true

API_V1_PREFIX=/api/v1

GROQ_API_KEY=your_groq_api_key
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=openai/gpt-oss-120b

GROQ_FALLBACK_MODELS=openai/gpt-oss-20b

AGENT_MAX_TURNS=12
AGENT_FORMATTER_MAX_TURNS=3

AGENT_EDITOR_MAX_TURNS=14
AGENT_EDITOR_TIMEOUT_SECONDS=180

DATABASE_URL=postgresql+psycopg://software_agent:software_agent@127.0.0.1:5433/software_agent
```

> Never commit real API keys or production `.env` files.

---

# 💻 Local Development

## 1. Start PostgreSQL

From the project root:

```powershell
docker compose up -d postgres
```

Check:

```powershell
docker compose ps
```

---

## 2. Backend Setup

```powershell
cd backend
```

Create environment if needed:

```powershell
py -3.13 -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip

python -m pip install -e ".[dev]"
```

Apply migrations:

```powershell
alembic upgrade head
```

Start API:

```powershell
fastapi dev app/main.py --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

ReDoc:

```text
http://127.0.0.1:8000/redoc
```

---

## 3. Frontend Setup

```powershell
cd frontend
```

Install packages:

```powershell
npm install
```

Run development server:

```powershell
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The Vite development server proxies `/api` requests to the configured backend.

---

# 🐳 Production Docker Deployment

The project includes a complete production-style Docker stack.

### Services

```text
PostgreSQL
FastAPI Backend
React + Nginx Frontend
```

---

## Build

From the project root:

```powershell
docker compose build
```

For a completely fresh build:

```powershell
docker compose build --no-cache
```

---

## Start

```powershell
docker compose up -d
```

---

## Verify Services

```powershell
docker compose ps
```

Expected:

```text
ai_software_agent_postgres    Up (healthy)

ai_software_agent_backend     Up (healthy)

ai_software_agent_frontend    Up (healthy)
```

---

## Production URLs

### Frontend

```text
http://127.0.0.1:8080
```

### Backend API

```text
http://127.0.0.1:8000
```

### Swagger

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

---

## 🌐 Nginx Reverse Proxy

The frontend communicates with the backend through:

```text
/api
```

Nginx forwards requests internally to:

```text
backend:8000
```

Example:

```text
Browser
   ↓
http://127.0.0.1:8080/api/v1/tasks
   ↓
Nginx
   ↓
backend:8000/api/v1/tasks
   ↓
FastAPI
```

This means the production frontend does not need to know the host backend address directly.

---

# 📁 Docker Repository Workspaces

The production backend uses:

```text
/workspace
```

as the controlled repository mount.

Host directory:

```text
workspaces/
```

is mounted into the backend container.

Example:

```text
Host:

AI-Software-Engineering-Agent/
└── workspaces/
    └── example_repository/
```

Docker task repository path:

```text
/workspace/example_repository
```

Existing historical tasks created on Windows may contain paths such as:

```text
C:\Users\...\repository
```

These remain available as historical records, but new Docker-based tasks should use `/workspace/...` paths.

---

# 🧪 Testing

## Backend Tests

```powershell
cd backend

python -m pytest -q
```

---

## Backend Linting

```powershell
ruff check .
```

---

## Frontend Linting

```powershell
cd frontend

npm run lint
```

---

## Frontend Production Build

```powershell
npm run build
```

---

## Docker Health

```powershell
docker compose ps
```

---

# ✅ Verification Pipeline

Every controlled repository verification can execute:

```text
1. compileall
2. Ruff
3. pytest
```

Example:

```text
compileall  → Passed
Ruff        → Passed
pytest      → Passed

Final Verification → Passed
```

All verification runs and individual command results are persisted.

---

# 🧪 Evaluation

A dedicated evaluation suite is included under:

```text
evaluation/
```

The suite contains:

- normal software engineering tasks,
- deliberate failure scenarios,
- self-correction scenarios,
- restricted-path tests,
- unsafe action tests,
- binary-file safety tests,
- environment-file protection tests.

The assignment requirement is to complete **10 or more evaluation tasks** while retaining the remaining cases for future regression testing.

### Current Evaluation Coverage

```text
Clean formal evaluation tasks    : 11
Additional end-to-end workflows  : 2
Total meaningful scenarios       : 13
```

Additional test cases remain available in the suite for future testing.

---

## Example Evaluated Tasks

Examples include:

```text
Update numeric constant
Update greeting constant
Fix addition function
Fix even number detection
Fix clamp upper boundary
Normalize names safely
Fix square calculation
Handle empty list safely
Count only positive numbers
Return maximum value
Restricted Git modification
Binary file modification safety
```

---

# 🔒 Safety Evaluation

Dedicated safety scenarios validate protection against:

### Restricted Git Modification

```text
.git/config
```

### Parent Directory Traversal

```text
../outside.txt
```

### Environment Secret Modification

```text
.env
```

### Cache Modification

```text
__pycache__/
```

### Binary File Editing

```text
data.bin
```

The system is designed to block unsafe actions rather than force completion.

---

# 🧠 Self-Correction Evaluation

The evaluation suite also includes deliberately introduced faults.

These cases verify:

```text
Initial Change
    ↓
Verification Failure
    ↓
Failure Analysis
    ↓
Correction Proposal
    ↓
Human Approval
    ↓
Correction Apply
    ↓
Reverification
```

The correction workflow maintains lineage between:

- source verification,
- correction session,
- correction patch,
- retry verification.

---

# 📊 Persistent Data Model

Primary PostgreSQL tables include:

```text
tasks

pending_patches

verification_runs

verification_steps

self_correction_sessions

self_correction_patches
```

Relationships use database-level foreign-key protection and cascade behavior where appropriate.

---

# 🖥️ User Interface

The engineering dashboard provides:

### Workspace

Manage the complete lifecycle of one software task.

### Task Navigation

Includes:

- task search,
- normal/evaluation filters,
- recent tasks,
- full task list,
- evaluation badges.

### Implementation Plan

Displays the current session plan or historical engineering evidence.

### Patch Review

Shows:

- file changes,
- additions,
- deletions,
- unified diff,
- original file hash,
- patch status,
- human approval controls.

### Automated Verification

Shows:

- verification history,
- successful checks,
- failed checks,
- runtime,
- commands,
- stdout,
- stderr.

### Self-Correction Control

Displays:

- correction state,
- attempts,
- remaining attempts,
- next action,
- correction lineage,
- human approval gates,
- safe-stop state.

### History

Provides a consolidated audit view of:

- tasks,
- patches,
- verification runs,
- correction sessions.

---

# 🛡️ Human Approval Guarantees

The system deliberately separates:

```text
AI Decision
```

from:

```text
Repository Write
```

The AI can prepare a patch.

It cannot finalize the repository modification without passing through the controlled approval workflow.

```text
AI prepares
     ↓
Human reviews
     ↓
Human approves
     ↓
System applies
```

This design keeps high-impact software changes under explicit human control.

---

# 📜 Auditability

The application retains persistent engineering history including:

- task creation,
- patch preparation,
- review status,
- patch application,
- verification execution,
- failure analysis,
- correction attempts,
- correction lineage.

This makes the workflow inspectable rather than opaque.

---

# 🐳 Docker End-to-End Validation

The final production Docker stack was tested using a real mounted repository.

Test repository:

```text
/workspace/docker_smoke_repo
```

Initial source contained an intentional multiplication bug:

```python
def multiply(a: int, b: int) -> int:
    return a + b
```

The Dockerized agent:

1. inspected the mounted repository,
2. generated a plan,
3. prepared the source patch,
4. presented the diff,
5. waited for human approval,
6. applied the approved change,
7. wrote the change to the mounted repository,
8. executed verification.

Final source:

```python
def multiply(a: int, b: int) -> int:
    return a * b
```

Final verification:

```text
compileall  Passed
Ruff        Passed
pytest      Passed
```

Container-side pytest result:

```text
2 passed
```

This validated the complete Docker workflow from UI to repository write and verification.

---

# ⚙️ Docker Test Database

The PostgreSQL test service is isolated behind a Docker Compose profile.

It is not started during normal production startup.

To start it:

```powershell
docker compose --profile test up -d postgres_test
```

This keeps the regular production stack limited to:

```text
postgres
backend
frontend
```

---

# 🧹 Stop the Stack

```powershell
docker compose down
```

This does not remove the persistent database volume.

To inspect running containers:

```powershell
docker compose ps
```

To inspect backend logs:

```powershell
docker compose logs backend
```

Frontend:

```powershell
docker compose logs frontend
```

Database:

```powershell
docker compose logs postgres
```

---

# 🔑 Secret Management

Real credentials must never be committed.

Ignored files include:

```text
.env
backend/.env
frontend/.env
```

Safe templates are provided through:

```text
.env.example
backend/.env.example
frontend/.env.example
```

Before publishing the repository, always confirm:

```powershell
git ls-files | Select-String -Pattern "(^|/)\.env$"
```

The command should return no real environment files.

---

# 📄 Technical Documentation

The complete technical report is available at:

[📘 Final Technical Report](docs/AI_Software_Engineering_Agent_Final_Technical_Report.pdf)

It covers:

- architecture,
- engineering decisions,
- agent workflow,
- repository tooling,
- human approval,
- self-correction,
- security controls,
- evaluation,
- production Docker setup,
- known limitations,
- deployment considerations.

---

# ⚠️ Known Production Considerations

### Historical Windows Paths

Tasks created before Dockerization may contain Windows absolute paths.

New container-based repositories should use:

```text
/workspace/<repository>
```

---

### Provider Quotas

Long-running agent workflows can consume significant model quota.

The backend includes:

- fallback model support,
- rate-limit classification,
- retry controls,
- cooldown handling.

Production deployments should still monitor provider quotas.

---

### History Scaling

The current History interface aggregates information across persisted tasks.

For significantly larger production workloads, server-side pagination and consolidated audit endpoints would improve scalability.

---

### Windows Docker Bind Mount Permissions

Docker Desktop may expose Windows-mounted files with executable permissions inside Linux containers.

This can cause Ruff's `EXE002` check on some mounted files.

Production Linux-native workspaces do not normally exhibit this Windows-specific behavior.

---

# 🎯 Project Status

The AI Software Engineering Agent has completed its core implementation and production validation.

The system currently includes:

- AI-driven repository inspection and implementation planning
- Controlled code modification with human approval
- Automated compile, lint, and test verification
- Failure analysis and bounded self-correction
- Persistent PostgreSQL task and audit history
- Safety controls for protected and unsafe operations
- Production-ready React engineering dashboard
- Dockerized FastAPI backend
- Dockerized React + Nginx frontend
- Dockerized PostgreSQL database
- Nginx reverse proxy configuration
- Mounted repository workspace support
- 10+ completed evaluation scenarios
- End-to-end Docker workflow validation

The complete engineering workflow has been validated from task creation through repository inspection, patch preparation, human approval, controlled file modification, and automated verification.

The project is packaged as a reproducible Docker Compose application and is ready to be deployed to a compatible hosting environment.

---

# 🏁 Final Outcome

This project demonstrates a complete human-supervised AI software engineering workflow where AI can reason about an existing codebase, prepare implementation changes, verify its work, recover from failures, and operate within explicit safety boundaries.

The final system combines:

**Agentic reasoning → Software engineering tools → Human oversight → Automated verification → Persistent auditability**

The result is a practical foundation for building reliable AI-assisted software engineering systems in real development environments.

---

# 💻 Developer

<div align="center">

## Alisha Sajjad

**AI Engineer | Software Engineer | Agentic AI Developer**

Built with a focus on production-grade AI engineering, human-in-the-loop safety, automated software verification, and reliable agentic workflows.

<br />

[![GitHub](https://img.shields.io/badge/GitHub-Profile-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/alishasajjad)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](www.linkedin.com/in/devalishasajjad)

</div>

---

# 📜 License

This project is licensed under the **MIT License**.

You are free to use, modify, distribute, and build upon this project in accordance with the terms of the license.

See the [`LICENSE`](LICENSE) file for full details.

---

<div align="center">

### 🤖 AI Software Engineering Agent

**Plan intelligently. Review explicitly. Verify everything. Recover safely.**

<br />

[![Back to Top](https://img.shields.io/badge/↑_Back_to_Top-0F172A?style=for-the-badge)](#-ai-software-engineering-agent)

<br />

<img src="https://img.shields.io/badge/Built_with-AI_Engineering-14B8A6?style=flat-square" alt="Built with AI Engineering" />

</div>