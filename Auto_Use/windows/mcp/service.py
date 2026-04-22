# Copyright 2026 Autouse AI — https://github.com/auto-use/Auto-Use
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# If you build on this project, please keep this header and credit
# Autouse AI (https://github.com/auto-use/Auto-Use) in forks and derivative works.
# A small attribution goes a long way toward a healthy open-source
# community — thank you for contributing.

"""
MCP Server for Auto Use
========================
Exposes scanner + controller as MCP tools.
External clients (Claude Desktop, Cursor, etc.) connect via stdio
and drive the screen through tool calls.

Three tools: scan_screen (observe), wait (pause), batch_actions (act).
"""

import os
import asyncio
import json
import base64
from io import BytesIO
from PIL import Image

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

from Auto_Use.windows.tree.element import UIElementScanner, ELEMENT_CONFIG
from Auto_Use.windows.controller import ControllerView


def _compress_screenshot(base64_str: str, max_width: int = 1080, quality: int = 75) -> str:
    try:
        img_bytes = base64.b64decode(base64_str)
        img = Image.open(BytesIO(img_bytes))
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        return base64_str


def _load_mcp_instructions() -> str:
    instructions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_instructions.md")
    with open(instructions_path, 'r', encoding='utf-8') as f:
        return f.read()


# ── Core components (no LLM needed) ──────────────────────────────────
scanner = UIElementScanner(ELEMENT_CONFIG)
controller = ControllerView(provider="mcp", model="mcp", cli_mode=True)

server = Server("autouse", instructions=_load_mcp_instructions())

controller.route_action([{"type": "new_session"}])


# ── Tool descriptions ────────────────────────────────────────────────

SCAN_SCREEN_DESC = """\
Scan the current screen. Returns the element tree and an annotated screenshot \
with magenta bounding boxes — each box has an [id] number at its top-left corner.

Element tree format: [id]<element name="" valuePattern.value="" type="" active="" visibility="" />

ALWAYS call scan_screen:
- Before any batch_actions call (to get fresh element IDs).
- After any batch_actions call (to verify results).

Element IDs are ephemeral — they change between scans. Never reuse IDs from a previous scan."""

WAIT_DESC = """\
Pause execution for N seconds. Use after open_app (3s recommended), \
after page navigation (2-3s), or when elements appear stale/missing. \
Always follow with scan_screen for fresh state."""

