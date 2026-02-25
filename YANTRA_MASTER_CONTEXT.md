# YANTRA_MASTER_CONTEXT.md — Unified Engine Memory

> **Version:** 2.0.0 | **Generated:** 2026-02-22 | **Classification:** MASTER REFERENCE — DO NOT FRAGMENT
>
> **Authority:** Euryale Ferox Private Limited | **Clearance:** Lead Architect

---

## 1. Brand & Aesthetic Rules

### 1.1 Design Tokens (Immutable)

| Token          | Value     | Usage                                    |
|----------------|-----------|------------------------------------------|
| `background`   | `#1E1E1E` | Base canvas for all pages / TUI containers |
| `surface`      | `#2A2A2A` | Secondary panels, data cards             |
| `accent`       | `#00E5FF` | Electric Blue — borders, links, glows, active states |
| `alert`        | `#FFB000` | Terminal Amber — warnings, system states |
| `text-primary` | `#E0E0E0` | Body text                                |
| `text-dim`     | `#888888` | Sub-text, metadata                       |
| `terminal-bg`  | `#101010` | Terminal HUD dark background             |
| `tui-bg`       | `#121212` | Yantra Shell TUI background (Phase 2 spec) |

### 1.2 Typography

| Font              | Role                                      |
|-------------------|-------------------------------------------|
| **JetBrains Mono** | All headings, terminal HUD readouts, code |
| **Inter**          | Body text, paragraphs, sub-headlines      |
| **Monospace / Nerd Font** | Yantra Shell TUI (terminal)        |

### 1.3 The Geometric Law (INVIOLABLE)

```css
border-radius: 0px; /* ALWAYS. No exceptions. */
```

Any UI element with `rounded-*`, `rounded-md`, `border-radius > 0px`, or any similar softening is **a protocol violation**. Enforced globally in `globals.css` via `border-radius: 0 !important` and in `tailwind.config.ts` with all `borderRadius` values set to `0px`. In the TUI, this translates to sharp, continuous line borders (`border: solid $electric_blue;`) — no curved widgets.

### 1.4 Interaction Feel

- Hover borders: **instantaneous snap** to `#00E5FF` — no CSS `transition` property. Machine-feel, not organic.
- 1px gaps between cards render as seamless grid lines.
- Interface must feel like a **precision instrument** — advanced sci-fi telemetry equipment, not a standard web app.

### 1.5 Brand Philosophy

YantraOS is derived from the Sanskrit for **machine, instrument, or engine utilized to focus energy**. It operates under the philosophical framework of a **"Karma Yogi"** — a relentless, background entity that continuously organizes, optimizes, and heals the system environment 24/7 without user intervention. It is explicitly designed as a **Level 3 AI-Agent Operating System** built as a native orchestration layer on top of Arch Linux. The platform solves the **"AI Accessibility Gap"** (where local AI requires expensive GPUs, excluding 90% of users) by employing a "Hybrid Advantage"—combining local privacy and zero latency with cloud power for complex reasoning.

---

## 2. Deployed Web HUD Architecture

### 2.1 Core Stack

| Layer              | Technology                          | Version       |
|--------------------|-------------------------------------|---------------|
| Framework          | Next.js (App Router)                | 14.2.29       |
| Language           | TypeScript + TSX                    | ^5            |
| Styling            | Tailwind CSS (geometric only)       | ^3.4.1        |
| Animation          | Framer Motion                       | ^11.18.2      |
| AI SDK             | Vercel AI SDK (`ai`)                | ^6.0.97       |
| AI Provider        | `@ai-sdk/google` (Gemini 2.0 Flash) | ^3.0.30      |
| Vector DB Client   | `@pinecone-database/pinecone`       | ^7.1.0        |
| UI Components      | 21st.dev / Aceternity (EvervaultCard, BackgroundBeams, BackgroundPaths) | Custom |
| Icons              | Lucide React                        | ^0.575.0      |
| Hosting            | Vercel                              | Production    |
| Repository         | `osyantra/yantraos-web-hud` (private) | `main` branch |

### 2.2 Environment Variables (Production)

```env
PINECONE_API_KEY=<secret>
GOOGLE_GENERATIVE_AI_API_KEY=<secret>   # Required by @ai-sdk/google
NEXT_PUBLIC_SITE_URL=https://yantraos.com
```

