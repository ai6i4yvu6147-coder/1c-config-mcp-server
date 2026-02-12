@echo off
echo Building Admin Tool...
call venv\Scripts\activate.bat
pyinstaller --onefile --windowed --name "1C-Config-Admin" --noconfirm --icon=NONE admin_tool/gui.py
echo Done!