<div align="center">

  <img src="https://avatars.githubusercontent.com/u/261651914" alt="YantraOS Logo" width="120" height="120" />

  # YantraOS
  
  **The First Native AI-Agent Operating System**
  
  *[ Passive Tool ] ➔ [ Active Worker ]*

  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Based On](https://img.shields.io/badge/Based%20On-Arch%20Linux-blue)](https://archlinux.org/)
  [![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289DA)](https://discord.gg/your-invite-link)
  [![Status](https://img.shields.io/badge/Status-Pre--Alpha-red)]()

  [**Website**](https://yantraos.com) | [**Documentation**](https://yantraos.gitbook.io) | [**Roadmap**](https://github.com/orgs/YantraOS/projects/1)

</div>

---

## 🌌 What is YantraOS?

**YantraOS** (Sanskrit: *Yantra* — Instrument/Engine) is a reimagined Linux distribution designed to shift personal computing from a passive experience to an active one. 

Unlike traditional operating systems that wait for your input, YantraOS runs a persistent **"Kriya Loop"**—a background AI daemon that proactively manages tasks, organizes files, and executes complex workflows 24/7.

Built on **Arch Linux**, it features a **Hybrid Inference Engine** that intelligently routes tasks between local privacy-first models and powerful cloud APIs based on your hardware.

---

## 🧠 The Hybrid "Yantra" Engine

YantraOS solves the "Hardware Barrier" by abstracting AI inference. You don't need an H100 GPU to have a smart OS.

| Mode | Hardware Detection | Model Used | Use Case |
| :--- | :--- | :--- | :--- |
| **Local Mode** (Privacy) | NVIDIA RTX / AMD Radeon (>8GB VRAM) | **Ollama** (Llama 3, DeepSeek) | Code generation, file sorting, system maintenance. *100% Offline.* |
| **Cloud Mode** (Power) | Integrated Graphics / Low RAM | **Gemini 2.0 / Claude 3.5** | Complex reasoning, creative writing, internet research. |

> **Note:** The "Router" (powered by LiteLLM) handles this switch automatically. User data never leaves the device unless explicitly required by a Cloud task.

---

## ✨ Key Features

### 1. The "Kriya" Loop (24/7 Worker)
Your OS doesn't sleep when you do. 
- **Auto-Maintenance:** Cleans cache, updates pacman mirrors, and organizes `~/Downloads` overnight.
- **Context Awareness:** The OS "sees" your screen (OCR) and terminal output to offer proactive fixes for errors.

### 2. Savant Memory (RAG)
YantraOS learns your specific workflows.
- **Skill Acquisition:** Show it how to deploy a Docker container once. It records the logs, embeds them into a local Vector Database (**ChromaDB**), and creates a reusable "Skill."
- **Next time:** Just say "Deploy this," and it recalls the skill.

### 3. Sandboxed Execution
Safety first. AI agents can be dangerous.
- All autonomous commands run inside isolated **Docker** containers or restricted user namespaces.
- The AI proposes a `sudo` action; YOU approve it.

---

## 🛠 Tech Stack

* **Base System:** Arch Linux (Custom ISO)
* **Orchestration:** Python (Systemd Service)
* **Inference Router:** LiteLLM
* **Local Inference:** Ollama
* **Vector Database:** ChromaDB (Local)
* **UI/UX:** Custom GNOME Shell Extension + Terminal UI (TUI)

---

## 🚀 Getting Started (Developer Preview)

*Warning: This is pre-alpha software. Do not install on your primary machine.*

### Prerequisites
* **RAM:** 8GB (Minimum), 16GB+ (Recommended for Local Mode)
* **Storage:** 50GB Free Space
* **GPU:** NVIDIA (CUDA) recommended for local inference.

### Installation (The "Shell" Overlay)
You can install the Yantra Core on an existing Arch Linux setup:

```bash
# Clone the repository
git clone [https://github.com/YantraOS/yantra-core.git](https://github.com/YantraOS/yantra-core.git)

# Enter directory
cd yantra-core

# Run the installer script
chmod +x install.sh
./install.sh