BATCH_ACTIONS_DESC = """\
Execute one or more actions sequentially in a single call. Stops on first error. \
Cannot contain scan_screen or wait.

--- Screen Automation ---

1. left_click: Format - `{"type":"left_click","id":<int>,"clicks":<int>}`
   Left-click element by [id].
   - clicks=1 (default): single click — buttons, links, menus, tabs.
   - clicks=2: double-click — open files/folders, select a word in OCR_TEXT.
   - clicks=3: triple-click — select entire paragraph in OCR_TEXT.
   - Only interact with elements where active='True' and visibility='full'.
   - OCR_TEXT replacement: double-click word → canvas_input with trailing space.
   - Example: {"type":"left_click","id":8,"clicks":2}

2. right_click: Format - `{"type":"right_click","id":<int>,"clicks":1}`
   Right-click element by [id] to open context menu.
   - Example: {"type":"right_click","id":9,"clicks":1}

3. input: Format - `{"type":"input","id":<int>,"value":"<string>"}`
   Type text into a UI element by [id]. Auto-clears existing content (Ctrl+A) first.
   - Use for: text fields, search boxes, address bars — any element with a clear input target.
   - For typing into focused areas without an addressable element, use canvas_input.
   - Example: {"type":"input","id":12,"value":"hello world"}

4. canvas_input: Format - `{"type":"canvas_input","value":"<string>"}`
   Type into the currently focused area — no [id] needed.
   - Does NOT auto-clear. Use Backspace or Ctrl+A (shortcut_combo) first if clearing is needed.
   - Use for: document bodies, spreadsheet cells, code editors, canvas-heavy apps.
   - For OCR_TEXT replacement: always add a trailing space.
   - Example: {"type":"canvas_input","value":"replacement text "}

5. scroll: Format - `{"type":"scroll","id":<int>,"direction":"<up|down|left|right>"}`
   Scroll an element in a direction.
   - Scroll visibility='partial' elements into full view before interacting.
   - Example: {"type":"scroll","id":5,"direction":"down"}

6. shortcut_combo: Format - `{"type":"shortcut_combo","value":"<string>"}`
   Press a keyboard shortcut (max 3 key pairs). Applies to the focused window.
   - Common: ctrl+c, ctrl+v, ctrl+s, ctrl+z, ctrl+f, enter, escape, tab, \
alt+tab, win+tab, alt+f4, ctrl+t, ctrl+j, ctrl+home, alt+y (UAC accept), alt+n (UAC decline).
   - Example: {"type":"shortcut_combo","value":"ctrl+c"}

7. open_app: Format - `{"type":"open_app","value":"<string>"}`
   Launch a Windows application by name (e.g. 'chrome', 'notepad', 'spotify').
   - Always follow with wait(3) + scan_screen to allow loading.
   - Use Win+Tab (shortcut_combo 'win+tab') first to check if already running.
   - Example: {"type":"open_app","value":"chrome"}

8. screenshot: Format - `{"type":"screenshot","id":<int>}`
   Capture a UI element's region to the clipboard — clean, without annotations.
   - Paste with shortcut_combo 'ctrl+v'.
   - Example: {"type":"screenshot","id":15}

--- CLI / Coding ---

9. shell: Format - `{"type":"shell","command":"<string>","input":"<string>"}`
   Execute a PowerShell command on Windows.
   - Always include input: use "" when no stdin is needed, actual values when the \
program prompts for input (input(), Read-Host, etc.).
   - Cannot access C:\\Windows.
   - Returns: cwd, command, output, status.
   - Example: {"type":"shell","command":"tree /f","input":""}
   - Example: {"type":"shell","command":"python calc.py","input":"5\\n10\\n"}

10. view: Format - `{"type":"view","path":"<string>"}`
    View file contents with [line_number] prefixes on each line.
    - Trailing blank line at end = append point for write.
    - Always view before editing to get accurate line numbers.
    - Example: {"type":"view","path":"src/main.py"}

11. write: Format - `{"type":"write","path":"<string>","line":<int>,"content":"<string>"}`
    Insert content at a specific line number. Existing lines shift down.
    - line=1 for new/empty files. Use last line number from view to append.
    - Match the file's indentation style. Build large code incrementally across multiple writes.
    - Example: {"type":"write","path":"src/app.py","line":1,"content":"def add(a, b):\\n    return a + b\\n"}

12. replace: Format - `{"type":"replace","path":"<string>","line":<int>,"old_block":"<string>","new_block":"<string>"}`
    Replace a block of lines starting at a specific line number.
    - Reads N lines from `line` downward (N = number of lines in old_block), verifies exact match, then swaps in new_block.
    - old_block and new_block can be multi-line (use \\n to separate lines). They can have different line counts.
    - Always view first to confirm exact line content.
    - Example (single line): {"type":"replace","path":"src/app.py","line":2,"old_block":"    return a + b","new_block":"    return a * b"}
    - Example (multi-line): {"type":"replace","path":"src/app.py","line":5,"old_block":"def old_func():\\n    pass","new_block":"def new_func():\\n    x = 1\\n    return x"}

--- Tracking ---

13. new_session: Format - `{"type":"new_session"}`
    Clear all tracking data (todo + scratchpad) from any previous session.
    - Call once at the very start of every new conversation, before anything else. Never skip this.

14. create_todo: Format - `{"type":"create_todo","value":"<string>"}`
    Create a structured todo plan by breaking the user's request into clear sub-steps.
    - Format value as: "Objective: <clear_objective>\\n- [ ] step_1\\n- [ ] step_2\\n- [ ] step_3"
    - System auto-numbers everything — todo blocks increment per session, step numbers are \
global and continuous. Your input becomes:
      Todo 1: Objective — Deploy React app
        #1 - [ ] Install dependencies via shell
        #2 - [ ] Build project and verify output
        #3 - [ ] Open browser and verify live site
    - Create once per task. For a new task in the same session, create another todo — numbering continues:
      Todo 2: Objective — Fix CSS layout bug
        #4 - [ ] Identify broken component via scan_screen
        #5 - [ ] Edit stylesheet via replace
        #6 - [ ] Verify fix in browser
    - Example: {"type":"create_todo","value":"Objective: Send email with attachment\\n- [ ] Open Gmail in browser\\n- [ ] Compose new email and fill fields\\n- [ ] Attach file and send\\n- [ ] Verify sent confirmation"}

15. update_todo: Format - `{"type":"update_todo","step":<int>}`
    Mark a todo step as complete by its global step number.
    - Only mark done after visual confirmation (scan_screen) — never assume success.

16. read_todo: Format - `{"type":"read_todo"}`
    Read the full todo list — all objectives, steps, and their completion status.
    - Call at the start of every execute cycle to know exactly where you are.
    - Call when context gets long and you need to recover your plan.

17. write_scratchpad: Format - `{"type":"write_scratchpad","content":"<string>"}`
    Append a verified checkpoint or key fact to persistent session memory (your external brain).
    - Only write after visual or tool confirmation — never store assumptions.
    - Write immediately when confirmed — data not stored is data lost.
    - Label every entry clearly so it's useful when read back later.
    - Use for: task completions, metrics, final answers, web findings, file paths, URLs, error notes.
    - Example: {"type":"write_scratchpad","content":"[Source: Amazon] RTX 4070 — $289, in stock, free shipping"}
    - Example: {"type":"write_scratchpad","content":"ERROR: Login failed — password field rejected input, retrying with autofill"}

18. read_scratchpad: Format - `{"type":"read_scratchpad"}`
    Read the full scratchpad — your persistent session memory.
    - Call before any step that depends on data from an earlier step.
    - Call before synthesizing a final answer, comparison, or report.
    - Call when context is long and you need to recall earlier results.
    - Think of scratchpad as your external brain — if you didn't write it down, you don't know it.

--- Batch Examples ---
Single step with tracking:
  actions: [{"type":"update_todo","step":2}, {"type":"write_scratchpad","content":"Installed all npm packages successfully"}]

Form fill sequence:
  actions: [{"type":"input","id":19,"value":"www.google.com"}, {"type":"shortcut_combo","value":"enter"}]

Code editing with verification:
  actions: [{"type":"view","path":"src/app.py"}, {"type":"replace","path":"src/app.py","line":5,"old_block":"    x = a + b\\n    y = c + d\\n    return None","new_block":"    x = a * b\\n    y = c * d\\n    return x + y"}]

Full cycle in one batch (track + act + record):
  actions: [{"type":"read_todo"}, {"type":"shell","command":"npm test","input":""}, {"type":"update_todo","step":3}, {"type":"write_scratchpad","content":"All 12 tests passing"}]"""