> **WARNING:** The env var name is `GOOGLE_GENERATIVE_AI_API_KEY`, NOT `GEMINI_API_KEY`. Enforced by the `@ai-sdk/google` provider.

### 2.3 Production URL

```
https://yantraos.com
```

### 2.4 Page Architecture & Routing

| Route             | Status | Components                               |
|-------------------|--------|------------------------------------------|
| `/`               | ✅ LIVE | NavBar, TerminalHUD, TelemetryStrip (Polling 5s), EngineRoom, SkillStore |
| `/skill-store`    | 🔲 TODO | Skill grid + Pinecone semantic search   |
| `/architecture`   | 🔲 TODO | Architecture docs viewer                |
| `/docs`           | 🔲 TODO | RAG documentation browser               |
| `/api/health`     | ✅ LIVE | GET — Merges live Kriya Cache + Pinecone Health |
| `/api/telemetry/ingest` | ✅ LIVE | POST — Validates and caches live daemon telemetry |
| `/api/skills/search` | ✅ LIVE | GET `?query=X` — RAG search against Pinecone `yantra-memory` |
| `/api/kriya/execute` | ✅ LIVE | POST — Streaming inference via Vercel AI SDK + Gemini 2.0 Flash |

### 2.5 Component Inventory

| Component              | Purpose                                                |
|------------------------|--------------------------------------------------------|
| `NavBar`               | `YANTRA_OS` + blinking cursor, nav links, 1px `#00E5FF` bottom border |
| `TerminalHUD`          | Interactive console: boot sequence → live command input |
| `TerminalTypewriter`   | Multi-line sequential terminal output simulation       |
| `TelemetryStrip`       | Live indicators: PINECONE / MODEL / ROUTING / BUILD    |
| `EngineRoom`           | 3-column architecture grid (CORE-01/02/03)             |
| `SkillStore`           | 4 mock skills, category filter bar                     |
| `FeatureLayout`        | Consistent horizontal section structuring + entrance animations |
| `EvervaultCard`        | 21st.dev — Cipher text overlay + radial glow for Engine Room |
| `BackgroundBeams`      | 21st.dev — Dynamic animated background for Hero        |
| `BackgroundPaths`      | 21st.dev — Flowing technical grid for Skill Store      |

### 2.6 Engine Room Cards (CORE-01/02/03)

| Card | Label | Key Specs |
|------|-------|-----------|
| Hybrid Inference Engine | CORE-01 | LiteLLM local ≥8GB VRAM, managed cloud fallback |
| Vector Memory | CORE-02 | Pinecone 1536-dim cosine, per-skill namespacing |
| Atomic Stability | CORE-03 | Docker isolation, BTRFS rollback, Kriya Loop self-annealing |

### 2.7 Terminal Boot Sequence

```
> SYSTEM INITIATED: Euryale Ferox V1.0       [Electric Blue]
> DAEMON: Kriya Loop Active.                  [Terminal Amber]
> TELEMETRY: VRAM 12GB Detected. Routing...  [Green]
> REASONING: Optimizing workflow...           [Light grey]
> STATUS: All systems nominal.               [Electric Blue]
```

After boot, input auto-appears and auto-focuses. User input in `#888`, daemon responses in `#00E5FF`, `● PROCESSING` (amber) during streaming.

---

## 3. JSON Data Schemas

### 3.1 Skill Object — `yantraos/skill/v1`

```json
{
  "$schema": "yantraos/skill/v1",
  "id": "string (uuid-v4)",
  "title": "string",
  "description": "string",
  "version": "string (semver, e.g. '1.2.0')",
  "icon_reference": "string (lucide icon name or absolute path to SVG asset)",
  "tags": ["string"],
  "category": "enum: 'automation' | 'inference' | 'rag' | 'data' | 'system' | 'utility'",
  "execution_environment": {
    "type": "enum: 'local' | 'cloud' | 'hybrid'",
    "requires_vram_gb": "number | null",
    "supported_models": ["string (model slug)"],
    "daemon_hook": "string (Kriya Loop daemon endpoint, e.g. '/api/kriya/execute')"
  },
  "pinecone_metadata": {
    "index_name": "string",
    "namespace": "string",
    "vector_dimensions": 1536
  },
  "author": "string",
  "created_at": "ISO 8601 timestamp",
  "updated_at": "ISO 8601 timestamp",
  "is_public": "boolean",
  "download_count": "number"
}
```

