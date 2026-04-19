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

import logging

from .service import ControllerService
from .tool import open_on_windows
from .key_combo.service import KeyComboService
from .tool.screenshot import ScreenshotService
from .cli.service import CLIService
from .tool.todo import create_todo, update_todo, read_todo, write_scratchpad, read_scratchpad, clear_session

logger = logging.getLogger(__name__)


class ControllerView:
    def __init__(self, provider: str = None, model: str = None, cli_mode: bool = True):
        """Initialize the Controller View - MCP action router
        
        Args:
            provider: Provider identifier (informational only)
            model: Model identifier (informational only)
            cli_mode: Always True for MCP — enables shell/view/write/replace
        """
        self.cli_mode = cli_mode
        self.controller_service = ControllerService()
        self.key_combo_service = KeyComboService()
        self.cli_service = CLIService() if cli_mode else None
        self.screenshot_service = ScreenshotService(self.controller_service)
    
    def set_elements(self, elements_mapping, application_name=""):
        """Set the elements mapping in controller service"""
        self.controller_service.set_elements(elements_mapping, application_name)
    
    def route_action(self, action_data):
        """
        Route a single action to the appropriate service.
        MCP sends one action at a time as a single-item list.
        
        Args:
            action_data (list): Single-action list e.g. [{"type": "left_click", "id": 5, "clicks": 1}]
            
        Returns:
            dict: Result of the action execution
        """
        try:
            results = []
            
            for action_item in action_data:
                action_type = action_item.get("type")
                
                if not action_type:
                    logger.warning(f"Action item missing 'type' field: {action_item}")
                    continue
                
                # ==================== Screen Automation ====================
                
                if action_type == "left_click":
                    element_id = action_item.get("id")
                    clicks = action_item.get("clicks", 1)
                    if clicks == 3:
                        result = self.controller_service.triple_click(element_id)
                    elif clicks == 2:
                        result = self.controller_service.double_click(element_id)
                    else:
                        result = self.controller_service.click(element_id)
                    results.append(result)
                    if result.get("status") == "error":
                        return result
                
                elif action_type == "input":
                    element_id = action_item.get("id")
                    text_value = action_item.get("value")
                    result = self.controller_service.input(element_id, text_value)
                    results.append(result)
                    if result.get("status") == "error":
                        return {
                            "status": "error",
                            "action": "input",
                            "results": results,
                            "message": f"Input insertion in element {element_id} failed"
                        }
                
                elif action_type == "scroll":
                    element_id = action_item.get("id")
                    direction = action_item.get("direction")
                    result = self.controller_service.scroll(element_id, direction)
                    results.append(result)
                    if result.get("status") == "error":
                        return {
                            "status": "error",
                            "action": "scroll",
                            "results": results,
                            "message": f"Scroll on element {element_id} failed"
                        }
                
                elif action_type == "canvas_input":
                    text_value = action_item.get("value")
                    result = self.controller_service.canvas_input(text_value)
                    results.append(result)
                    if result.get("status") == "error":
                        return result
                
                elif action_type == "right_click":
                    element_id = action_item.get("id")
                    result = self.controller_service.right_click(element_id)
                    results.append(result)
                    if result.get("status") == "error":
                        return result
                
                elif action_type == "shortcut_combo":
                    combo_value = action_item.get("value")
                    result = self.key_combo_service.send(combo_value)
                    results.append(result)
                    if result.get("status") == "error":
                        return result
                
                elif action_type == "screenshot":
                    element_id = str(action_item.get("id"))
                    logger.info(f"Taking screenshot of element: {element_id}")
                    
                    if element_id not in self.controller_service.elements_mapping:
                        return {
                            "status": "error",
                            "action": "screenshot",
                            "index": element_id,
                            "message": f"Element index {element_id} not found"
                        }
                    
                    element_info = self.controller_service.elements_mapping[element_id]
                    rect = element_info.get('visible_rect') or element_info['rect']
                    
                    result = self.screenshot_service.capture_element(rect)
                    result["index"] = element_id
                    results.append(result)
                    if result.get("status") == "error":
                        return result
                
                elif action_type == "open_app":
                    app_name = action_item.get("value")
                    logger.info(f"Opening application: {app_name}")
                    
                    success = open_on_windows(app_name)
                    
                    if success:
                        logger.info(f"Successfully opened {app_name}")
                        result = {"status": "success", "action": "tool", "tool": "open_app", "app": app_name}
                        results.append(result)
                    else:
                        logger.error(f"Failed to open {app_name}")
                        return {
                            "status": "error",
                            "action": "tool",
                            "tool": "open_app",
                            "app": app_name,
                            "message": "Application not found or failed to launch"
                        }
                
                # ==================== CLI Tools ====================
                
                elif action_type == "shell":
                    if self.cli_service:
                        command = action_item.get("command", "")
                        input_text = action_item.get("input", None)
                        result = self.cli_service.shell(command, input_text)
                        results.append(result)
                        if result.get("status") == "error" and result.get("error"):
                            return result
                    else:
                        return {
                            "status": "error",
                            "action": "shell",
                            "message": "CLI service not initialized (cli_mode=False)"
                        }
                
                elif action_type == "view":
                    if self.cli_service:
                        path = action_item.get("path", "")
                        result = self.cli_service.view(path)
                        results.append(result)
                    else:
                        return {
                            "status": "error",
                            "action": "view",
                            "message": "CLI service not initialized (cli_mode=False)"
                        }
                
                elif action_type == "write":
                    if self.cli_service:
                        path = action_item.get("path", "")
                        line = action_item.get("line", 1)
                        content = action_item.get("content", "")
                        result = self.cli_service.write(path, line, content)
                        results.append(result)
                    else:
                        return {
                            "status": "error",
                            "action": "write",
                            "message": "CLI service not initialized (cli_mode=False)"
                        }
                
                elif action_type == "replace":
                    if self.cli_service:
                        path = action_item.get("path", "")
                        line = action_item.get("line", 0)
                        old_block = action_item.get("old_block", "")
                        new_block = action_item.get("new_block", "")
                        result = self.cli_service.replace(path, line, old_block, new_block)
                        results.append(result)
                    else:
                        return {
                            "status": "error",
                            "action": "replace",
                            "message": "CLI service not initialized (cli_mode=False)"
                        }
                
                # ==================== Tracking Tools ====================
                
                elif action_type == "new_session":
                    clear_session()
                    result = {"status": "success", "action": "new_session", "message": "Session cleared. Todo and scratchpad wiped. Ready for new task."}
                    results.append(result)
                
                elif action_type == "create_todo":
                    value = action_item.get("value", "")
                    todo_output = create_todo(value)
                    result = {"status": "success", "action": "create_todo", "output": todo_output}
                    results.append(result)
                
                elif action_type == "update_todo":
                    step = action_item.get("step", 0)
                    todo_output = update_todo(step)
                    result = {"status": "success", "action": "update_todo", "output": todo_output}
                    results.append(result)
                
                elif action_type == "read_todo":
                    todo_output = read_todo()
                    result = {"status": "success", "action": "read_todo", "output": todo_output}
                    results.append(result)
                
                elif action_type == "write_scratchpad":
                    content = action_item.get("content", "")
                    sp_output = write_scratchpad(content)
                    result = {"status": "success", "action": "write_scratchpad", "output": sp_output}
                    results.append(result)
                
                elif action_type == "read_scratchpad":
                    sp_output = read_scratchpad()
                    result = {"status": "success", "action": "read_scratchpad", "output": sp_output}
                    results.append(result)
            
            if len(results) == 0:
                return {"status": "error", "message": "No valid action found"}
            elif len(results) == 1:
                return results[0]
            else:
                return {"status": "success", "action": "multiple", "results": results}
                
        except Exception as e:
            logger.error(f"Error routing action: {str(e)}")
            return {"status": "error", "message": str(e)}