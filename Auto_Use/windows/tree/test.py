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
Quick scan test — runs element.py with DEBUG=True so it saves tree.txt + annotated screenshot.
Run: python -m Auto_Use.windows.tree.test
"""

import sys
import os

# Ensure project root is on path when run directly (Auto_Use/windows/tree → repo root is ../../..)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import Auto_Use.windows.tree.element as elem

# Force debug on so save_to_file() and screenshot write to disk
elem.DEBUG = True
elem.SCREENSHOT = True

from Auto_Use.windows.tree.element import UIElementScanner, ELEMENT_CONFIG

print("Scanning screen...")
scanner = UIElementScanner(ELEMENT_CONFIG)
scanner.scan_elements()
scanner.save_to_file()

tree_text, image_b64, uac = scanner.get_scan_data()

print(f"App:      {scanner.application_name}")
print(f"Elements: {len(scanner.get_elements_mapping())}")
print(f"UAC:      {uac}")

if tree_text:
    # Save tree as a simple text file in project root
    with open("tree.txt", "w", encoding="utf-8") as f:
        f.write(tree_text)
    print("Saved:    tree.txt")

if image_b64:
    import base64
    img_bytes = base64.b64decode(image_b64)
    with open("screenshot.png", "wb") as f:
        f.write(img_bytes)
    print("Saved:    screenshot.png")

print("Done.")