### 3.2 Kriya Loop Telemetry — `yantraos/telemetry/v1`

```json
{
  "$schema": "yantraos/telemetry/v1",
  "timestamp": "ISO 8601 timestamp",
  "daemon_status": "enum: 'BOOTING' | 'ACTIVE' | 'IDLE' | 'ERROR' | 'OFFLINE'",
  "active_model": "string (currently loaded model slug)",
  "cpu_load": {
    "percent": "number (0-100)",
    "core_count": "number"
  },
  "vram_usage": {
    "used_gb": "number",
    "total_gb": "number",
    "percent": "number (0-100)"
  },
  "ram_usage": {
    "used_gb": "number",
    "total_gb": "number",
    "percent": "number (0-100)"
  },
  "inference_routing": "enum: 'LOCAL' | 'CLOUD' | 'FALLBACK'",
  "active_skill_id": "string (uuid-v4) | null",
  "current_cycle": {
    "phase": "enum: 'ANALYZE' | 'PATCH' | 'TEST' | 'UPDATE_ARCHITECTURE' | 'IDLE'",
    "iteration": "number",
    "log_tail": ["string"]
  },
  "pinecone_connection": "enum: 'CONNECTED' | 'DEGRADED' | 'DISCONNECTED'",
  "last_error": "string | null"
}
```

### 3.3 Pinecone Index Schema

| Field              | Type   | Value                              |
|--------------------|--------|------------------------------------|
| Index Name         | string | `yantra-skills`                    |
| Dimensions         | number | `1536` (text-embedding-3-small)    |
| Metric             | string | `cosine`                           |
| Namespace Strategy | string | One namespace per skill slug       |

**Vector Metadata Fields:**

```json
{
  "skill_id": "string",
  "title": "string",
  "category": "string",
  "tags": ["string"],
  "version": "string"
}
```

---

## 4. Arch Linux Daemon Blueprint — The Kriya Loop

### 4.1 What Is the Kriya Loop

The Kriya Loop is YantraOS's **persistent background daemon** — a self-annealing, 4-phase autonomous execution cycle that runs as a `systemd` service on Arch Linux. Derived from the Sanskrit word for "Completed Action," it is a 24/7 worker that never sleeps. It sorts downloads, manages packages, reads logs, and heals the environment while the user rests. It is the core engine that monitors hardware, routes inference, executes Skills, and reports telemetry. It solves the **"Dead OS Crisis"** (Passive Computing Failure where systems experience 30% meta-work and 70% wasted capacity) by transforming the OS from a passive tool into an active, autonomous worker following a continuous `OBSERVATION → ACTION` loop.

### 4.2 The Four Phases

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌────────────────────┐
│ ANALYZE  │ →  │  PATCH   │ →  │   TEST   │ →  │ UPDATE_ARCHITECTURE│
└──────────┘    └──────────┘    └──────────┘    └────────────────────┘
      ↑                                                    │
      └────────────────────────────────────────────────────┘
