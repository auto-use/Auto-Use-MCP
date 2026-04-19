# Copyright 2026 Ashish Yadav (Autouse AI)
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

"""
MCP Server for AutoUse (macOS)
===============================
Exposes scanner + controller as MCP tools.
External clients (Claude Desktop, Cursor, etc.) connect via stdio
and drive the screen through tool calls.

Includes:
  - Screen automation tools (scan, click, type, scroll, screenshot)
  - CLI/coding tools (shell, view, write, replace)
  - AppleScript tool (macOS-native app automation)
  - Tracking tools (todo, scratchpad, session)
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

from Auto_Use.macOS.tree.element import UIElementScanner, ELEMENT_CONFIG
from Auto_Use.macOS.controller import ControllerView
from Auto_Use.macOS.controller.tool.todo import clear_session


def _compress_screenshot(base64_str: str, max_width: int = 1080, quality: int = 75) -> str:
    """Compress screenshot to reduce token size"""
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


def _with_autorelease_pool(fn, *args):
    """Wrap a function call with NSAutoreleasePool for worker thread safety on macOS."""
    from Foundation import NSAutoreleasePool
    pool = NSAutoreleasePool.alloc().init()
    try:
        return fn(*args)
    finally:
        del pool


def _load_mcp_instructions() -> str:
    """Load MCP instructions from mcp_instructions.md"""
    instructions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_instructions.md")
    with open(instructions_path, 'r', encoding='utf-8') as f:
        return f.read()


# ==================== Permission Checks ====================

import sys
import subprocess as _sp

_permissions_opened = False  # Only open Settings once per session


def _check_accessibility() -> bool:
    """Check Accessibility permission. Triggers macOS prompt on first call."""
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        from CoreFoundation import CFDictionaryCreate
        # kAXTrustedCheckOptionPrompt = True triggers the system dialog
        import objc
        options = {objc.pyobjc_id(b"AXTrustedCheckOptionPrompt".decode()): True}
        return AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
    except Exception:
        from ApplicationServices import AXIsProcessTrusted
        return AXIsProcessTrusted()


def _check_screen_recording() -> bool:
    """Check Screen Recording permission.
    
    Without permission, CGWindowListCopyWindowInfo still returns window entries
    but kCGWindowName is None for other apps' windows. With permission, names are visible.
    """
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

    window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    if not window_list:
        return False

    my_pid = os.getpid()
    for window in window_list:
        pid = int(window.get('kCGWindowOwnerPID', 0))
        if pid != my_pid:
            name = window.get('kCGWindowName')
            if name is not None:
                return True
    return False


def _get_process_name() -> str:
    """Get the name of the current process for user instructions."""
    is_compiled = getattr(sys, 'frozen', False) or '__compiled__' in dir()
    if is_compiled:
        return os.path.basename(sys.executable)
    return "python3"


def _check_permissions_for_scan():
    """Check permissions before scanning. Opens Settings panes once if missing.
    
    Returns:
        None if all permissions granted, or error message string if missing.
    """
    global _permissions_opened
    from ApplicationServices import AXIsProcessTrusted

    has_accessibility = AXIsProcessTrusted()
    has_screen_recording = _check_screen_recording()

    if has_accessibility and has_screen_recording:
        return None

    missing = []
    if not has_accessibility:
        missing.append("Accessibility")
    if not has_screen_recording:
        missing.append("Screen Recording")

    # Open the relevant Settings panes — once per session
    if not _permissions_opened:
        _permissions_opened = True
        if not has_accessibility:
            _sp.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
        if not has_screen_recording:
            _sp.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"])

    process_name = _get_process_name()

    return (
        f"Missing macOS permissions: {', '.join(missing)}\n\n"
        f"AutoUse needs these to see and control the screen.\n\n"
        f"Fix:\n"
        f"1. System Settings has been opened for you.\n"
        f"2. Find '{process_name}' in the list and enable it.\n"
        f"3. If not listed, click '+' and add: {sys.executable}\n"
        f"4. Quit and relaunch the MCP client (Claude Desktop / Cursor) after granting.\n\n"
        f"Both permissions are required — Accessibility for UI control, Screen Recording for screen capture."
    )


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

2. right_click: Format - `{"type":"right_click","id":<int>}`
   Right-click element by [id] to open context menu.
   - Example: {"type":"right_click","id":9}

3. input: Format - `{"type":"input","id":<int>,"value":"<string>"}`
   Type text into a UI element by [id]. Auto-clears existing content (Cmd+A) first.
   - Use for: text fields, search boxes, address bars — any element with a clear input target.
   - For typing into focused areas without an addressable element, use canvas_input.
   - Example: {"type":"input","id":12,"value":"hello world"}

4. canvas_input: Format - `{"type":"canvas_input","value":"<string>"}`
   Type into the currently focused area — no [id] needed.
   - Does NOT auto-clear. Use Backspace or Cmd+A (shortcut_combo) first if clearing is needed.
   - Use for: document bodies, spreadsheet cells, code editors, canvas-heavy apps.
   - For OCR_TEXT replacement: always add a trailing space.
   - Example: {"type":"canvas_input","value":"replacement text "}

5. scroll: Format - `{"type":"scroll","id":<int>,"direction":"<up|down|left|right>"}`
   Scroll an element in a direction.
   - Scroll visibility='partial' elements into full view before interacting.
   - Example: {"type":"scroll","id":5,"direction":"down"}

6. shortcut_combo: Format - `{"type":"shortcut_combo","value":"<string>"}`
   Press a keyboard shortcut (max 3 key pairs). Applies to the focused window.
   - Common: cmd+c, cmd+v, cmd+s, cmd+z, cmd+f, enter, escape, tab, \
cmd+tab, cmd+q, cmd+t, cmd+w, cmd+space (Spotlight).
   - Example: {"type":"shortcut_combo","value":"cmd+c"}

7. open_app: Format - `{"type":"open_app","value":"<string>"}`
   Launch a macOS application by name (e.g. 'Safari', 'Google Chrome', 'Finder').
   - Always follow with wait(3) + scan_screen to allow loading.
   - Use Cmd+Tab (shortcut_combo 'cmd+tab') first to check if already running.
   - Example: {"type":"open_app","value":"Safari"}

8. screenshot: Format - `{"type":"screenshot","id":<int>}`
   Capture a UI element's region to the clipboard — clean, without annotations.
   - Paste with shortcut_combo 'cmd+v'.
   - Example: {"type":"screenshot","id":15}

--- AppleScript ---

9. applescript: Format - `{"type":"applescript","app":"<string>","value":"<string>"}`
   Run AppleScript on any macOS app. App activation is automatic.
   - Provide action lines (system wraps in 'tell application' block) or a full 'tell application ... end tell' block.
   - Safari: use `make new tab` (never `make new document`), always `set current tab to newTab`. End with `return` for verification.
   - Example: {"type":"applescript","app":"Safari","value":"tell front window to set newTab to make new tab with properties {URL:\"https://youtube.com\"}\ntell front window to set current tab to newTab"}
   - Example: {"type":"applescript","app":"Finder","value":"return name of every file of desktop"}

--- CLI / Coding ---

10. shell: Format - `{"type":"shell","command":"<string>","input":"<string>"}`
    Execute a zsh command on macOS.
    - Always include input: use "" when no stdin is needed, actual values when the \
program prompts for input.
    - Returns: cwd, command, output, status.
    - Example: {"type":"shell","command":"ls -la","input":""}

11. view: Format - `{"type":"view","path":"<string>"}`
    View file contents with [line_number] prefixes on each line.
    - Trailing blank line at end = append point for write.
    - Always view before editing to get accurate line numbers.
    - Example: {"type":"view","path":"src/main.py"}

12. write: Format - `{"type":"write","path":"<string>","line":<int>,"content":"<string>"}`
    Insert content at a specific line number. Existing lines shift down.
    - line=1 for new/empty files. Use last line number from view to append.
    - Example: {"type":"write","path":"src/app.py","line":1,"content":"def add(a, b):\\n    return a + b\\n"}

13. replace: Format - `{"type":"replace","path":"<string>","line":<int>,"old_str":"<string>","new_str":"<string>"}`
    Replace content at a specific line in a file.
    - Provide exact old_str to match on that line and new_str to replace it.
    - Always view first to confirm exact line content.
    - Example: {"type":"replace","path":"src/app.py","line":2,"old_str":"result = a + b","new_str":"result = a * b"}

--- Tracking ---

14. new_session: Format - `{"type":"new_session"}`
    Clear all tracking data (todo + scratchpad) from any previous session.
    - Call once at the very start of every new conversation, before anything else.

15. create_todo: Format - `{"type":"create_todo","value":"<string>"}`
    Create a structured todo plan by breaking the user's request into clear sub-steps.
    - Format value as: "Objective: <clear_objective>\\n- [ ] step_1\\n- [ ] step_2\\n- [ ] step_3"

16. update_todo: Format - `{"type":"update_todo","step":<int>}`
    Mark a todo step as complete by its global step number.
    - Only mark done after visual confirmation — never assume success.

17. read_todo: Format - `{"type":"read_todo"}`
    Read the full todo list — all objectives, steps, and completion status.

18. write_scratchpad: Format - `{"type":"write_scratchpad","content":"<string>"}`
    Append a verified checkpoint or key fact to persistent session memory.
    - Only write after confirmation — never store assumptions.

19. read_scratchpad: Format - `{"type":"read_scratchpad"}`
    Read the full scratchpad — your persistent session memory.

--- Batch Examples ---
Single step with tracking:
  actions: [{"type":"update_todo","step":2}, {"type":"write_scratchpad","content":"Installed all npm packages successfully"}]

Form fill sequence:
  actions: [{"type":"input","id":19,"value":"www.google.com"}, {"type":"shortcut_combo","value":"enter"}]

Code editing with verification:
  actions: [{"type":"view","path":"src/app.py"}, {"type":"replace","path":"src/app.py","line":5,"old_str":"    x = a + b","new_str":"    x = a * b"}]

Full cycle in one batch (track + act + record):
  actions: [{"type":"read_todo"}, {"type":"shell","command":"npm test","input":""}, {"type":"update_todo","step":3}, {"type":"write_scratchpad","content":"All 12 tests passing"}]"""


