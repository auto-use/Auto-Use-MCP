<div align="center">
  <img src="Auto_Use/logo/autouse.png" alt="Auto Use Logo" width="120"/>

  # Auto Use — MCP Server

  <a href="https://autouse.netlify.app/">
    <img src="https://img.shields.io/badge/⬇️%20Download%20.mcpb%20(One--Click%20Install)-2563EB?style=for-the-badge&logoColor=white" alt="Download .mcpb" height="44"/>
  </a>

  **🤖 Computer-Use MCP Server for macOS & Windows**

  This is the **source repository** for the Auto Use MCP server — a single cross-platform MCP that gives any MCP-compatible client (Claude Desktop, Cursor, etc.) direct control of your computer: screen perception, mouse and keyboard input, browser control, file editing, and shell access. The macOS and Windows implementations live side-by-side in this repo and are dispatched automatically at runtime by `main.py`.

  > 📦 **Looking for the ready-to-install bundle?** Grab the prebuilt `.mcpb` from **[autouse.netlify.app](https://autouse.netlify.app/)** — drag it into Claude Desktop and you're done. No Python, no venv, no setup.

  [Features](#-features) • [Example Tasks](#-example-tasks) • [Setup](#-setup) • [Author](#-author)
</div>

---

## ✨ Features

MCP tools exposed by the server — the client (Claude Desktop, Cursor, etc.) drives them.

- **State-of-the-art screen perception** — proprietary single-pass analysis fusing OCR with native platform accessibility APIs, producing a structured element tree with full depth awareness. Unlocks interaction with canvas-based and non-standard UI. Completes in seconds.
- **Mouse & keyboard input** — pixel-perfect click, type, scroll, shortcuts via native OS input APIs
- **Browser control** — every browser (Chrome, Firefox, Arc, Brave, Safari…) with no debug flags or connectors
- **File editing** — read, write, create, and modify files across large projects
- **Shell access** — run commands on the local machine
- **AppleScript** — native scripting bridge on macOS
- **Secure sandbox** — path protection and destructive-command guards

---

## 🎯 Example Tasks

Just describe what you want — Auto Use picks the right tool for the job.

### 🖥️ GUI Task
```
"Open Chrome, go to YouTube, and search for Python tutorials"
```

### 👨‍💻 Coding Task
```
"Create a Python Flask API with user authentication"
```

### 🌐 Web Search Task
```
"Find the latest NVIDIA stock price and quarterly revenue"
```

### 💻 CLI Task
```
"Check disk space and clean up temp files"
```

### 🍎 AppScript Task
```
"Send an iMessage to John saying I'll be 10 minutes late"
```

---

## 🎯 What Can Auto Use Do?

| Category | Examples |
|----------|----------|
| **Browser** | Fill forms, extract data, navigate sites, download files |
| **Productivity** | Create documents, manage spreadsheets, organize files |
| **Development** | Write code, debug errors, run tests, manage git |
| **System** | Install software, configure settings, manage processes |
| **Research** | Search web, compile information, generate reports |

---

## 📋 Requirements

- **macOS** (Apple Silicon or Intel) **or** **Windows 10/11**
- An **MCP-compatible client** (Claude Desktop, Cursor, etc.)
- Python **3.13+** (only if running from source)

---

## 🚀 Setup

### Option 1 — One-click install (recommended)

Download the prebuilt bundle and drag it into Claude Desktop. That's it.

> 🌐 **[autouse.netlify.app](https://autouse.netlify.app/)** — grab `autouse.mcpb`, then drop it into Claude Desktop (`Settings → Extensions`) or double-click it. Works on both macOS and Windows from the same file.

No Python, no venv, no API keys on the server side — the client handles everything.

---

### Option 2 — Run from source (for developers)

The repo ships source only; `main.py` is the entry point and auto-dispatches to the right platform subpackage (`Auto_Use/macOS/mcp` on darwin, `Auto_Use/windows/mcp` on win32).

#### 🍎 macOS

1. **Clone and set up a virtual environment**

   ```bash
   git clone https://github.com/auto-use/Auto-Use-MCP.git
   cd Auto-Use-MCP
   python3 -m venv venv
   source venv/bin/activate
   pip install -r mac_requirements.txt
   ```

2. **Grant Accessibility + Screen Recording** to your terminal / Python in `System Settings → Privacy & Security` so Auto Use can see and control the desktop.

#### 🪟 Windows

1. **Clone and set up a virtual environment**

   ```bat
   git clone https://github.com/auto-use/Auto-Use-MCP.git
   cd Auto-Use-MCP
   py -3.13 -m venv venv
   venv\Scripts\activate
   pip install -r windows_requirements.txt
   ```

> **Note:** Python **3.13.3** is the preferred version for best compatibility.

#### Connect your MCP client

Point your MCP client at `main.py` using **absolute paths** (relative paths break on Windows because spawned processes default to `C:\WINDOWS\system32`).

**macOS** — `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "autouse": {
      "command": "/ABSOLUTE/PATH/TO/Auto-Use-MCP/venv/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/Auto-Use-MCP/main.py"]
    }
  }
}
```

**Windows** — `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "autouse": {
      "command": "D:/ABSOLUTE/PATH/TO/Auto-Use-MCP/venv/Scripts/python.exe",
      "args": ["D:/ABSOLUTE/PATH/TO/Auto-Use-MCP/main.py"]
    }
  }
}
```

Fully quit and relaunch your MCP client. `main.py` will pick the correct platform module automatically.

---

## 🛡️ Safety

- **Sandbox Isolation** — Code runs in a protected environment
- **No System Modification** — Won't delete files or run destructive commands without permission
- **Permission Awareness** — Asks for confirmation before accepting elevation prompts
- **Path Protection** — Blocks access to critical system folders

---

## 🌟 Why Auto Use?

| Feature | Auto Use | Others |
|---------|----------|--------|
| Unified OS-level MCP | ✅ | ❌ |
| Native accessibility + OCR perception | ✅ | Limited |
| Real browser control (no debug flags) | ✅ | ❌ |
| macOS + Windows from one repo | ✅ | ❌ |
| Coding / file editing tools | ✅ | ❌ |
| Shell access | ✅ | Limited |
| Secure sandbox | ✅ | ❌ |

---

## 💻 OS Support

This repository supports **both macOS and Windows** — the two platform implementations live side-by-side and are selected automatically by `main.py` at runtime:

- **macOS** — `Auto_Use/macOS/`
- **Windows** — `Auto_Use/windows/`

---

## 👤 Author

**Ashish Yadav** — founder of [Autouse AI](https://github.com/auto-use)

---

## 📄 License & Attribution

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE) and [NOTICE](NOTICE).

If you use, fork, reference, or derive from this project, you must:

1. Preserve the copyright notice and the `NOTICE` file.
2. Credit **Ashish Yadav (Autouse AI)** as the original author.
3. Link back to the project: https://github.com/auto-use

### How to cite

> Yadav, Ashish. *Autouse AI — Computer Use.* Autouse AI, 2026. https://github.com/auto-use
