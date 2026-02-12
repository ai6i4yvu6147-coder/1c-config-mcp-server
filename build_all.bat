@echo off
echo Building all components...

echo.
echo [1/3] Building Admin Tool v1...
call venv\Scripts\activate.bat
pyinstaller --onedir --windowed --name "1C-Config-Admin-v1" --noconfirm ^
    --hidden-import=sqlite3 ^
    --hidden-import=xml.etree.ElementTree ^
    --hidden-import=xml.etree ^
    --collect-all xml ^
    --add-data "admin_tool;admin_tool" ^
    --add-data "shared;shared" ^
    admin_tool/gui.py

echo.
echo [2/3] Building Admin Tool v2...
pyinstaller --onedir --windowed --name "1C-Config-Admin" --noconfirm ^
    --hidden-import=sqlite3 ^
    --hidden-import=uuid ^
    --hidden-import=json ^
    --hidden-import=xml.etree.ElementTree ^
    --hidden-import=xml.etree ^
    --collect-all xml ^
    --add-data "admin_tool;admin_tool" ^
    --add-data "shared;shared" ^
    admin_tool/gui_v2.py

echo.
echo [3/3] Building MCP Server...
pyinstaller --onedir --name "1c-config-server" --noconfirm ^
    --hidden-import=sqlite3 ^
    --hidden-import=uuid ^
    --hidden-import=json ^
    --hidden-import=asyncio ^
    --hidden-import=xml.etree.ElementTree ^
    --hidden-import=xml.etree ^
    --collect-all xml ^
    --add-data "server;server" ^
    --add-data "shared;shared" ^
    server/server.py

echo.
echo Creating Portable folder structure...
if exist "Portable" rmdir /s /q "Portable"
mkdir Portable
mkdir Portable\databases

echo Copying Admin Tool v2...
xcopy /E /I /Y dist\1C-Config-Admin Portable\Admin

echo Copying MCP Server...
xcopy /E /I /Y dist\1c-config-server Portable\Server

echo Creating launchers...
echo @echo off > Portable\Admin.bat
echo start "" "%%~dp0Admin\1C-Config-Admin.exe" >> Portable\Admin.bat

echo @echo off > Portable\Server.bat
echo "%%~dp0Server\1c-config-server.exe" >> Portable\Server.bat

echo Copying README...
copy Portable\README.txt Portable\README.txt 2>nul

echo.
echo Done! Portable structure:
echo   Portable/
echo     Admin/           - Admin GUI v2 (with Projects)
echo     Server/          - MCP Server
echo     databases/       - Your databases
echo     projects.json    - Projects configuration
echo     Admin.bat        - Launch Admin
echo     Server.bat       - Launch Server (for testing)
echo.
echo Build completed successfully!