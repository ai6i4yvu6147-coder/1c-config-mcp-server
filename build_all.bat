@echo off
echo Building all components...

echo.
echo [1/2] Building Admin Tool...
call venv\Scripts\activate.bat
pyinstaller --onedir --windowed --name "1C-Config-Admin" ^
    --hidden-import=sqlite3 ^
    --hidden-import=xml.etree.ElementTree ^
    --hidden-import=xml.etree ^
    --collect-all xml ^
    --add-data "admin_tool;admin_tool" ^
    --add-data "shared;shared" ^
    admin_tool/gui.py

echo.
echo [2/2] Building MCP Server...
pyinstaller --onedir --name "1c-config-server" ^
    --hidden-import=sqlite3 ^
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

echo Copying Admin Tool...
xcopy /E /I /Y dist\1C-Config-Admin Portable\Admin

echo Copying MCP Server...
xcopy /E /I /Y dist\1c-config-server Portable\Server

echo Creating config...
copy server\config.json Portable\Server\

echo Creating launchers...
echo @echo off > Portable\Admin.bat
echo start "" "%%~dp0Admin\1C-Config-Admin.exe" >> Portable\Admin.bat

echo @echo off > Portable\Server.bat
echo "%%~dp0Server\1c-config-server.exe" >> Portable\Server.bat

echo.
echo Done! Structure:
echo   Portable/
echo     Admin/           - Admin GUI
echo     Server/          - MCP Server
echo     databases/       - Your databases
echo     Admin.bat        - Launch Admin
echo     Server.bat       - Launch Server
pause