```

| Phase                | Function                                                        |
|----------------------|-----------------------------------------------------------------|
| `ANALYZE`            | Scan system state (GPU, RAM, disk), evaluate pending skill queue |
| `PATCH`              | Pull updates, apply model weights, adjust routing config        |
| `TEST`               | Validate inference pipeline, run health checks                  |
| `UPDATE_ARCHITECTURE`| Commit state changes, emit telemetry, rotate logs               |

The loop runs with `time.sleep(10)` between iterations to prevent CPU thrashing. Error handling wraps the entire loop so unhandled exceptions log to `/var/log/yantra/engine.log` rather than crashing the daemon.

### 4.3 14-Day Hyper-Sprint Schedule

| Phase | Name | Days | Deliverables |
|-------|------|------|-------------|
| **1** | **The Neural Fabric** | 1–4 | `hardware.py` (VRAM detection), `router.py` (LiteLLM gateway), `memory.py` (ChromaDB RAG), `engine.py` (Kriya Loop orchestrator) |
| **2** | **The Interface** | 5–9 | `shell.py` (Yantra Shell TUI), `theme.tcss` (branding CSS), `widgets.py` (GPUHealth, ThoughtStream), `bridge.py` (UNIX socket IPC) |
| **3** | **The Deployment** | 10–14 | `yantra.service` (systemd), `install.sh` (atomic installer), `50-yantra-snapshot.hook` (BTRFS), `sandbox.py` (Docker), `Dockerfile.agent` |

### 4.4 Daemon Technology Stack

| Component          | Technology       | Purpose                                    |
|--------------------|------------------|--------------------------------------------|
| Language           | Python 3.12+     | Daemon core                                |
| Init System        | `systemd`        | Service management with `Type=notify`      |
| Watchdog           | `sdnotify`       | `WatchdogSec=15` — heartbeat every 15s, auto-restart on deadlock |
| GPU Telemetry      | `pynvml`         | NVIDIA VRAM/utilization monitoring         |
| GPU Fallback       | `rocm-smi` / `sysfs` / `lspci` | AMD/Intel fallback detection  |
| Local Inference    | Ollama           | Local LLM runner (Llama 3, DeepSeek-R1)   |
| Cloud Inference    | Gemini 2.0 Flash / Claude 3.5 Haiku | Cloud fallback models |
| Inference Router   | `LiteLLM`        | Unified local ↔ cloud model routing with fallback arrays |
| Local Vector Store | `ChromaDB`       | Local embedding cache / offline RAG / Skill Acquisition |
| TUI Framework      | Python `textual` + `rich` | Terminal User Interface         |
| IPC                | UNIX Domain Sockets | `/run/yantra/ipc.sock` — TUI ↔ daemon bridge |
| Containerization   | `docker` + `docker-py` | Skill isolation, ephemeral Alpine containers |
| Snapshot/Rollback  | `btrfs-progs`    | Filesystem snapshots for atomic stability  |
| Pacman Hook        | `50-yantra-snapshot.hook` | Pre-transaction BTRFS snapshot   |

### 4.5 Filesystem Layout

```
/opt/yantra/
├── config.yaml          # API keys (Gemini/Claude) and VRAM thresholds
├── core/
│   ├── __init__.py
│   ├── hardware.py      # VRAM check → LOCAL_CAPABLE | CLOUD_ONLY
│   ├── router.py        # LiteLLM routing with fallback arrays
│   ├── engine.py        # The Kriya Loop (main daemon loop)
│   └── memory.py        # ChromaDB RAG implementation
├── ui/
│   ├── shell.py         # Main Textual App entry point
│   ├── theme.tcss       # Geometric dark grey + electric blue CSS
│   ├── widgets.py       # GPUHealth, ThoughtStream, AuditLog
│   └── bridge.py        # UNIX Domain Socket IPC
├── deploy/
│   ├── yantra.service   # systemd unit (Type=notify, WatchdogSec=15)
│   ├── install.sh       # Atomic installer with backup/restore
│   ├── 50-yantra-snapshot.hook  # Pacman pre-transaction BTRFS hook
│   ├── sandbox.py       # Docker execution module (docker-py)
│   └── Dockerfile.agent # Alpine Linux sandbox blueprint
├── models/              # Downloaded model weights
├── skills/              # Installed skill packages
├── data/                # ChromaDB persistent storage (/var/lib/yantra/chroma)
├── logs/                # Rotating daemon logs (/var/log/yantra/)
├── snapshots/           # BTRFS snapshot metadata
└── requirements.txt     # nvidia-ml-py, litellm, chromadb, psutil, textual, rich, sdnotify, docker
```

### 4.6 Permissions Matrix (Strict)

| Entity            | User              | Group    | Access Scope               |
|-------------------|-------------------|----------|-----------------------------|
| Daemon Process    | `yantra_daemon`   | `yantra` | `/opt/yantra/` (read/write) |
| Skill Executor    | `yantra_daemon`   | `docker` | Docker socket access only   |
| Config Files      | `root`            | `yantra` | `640` (owner rw, group r)   |
| Model Weights     | `yantra_daemon`   | `yantra` | `750` (owner rwx, group rx) |
| Log Directory     | `yantra_daemon`   | `yantra` | `755`                       |
| systemd Unit      | `root`            | `root`   | `/etc/systemd/system/yantra-daemon.service` |
| IPC Socket        | `yantra_daemon`   | `yantra` | `/run/yantra/ipc.sock`      |

> **CRITICAL:** The daemon does NOT run as root. The `yantra_daemon` user is added to the `docker` group for container access. Pacman hooks run under pacman's own context, not the daemon's.

### 4.7 systemd Service Unit

```ini
[Unit]
Description=YantraOS Kriya Loop Daemon
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=notify
User=yantra_daemon
Group=yantra
ExecStart=/usr/bin/python3 /opt/yantra/core/engine.py
Restart=always
RestartSec=5
WatchdogSec=15
StandardOutput=journal
StandardError=journal
Environment=YANTRA_HOME=/opt/yantra

