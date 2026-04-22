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

import os
import re
import logging

logger = logging.getLogger(__name__)

# Directory for MCP tracking files
TRACKING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "mcp_tracking")


def _ensure_tracking_dir():
    """Create tracking directory if it doesn't exist"""
    os.makedirs(TRACKING_DIR, exist_ok=True)


def _todo_path():
    return os.path.join(TRACKING_DIR, "todo.md")


def _scratchpad_path():
    return os.path.join(TRACKING_DIR, "scratchpad.md")


def _format_todo() -> str:
    """Read todo.md and return its content wrapped in <todo> tags."""
    todo_file = _todo_path()
    if not os.path.exists(todo_file):
        return "<todo>\nNo todos yet\n</todo>"
    with open(todo_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content:
        return "<todo>\nNo todos yet\n</todo>"
    return f"<todo>\n{content}\n</todo>"


def _format_scratchpad() -> str:
    """Read scratchpad.md, auto-number each line, and return wrapped in <scratchpad> tags."""
    sp_file = _scratchpad_path()
    if not os.path.exists(sp_file):
        return "<scratchpad>\nScratchpad is empty\n</scratchpad>"
    with open(sp_file, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f.readlines() if l.strip()]
    if not lines:
        return "<scratchpad>\nScratchpad is empty\n</scratchpad>"
    numbered = "\n".join(f"{i}. {line}" for i, line in enumerate(lines, 1))
    return f"<scratchpad>\n{numbered}\n</scratchpad>"


def clear_session():
    """Wipe both todo.md and scratchpad.md for a fresh session"""
    _ensure_tracking_dir()
    for path in [_todo_path(), _scratchpad_path()]:
        if os.path.exists(path):
            os.remove(path)


def _get_last_numbers():
    """Parse todo.md to find last todo block number and last step number"""
    todo_file = _todo_path()
    last_todo = 0
    last_step = 0
    
    if not os.path.exists(todo_file):
        return last_todo, last_step
    
    with open(todo_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find last todo block number
    todo_matches = re.findall(r'^Todo (\d+):', content, re.MULTILINE)
    if todo_matches:
        last_todo = max(int(n) for n in todo_matches)
    
    # Find last step number
    step_matches = re.findall(r'^#(\d+)-', content, re.MULTILINE)
    if step_matches:
        last_step = max(int(n) for n in step_matches)
    
    return last_todo, last_step


def create_todo(value: str) -> str:
    """
    Create a new todo block from agent's raw string.
    
    Agent sends:
        "Objective: Deploy React app\\n- [ ] Install deps\\n- [ ] Build project\\n- [ ] Verify site"
    
    System produces:
        Todo 1: Objective - Deploy React app
        #1- [ ] Install deps
        #2- [ ] Build project
        #3- [ ] Verify site
    
    Args:
        value: Raw string with "Objective: ..." on first line, "- [ ] ..." on subsequent lines
        
    Returns:
        str: Confirmation message
    """
    _ensure_tracking_dir()
    last_todo, last_step = _get_last_numbers()
    
    raw_lines = value.strip().split("\n")
    
    # Parse objective from first line
    first_line = raw_lines[0].strip()
    if first_line.lower().startswith("objective:"):
        objective = first_line[len("objective:"):].strip()
    else:
        objective = first_line
    
    # Parse steps from remaining lines
    steps = []
    for line in raw_lines[1:]:
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            step_text = stripped[len("- [ ]"):].strip()
            if step_text:
                steps.append(step_text)
    
    if not steps:
        return "No steps found. Format: Objective: ...\\n- [ ] step1\\n- [ ] step2"
    
    new_todo_num = last_todo + 1
    next_step = last_step + 1
    
    lines = [f"Todo {new_todo_num}: Objective - {objective}"]
    for i, step in enumerate(steps):
        step_num = next_step + i
        lines.append(f"#{step_num}- [ ] {step}")
    
    block = "\n".join(lines) + "\n\n"
    
    with open(_todo_path(), "a", encoding="utf-8") as f:
        f.write(block)
    
    return _format_todo()


def update_todo(step_number: int) -> str:
    """
    Mark a step as complete by its global number.
    
    Args:
        step_number: The step number to mark done
        
    Returns:
        str: Confirmation or error message
    """
    todo_file = _todo_path()
    
    if not os.path.exists(todo_file):
        return "No todo file exists"
    
    with open(todo_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    pattern = f"#{step_number}- [ ] "
    if pattern not in content:
        # Check if already done
        done_pattern = f"#{step_number}- [x] "
        if done_pattern in content:
            return f"Step #{step_number} already completed"
        return f"Step #{step_number} not found"
    
    content = content.replace(pattern, f"#{step_number}- [x] ", 1)
    
    with open(todo_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    return _format_todo()


def read_todo() -> str:
    """Read full todo.md content wrapped in <todo> tags"""
    return _format_todo()


def write_scratchpad(content: str) -> str:
    """Append content to scratchpad.md, return full auto-numbered scratchpad"""
    _ensure_tracking_dir()
    with open(_scratchpad_path(), "a", encoding="utf-8") as f:
        f.write(content + "\n")
    return _format_scratchpad()


def read_scratchpad() -> str:
    """Read full scratchpad.md content with auto-numbered lines"""
    return _format_scratchpad()