# ── Tool registration ─────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scan_screen",
            description=SCAN_SCREEN_DESC,
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="wait",
            description=WAIT_DESC,
            inputSchema={
                "type": "object",
                "properties": {
                    "value": {"type": "string", "description": "Seconds to wait (e.g. '3')"}
                },
                "required": ["value"]
            }
        ),
        types.Tool(
            name="batch_actions",
            description=BATCH_ACTIONS_DESC,
            inputSchema={
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "description": "Action type"}
                            },
                            "required": ["type"]
                        },
                        "description": "Array of actions to execute sequentially."
                    }
                },
                "required": ["actions"]
            }
        ),
    ]


# ── Tool execution ────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent]:

    if name == "scan_screen":
        await asyncio.to_thread(scanner.scan_elements)
        element_tree, annotated_image_base64, uac_detected = scanner.get_scan_data()

        elements_mapping = scanner.get_elements_mapping()
        controller.set_elements(elements_mapping, scanner.application_name)

        result = []

        if uac_detected:
            result.append(types.TextContent(
                type="text",
                text="UAC prompt detected. Screen is blocked. "
                     "Use batch_actions with shortcut_combo 'alt+y' to accept or 'alt+n' to decline."
            ))
            return result

        result.append(types.TextContent(
            type="text",
            text=f"<element_tree>\n{element_tree}\n</element_tree>"
        ))

        if annotated_image_base64:
            compressed = _compress_screenshot(annotated_image_base64)
            result.append(types.ImageContent(
                type="image",
                data=compressed,
                mimeType="image/jpeg"
            ))

        return result

    if name == "wait":
        import time
        seconds = float(arguments.get("value", "3"))
        await asyncio.to_thread(time.sleep, seconds)
        return [types.TextContent(type="text", text=f"Waited {seconds} seconds.")]

    if name == "batch_actions":
        EXCLUDED = {"scan_screen", "wait", "batch_actions"}
        actions_input = arguments.get("actions", [])
        if not actions_input:
            return [types.TextContent(type="text", text="Error: empty actions array")]

        for i, action in enumerate(actions_input):
            action_type = action.get("type", "")
            if action_type in EXCLUDED:
                return [types.TextContent(
                    type="text",
                    text=f"Error: '{action_type}' cannot be used inside batch_actions "
                         f"(action index {i}). Use it as a standalone tool call."
                )]

        action_result = await asyncio.to_thread(controller.route_action, actions_input)
        return [types.TextContent(
            type="text",
            text=json.dumps(action_result, indent=2, ensure_ascii=False)
        )]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Server entry point ────────────────────────────────────────────────

async def run_mcp_server():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
