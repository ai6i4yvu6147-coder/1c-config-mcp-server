@echo off
echo Building all components...

echo.
call venv\Scripts\activate.bat
echo [1/2] Building Admin Tool v2...
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
echo [2/2] Building MCP Server...
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
echo Creating Portable folder structure in parent directory...
set "PORTABLE_ROOT=..\1c_config_mcp_server_Portable"
if exist "%PORTABLE_ROOT%" rmdir /s /q "%PORTABLE_ROOT%"
mkdir "%PORTABLE_ROOT%"
mkdir "%PORTABLE_ROOT%\databases"

echo Copying Admin Tool v2...
xcopy /E /I /Y dist\1C-Config-Admin "%PORTABLE_ROOT%\Admin"

echo Copying MCP Server...
xcopy /E /I /Y dist\1c-config-server "%PORTABLE_ROOT%\Server"

echo Creating launchers...
echo @echo off > "%PORTABLE_ROOT%\Admin.bat"
echo start "" "%%~dp0Admin\1C-Config-Admin.exe" >> "%PORTABLE_ROOT%\Admin.bat"

echo @echo off > "%PORTABLE_ROOT%\Server.bat"
echo "%%~dp0Server\1c-config-server.exe" >> "%PORTABLE_ROOT%\Server.bat"

echo.
echo Done! Portable structure: %PORTABLE_ROOT%\
echo     Admin/           - Admin GUI v2 (with Projects)
echo     Server/          - MCP Server
echo     databases/       - Your databases
echo     projects.json    - Projects configuration
echo     Admin.bat        - Launch Admin
echo     Server.bat       - Launch Server (for testing)
echo.
echo Build completed successfully!