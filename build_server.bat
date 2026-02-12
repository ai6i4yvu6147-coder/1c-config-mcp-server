@echo off
echo Building MCP Server...
call venv\Scripts\activate.bat
pyinstaller --onefile --name "1c-config-server" --noconfirm server/server.py
echo Done!