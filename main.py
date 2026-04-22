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

import sys
import io

# Force UTF-8 for stdio — MCP uses JSON over stdio and tool descriptions
# contain non-ASCII characters (em-dashes, etc.). Without this, compiled
# binaries or environments with ASCII locale crash with:
#   'ascii' codec can't encode characters in position X-Y: ordinal not in range(128)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

IS_COMPILED = getattr(sys, 'frozen', False) or '__compiled__' in dir()

def _setup_embedded_resources():
    import builtins
    import base64

    try:
        from _embedded_resources import RESOURCES
    except ImportError:
        return False

    _original_open = builtins.open

    def _patched_open(file, mode='r', *args, **kwargs):
        file_str = str(file).replace('\\', '/')

        for res_path, encoded_data in RESOURCES.items():
            if file_str.endswith(res_path) or res_path in file_str:
                file_parts = file_str.split('/')
                res_parts = res_path.split('/')

                if len(file_parts) >= 2 and len(res_parts) >= 2:
                    if file_parts[-1] == res_parts[-1] and file_parts[-2] == res_parts[-2]:
                        pass
                    elif file_str.endswith(res_path):
                        pass
                    else:
                        continue
                elif file_parts[-1] != res_parts[-1]:
                    continue

                content = base64.b64decode(encoded_data)

                if 'b' in mode:
                    return io.BytesIO(content)
                else:
                    encoding = kwargs.get('encoding', 'utf-8')
                    return io.StringIO(content.decode(encoding))

        return _original_open(file, mode, *args, **kwargs)

    builtins.open = _patched_open
    return True

if IS_COMPILED:
    _setup_embedded_resources()

import asyncio

# Platform dispatch — pick the right Auto_Use subpackage at import time.
# sys.platform is "darwin" on macOS, "win32" on Windows.
# The platform-specific binary_build.py scripts pass --nofollow-import-to on the
# inactive branch so each compiled binary only bundles its own platform's code.
if sys.platform == "darwin":
    from Auto_Use.macOS.mcp import run_mcp_server
elif sys.platform == "win32":
    from Auto_Use.windows.mcp import run_mcp_server
else:
    raise RuntimeError(f"AutoUse does not support this platform: {sys.platform}")

asyncio.run(run_mcp_server())