[Install]
WantedBy=multi-user.target
```

Key systemd details:

- `Type=notify` — daemon sends `READY=1` via `sdnotify` only after hardware detection, vector memory init, and IPC socket creation succeed.
- `WatchdogSec=15` — daemon must send `WATCHDOG=1` every 15 seconds; missed heartbeat triggers `SIGABRT` + auto-restart.
- `Restart=always` — guarantees 24/7 uptime.

### 4.8 Inference Routing Decision Tree

```
hardware.py → detect VRAM:
  IF pynvml detects NVIDIA RTX / AMD Radeon with RAM >= 16GB:
    capability = LOCAL_CAPABLE (Path A - 100% Air-gapped privacy)
    primary_model = "ollama/llama3" or "deepseek-r1" (http://localhost:11434)
  ELIF rocm-smi/sysfs detects AMD/Intel or RAM < 8GB:
    capability = CLOUD_ONLY (Path B - Mass market accessibility)
  ELSE (no GPU / detection fails):
    capability = CLOUD_ONLY

router.py → LiteLLM Router (Orchestration & Normalization):
  IF LOCAL_CAPABLE:
    route → Ollama local
    fallback → gemini/gemini-2.5-flash (on APIConnectionError or timeout)
  IF CLOUD_ONLY:
    route → gemini/gemini-2.5-flash
    fallback → claude/claude-3.5-haiku

Kriya Loop guarantees: inference NEVER hangs. All paths have fallbacks via a Secure API Gateway.
```

### 4.9 Skill Acquisition via RAG (ChromaDB)

When the daemon determines a successful sequence of commands:

1. Store the execution path as an embedding in ChromaDB at `/var/lib/yantra/chroma` (Vector Memory for execution logs and workflows).
2. Before generating new code, query the vector store for semantic similarity.
3. If high-similarity match found → retrieve verified past solutions to solve current problems (Contextual Awareness).
4. This creates permanent skill retention — **One-Shot Learning**: Teach Yantra a task once (e.g., 'Deploy React App'), and it remembers the steps forever. The system **learns from its environment**.

### 4.10 Yantra Shell TUI (Terminal User Interface)

**Three-Pane Layout:**

| Pane | Position | Width | Content |
|------|----------|-------|---------|
| Telemetry Grid | Left | 30% | Real-time VRAM bars, CPU metrics, Kriya Loop state (Sleeping/Monitoring/Optimizing/Executing) |
| Audit Log | Right | 70% | Auto-scrolling `RichLog` — step-by-step reasoning, bash commands, execution logs |
| Interaction Prompt | Bottom | 100% | Single-line input for natural language directives |

**Key Features:**

- `GPUHealth` widget: Reactive, polls hardware every 2 seconds via `hardware.py` (falls back to mock 16GB RTX 4090 on Windows/non-CUDA), displays VRAM % and active Kriya Phase.
- `ThoughtStream` widget: Displays raw LLM reasoning and daemon logs.
- Mode toggle: `M` key switches between **Manual Mode** (user commands) and **Autonomous Mode** (AI watches logs)
- Emergency halt: `Ctrl+C` invokes immediate task stop
- IPC Bridge (`bridge.py`): Automatically detects OS. Uses **TCP `127.0.0.1:50000` on Windows** and **UNIX Domain Sockets (`/tmp/yantra.sock`) on Linux**. TUI serializes intents as JSON, daemon streams responses back in real-time. 
- UI Styling: Enforces **strict hex color format** (`[#00E5FF]`, `[#888888]`, `[#FFB000]`) instead of custom Rich tags to prevent `MissingStyle` exceptions in Textual 0.52+.
- TUI does NOT block the daemon thread — asynchronous architecture via `asyncio`

### 4.11 Docker Sandboxed Execution

When the inference engine generates code to execute:

1. Daemon writes code to temp file
2. Spins up ephemeral Alpine Linux container via `docker-py`
3. Container runs with: `--cap-drop=ALL`, read-only root FS, strict seccomp profiles, `--rm` flag (Docker Container Isolation vs Protected Kernel Space).
4. **Safety First**: All AI scripts run in isolation.
5. **Human-in-the-Loop**: High-stakes commands (e.g., deletion) require user approval before execution.
6. **Result**: The AI can build or break things inside the box without touching personal files on the host machine.
7. Only `stdout` and return codes piped back to Kriya Loop. Container destroyed immediately after execution.

### 4.12 BTRFS Atomic Rollback

Before any high-stakes system command (e.g., `pacman -Syu`):

1. `50-yantra-snapshot.hook` fires on `Operation = Upgrade, Install, Remove`
2. Hook executes `btrfs subvolume snapshot` to clone `/@` → `/@snapshots/yantra_pre_exec_<timestamp>`
3. Snapshots older than 7 days are auto-pruned
4. On catastrophic failure: edit GRUB boot parameter → `rootflags=subvol=@snapshots/yantra_pre_exec_...` → system boots into stable snapshot
5. **Zero-risk operational autonomy**

### 4.13 Atomic Installer (`install.sh`) Requirements

1. Check for and install: `python-pip`, `docker`, `cuda`, `python-pynvml` via `pacman --noconfirm`
2. Create `yantra_daemon` user — do NOT run daemon as root
3. Add `yantra_daemon` to `docker` group
4. Before installing new files: backup `/opt/yantra` → `/var/backups/yantra_$(date).tar.gz`
5. If Python requirements fail → RESTORE backup immediately and exit
6. The installer itself must be **atomic** — partial installations must be rolled back

### 4.14 Required Arch Linux Packages

```
linux-headers, nvidia-dkms, cuda, python-pip, docker, docker-compose,
python-pynvml (AUR), chromadb (pip), litellm (pip), textual (pip),
rich (pip), sdnotify (pip), docker-py (pip), psutil (pip)
```

---

## 5. Component Architecture Matrix

Source: `YantraOS High-Tech Architectural and Development Specification.xlsx`

| Component | Logic Pathway | Hardware Req | Tech Stack | Purpose | Phase | Security |
|-----------|---------------|-------------|------------|---------|-------|----------|
| Hybrid Inference Engine | VRAM Check (Local >8GB / Cloud <8GB) | NVIDIA RTX GPU (8GB+) | LiteLLM, pynvml, Ollama, Gemini API | Autonomous task routing local ↔ cloud | 1 (Days 1-4) | Hardware fallback + LiteLLM redundancy |
| Kriya Loop (Daemon) | Local exec via Docker / Cloud Fallback | Arch Linux env | Python 3.12, systemd, asyncio | 24/7 background optimization & healing | 1 & 3 | systemd WatchdogSec, Type=notify, non-root |
| Yantra Shell (TUI) | User interaction & telemetry display | Terminal + Nerd Font | textual, Rich, UNIX Domain Sockets | Futuristic HUD for monitoring & commands | 2 (Days 5-9) | Async IPC isolated from daemon memory |
| Vector Memory (RAG) | Semantic search before raw inference | Persistent storage | ChromaDB | Skill acquisition via stored execution paths | 1 (Day 4) | Local vector store (privacy-focused) |
| Sandboxed Execution | AI-generated code execution | Docker Engine | Docker (Alpine), docker-py | Safe execution in isolated containers | 3 (Day 10) | `--cap-drop=ALL`, seccomp, ephemeral `--rm` |
| Atomic Rollback System | Pre-transaction pacman hook | BTRFS file system | Pacman Hooks, BTRFS Snapshots | Auto-snapshot before OS modifications | 3 (Day 11) | `50-yantra-snapshot.hook` (atomic backups) |

---

## 6. Telemetry Emission

The daemon emits `yantraos/telemetry/v1` JSON (see §3.2) via:

- **WebSocket** push to connected Web HUD instances
- **HTTP POST** to `/api/telemetry/ingest` on the Vercel backend
- **UNIX Domain Socket** to the local Yantra Shell TUI
- **journalctl** structured logging for local `systemd` integration

---

## 7. Development Toolchain ("God-Mode")

| Tool | Role | Target Phase |
|------|------|-------------|
| **Antigravity IDE** (Gemini 3 Pro) | Agentic backend code generation — Python daemons, hardware abstraction, Kriya Loop | Phase 1 |
| **Google Stitch** | Wireframe → TUI code conversion (textual + Rich) | Phase 2 |
| **Gemini 3 Pro** | High-level architectural reasoning, routing permutations, config arrays | Phase 1 |
| **Claude Opus 4.6** | Security auditor / Red Team engine — deployment scripts, container escapes, privilege escalation | Phase 3 |
| **Perplexity Pro** | Real-time Arch Linux driver anomalies, hardware error codes, systemd faults | All phases |

---

## 8. Build Constraints & Known Issues

| ID    | Constraint                                              | Impact  | Status   |
|-------|---------------------------------------------------------|---------|----------|
| C-001 | npm package name cannot contain `.` → workspace `YantraOS.com` blocked `create-next-app` | Medium | ✅ Resolved |
| C-002 | Next.js 14 requires Node.js 18.17+                     | Low     | ✅ Met   |
| C-003 | Framer Motion v11 SSR hydration caveats — terminal animations must use `"use client"` | Medium | ✅ Handled |
| C-004 | Geometric Law enforced in `tailwind.config.ts` — all `borderRadius` → `0px` | N/A | ✅ Enforced |
| C-005 | `postcss.config.mjs` had CommonJS `module.exports` in ESM — switched to `export default` | Low | ✅ Fixed |
| C-006 | OpenAI `gpt-4o-mini` rate-limited → pivoted to `google("gemini-2.0-flash")` | High | ✅ Resolved |
| C-007 | 90% of global users excluded from local AI by expensive GPU requirements → solved by Hybrid Engine | High | ✅ Architected |
| C-008 | LLM-generated code could execute destructive commands on host → solved by Docker sandbox | Critical | ✅ Architected |

---

## 9. Repository & Deployment Summary

| Property        | Value                                          |
|-----------------|------------------------------------------------|
| GitHub Org      | `osyantra`                                     |
| Repo            | `yantraos-web-hud` (private)                   |
| Branch          | `main`                                         |
| Hosting         | Vercel                                         |
| Production URL  | `https://yantraos.com`                         |
| Static Export   | `build-hostinger.ps1` (removes API routes)     |
| Package Name    | `yantra-os`                                    |
| Current Version | `0.1.0`                                        |

---

## 10. Phase Status Matrix

| Phase | Name               | Status      | Deliverables                                   |
|-------|--------------------|---------    |------------------------------------------------|
| 0     | Engine Init        | ✅ COMPLETE | Core docs, Next.js scaffold, JSON schemas      |
| 1     | Blueprint          | ✅ COMPLETE | Data schemas locked, architecture defined       |
| 2     | Link               | ✅ COMPLETE | Pinecone client, health endpoint, env config    |
| 3     | Architect          | ✅ COMPLETE | `/api/kriya/execute`, `/api/skills/search`      |
| 4     | Stylize            | ✅ COMPLETE | Full UI: NavBar, Terminal, Engine Room, Skills   |
| 5     | Trigger            | ✅ COMPLETE | Vercel deployed, GitHub synced, live at production URL |
| 6-9   | RAG + Fixes        | ✅ COMPLETE | NotebookLM sync, Hero UI fix, Vertex AI pivot  |
| **10**| **Windows Sim**    | ✅ COMPLETE | **Daemon Windows simulation, HUD Telemetry poll, IPC TCP fix** |
| 11    | Daemon Build       | ✅ COMPLETE | Arch Linux Kriya Loop daemon — 14-Day Hyper-Sprint |
| 12    | ArchISO Build      | ✅ COMPLETE | Archlive generation: Disarmed hooks, mkarchiso workarounds, CRLF updates |
| 13    | Native Validation  | ✅ COMPLETE | QEMU native testing, atomic installer (`install.sh`), systemd fixes |

---

## 11. Source Documents Index

| # | Document | Type | Content |
|---|----------|------|---------|
| 1 | `INITIATING ARCHITECTURAL PROTOCOL.docx` | TEP | 3-Phase Hyper-Sprint blueprint with "God-Prompts" for each phase |
| 2 | `YantraOS_ AI OS Development Plan.docx` | Full Spec | 36K-char exhaustive spec — philosophy, hardware profiling, LiteLLM routing, ChromaDB, TUI, IPC, systemd, BTRFS, Docker, security audit |
| 3 | `YantraOS High-Tech Architectural Specification.xlsx` | Matrix | 6-component architecture matrix with tech stack, phases, and security protocols |
| 4 | `YantraOS_Protocol.pdf` | Protocol | YantraOS protocol documentation (24.6 MB) |
| 5 | `YantraOS_The_Architecture_of_Autonomy.pdf` | Architecture | Full architecture of autonomy reference (32.1 MB) |
| 6 | `custom_os_linux_kernel_guide.txt` | Guide | Complete Linux kernel OS build guide (LFS, toolchain, bootloader) |
| 7 | `yantra_core.md` | Constitution | Project constitution — aesthetic law, JSON schemas, stack |
| 8 | `yantra_plan.md` | Sprint Plan | Sprint phases & routing checklist |
| 9 | `yantra_telemetry.md` | Telemetry | Integration discovery & constraints log |
| 10 | `yantra_kriya.md` | Execution Log | Build log & error traces |

---

## 12. Post-MVP Roadmap & Market Strategy

**Market Strategy:**

- **Primary:** Open Source Enthusiasts & Arch Linux Users.
- **Secondary:** STEM Students in hardware-constrained regions (Emerging Markets).
- **Differentiation:** The only OS optimized for Hybrid AI out of the box.

**Timeline (Road to Autonomy):**

1. **PHASE 1 (MVP) — The Neural Fabric & Interface**: Yantra Shell. Overlay for existing Linux distros. (Current Focus)
2. **PHASE 2 (ALPHA) — The Deployment**: Standalone ISO release. Integrated Hybrid Inference. Seeking funding to finalize.
3. **PHASE 3 (ECOSYSTEM) — The Future**: Yantra Skill Store. A public marketplace for users to package, publish, and monetize shareable RAG workflows, creating a Network Effect where collective intelligence improves every machine.
4. **Future Support**: Multi-GPU routing and ARM architecture builds.

---

## 13. Milestone 6: ISO Build & Native Validation Updates

1. **Build Engineering (`compile_iso.sh`)**:
   - Patched to copy `.inactive` pacman hooks (specifically `00-yantra-autosnap.hook.inactive`) to prevent premature BTRFS execution inside the chroot environment.
   - Preserves virtual environment hashbang correction logic for `/opt/yantra/venv/bin/*`.
2. **mkarchiso Fixes**:
   - Updated `profiledef.sh` with modern boot modes (`bios.syslinux` and `uefi.grub`).
   - Overrode `airootfs/etc/passwd` to sanitize users and avoid an unbound array fatal error in mkarchiso's `customize_airootfs.sh` skeleton copy loop.
   - Replaced Windows CRLF line endings with Unix LF globally in configurations and scripts.
3. **Atomic Deployment (`install.sh`)**:
   - Developed a robust bare-metal installer script with `trap rollback ERR` functionality referencing `/var/backups`.
   - Automatically reinstates the `.inactive` pacman hooks post-installation.
   - Ensures `yantra_daemon` group membership and docker integrations.
4. **Systemd Daemon Patch**:
   - `deploy/systemd/yantra.service` was updated with `Environment=PYTHONPATH=/opt/yantra` to resolve a namespace dislocation (`ModuleNotFoundError: No module named 'core'`) during native QEMU bootstrap.

---

> **EOF** — This document is the single source of truth for all YantraOS context. Any future agent session MUST read this file first before any implementation work.