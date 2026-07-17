@echo off
echo Building all components...

echo.
call venv\Scripts\activate.bat

echo.
echo Resolving 1c-metadata-schema...
set "METADATA_SCHEMA="
if exist "C:\repo\1c-metadata-schema\pyproject.toml" set "METADATA_SCHEMA=C:\repo\1c-metadata-schema"
if not defined METADATA_SCHEMA if exist "C:\projects\1c-metadata-schema\pyproject.toml" set "METADATA_SCHEMA=C:\projects\1c-metadata-schema"
if not defined METADATA_SCHEMA (
    echo ERROR: 1c-metadata-schema not found. Checked:
    echo   C:\repo\1c-metadata-schema
    echo   C:\projects\1c-metadata-schema
    exit /b 1
)
echo Using: %METADATA_SCHEMA%
pip install -e "%METADATA_SCHEMA%"
if errorlevel 1 (
    echo ERROR: pip install -e failed for %METADATA_SCHEMA%
    exit /b 1
)

echo.
echo [1/3] Building Admin Tool v2...
rem External data processor read side needs onec_metadata_schema bundled (Admin builds DBs).
pyinstaller --onedir --windowed --name "1C-Config-Admin" --noconfirm ^
    --hidden-import=sqlite3 ^
    --hidden-import=uuid ^
    --hidden-import=json ^
    --hidden-import=xml.etree.ElementTree ^
    --hidden-import=xml.etree ^
    --collect-all xml ^
    --collect-submodules onec_metadata_schema ^
    --add-data "admin_tool;admin_tool" ^
    --add-data "shared;shared" ^
    admin_tool/gui_v2.py

echo.
echo [2/3] Building MCP Server...
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
echo [3/3] Building Admin Hub CLI...
rem CLI `rebuild-index` rebuilds DBs (hub_rebuild -> DatabaseManager -> parser), so it needs
rem onec_metadata_schema bundled for external data processors too.
pyinstaller --onefile --name "1c-config-cli" --noconfirm ^
    --hidden-import=sqlite3 ^
    --hidden-import=json ^
    --collect-submodules onec_metadata_schema ^
    --add-data "shared;shared" ^
    admin_tool/cli.py

echo.
echo Creating Portable folder structure in parent directory...
set "PORTABLE_ROOT=..\1c_config_mcp_server_Portable"
if exist "%PORTABLE_ROOT%" rmdir /s /q "%PORTABLE_ROOT%"
mkdir "%PORTABLE_ROOT%"

echo Copying Admin Tool v2...
xcopy /E /I /Y dist\1C-Config-Admin "%PORTABLE_ROOT%\Admin"

echo Copying MCP Server...
xcopy /E /I /Y dist\1c-config-server "%PORTABLE_ROOT%\Server"

echo Copying Hub CLI...
mkdir "%PORTABLE_ROOT%\Tools"
copy /Y dist\1c-config-cli.exe "%PORTABLE_ROOT%\Tools\1c-config-cli.exe"

echo Copying module manifest...
copy /Y module.manifest.example.json "%PORTABLE_ROOT%\module.manifest.json"

echo Creating launchers...
echo @echo off > "%PORTABLE_ROOT%\Admin.bat"
echo start "" "%%~dp0Admin\1C-Config-Admin.exe" >> "%PORTABLE_ROOT%\Admin.bat"

echo @echo off > "%PORTABLE_ROOT%\Server.bat"
echo "%%~dp0Server\1c-config-server.exe" >> "%PORTABLE_ROOT%\Server.bat"

echo.
echo Done! Portable structure: %PORTABLE_ROOT%\
echo     Admin/                 - Admin GUI v2
echo     Server/                - MCP Server
echo     Tools/1c-config-cli.exe - Admin Hub protocol CLI
echo     module.manifest.json   - Module manifest
echo     databases/             - Created on first run
echo     projects.json          - Projects configuration
echo     Admin.bat / Server.bat - Launchers
echo.
echo Build completed successfully!