# Initialize core components (no LLM needed)
scanner = UIElementScanner(ELEMENT_CONFIG)
controller = ControllerView(provider="mcp", model="mcp", cli_mode=True)

# MCP Server
server = Server("autouse", instructions=_load_mcp_instructions())

# Fresh session — clear tracking files on startup
clear_session()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="scan_screen",
            description="Scan the current screen. Returns the element tree and an annotated screenshot with magenta bounding boxes showing element [id] at top-left corner. Element tree format: [id]<element name=\"\" valuePattern.value=\"\" type=\"\" active=\"\" visibility=\"\" />. ALWAYS call this first before any interaction, and after every action to verify results. Element IDs change between scans — never reuse old IDs.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="wait",
            description="Pause execution for N seconds. Use after open_app (3s recommended), after page navigation (2-3s for loading), or when UI elements appear missing/stale. After waiting, call scan_screen to get fresh state.",
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


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent]:
    
    # --- scan_screen: direct scanner call ---
    if name == "scan_screen":
        # Check permissions before attempting scan
        permission_error = await asyncio.to_thread(_with_autorelease_pool, _check_permissions_for_scan)
        if permission_error:
            return [types.TextContent(type="text", text=permission_error)]
        
        await asyncio.to_thread(_with_autorelease_pool, scanner.scan_elements)
        element_tree, annotated_image_base64, uac_detected = scanner.get_scan_data()
        
        # Update controller with fresh elements
        elements_mapping = scanner.get_elements_mapping()
        controller.set_elements(elements_mapping, scanner.application_name)
        
        result = []
        
        if uac_detected:
            result.append(types.TextContent(
                type="text",
                text="System dialog detected. Screen may be blocked. Try pressing 'escape' or clicking the dialog button to dismiss."
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
    
    # --- wait: simple sleep ---
    if name == "wait":
        import time
        seconds = float(arguments.get("value", "3"))
        await asyncio.to_thread(time.sleep, seconds)
        return [types.TextContent(type="text", text=f"Waited {seconds} seconds.")]
    
    # --- batch_actions: execute multiple actions sequentially ---
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

        action_result = await asyncio.to_thread(
            _with_autorelease_pool, controller.route_action, actions_input
        )
        return [types.TextContent(
            type="text",
            text=json.dumps(action_result, indent=2, ensure_ascii=False)
        )]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def run_mcp_server():
    """Start the MCP server on stdio"""
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())