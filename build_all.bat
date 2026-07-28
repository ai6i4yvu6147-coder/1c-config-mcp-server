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
rem Built from the tracked .spec, not CLI flags: PyInstaller regenerates (overwrites) a same-named
rem .spec whenever --name is passed without pointing at an existing spec file, which has silently
rem dropped datas entries (e.g. docs/agent-guide.md) in the past. The .spec is the source of truth.
pyinstaller 1C-Config-Admin.spec --noconfirm

echo.
echo [2/3] Building MCP Server...
pyinstaller 1c-config-server.spec --noconfirm

echo.
echo [3/3] Building Admin Hub CLI...
pyinstaller 1c-config-cli.spec --noconfirm

echo.
echo Verifying agent guide shipped in build outputs...
if not exist "dist\1c-config-server\_internal\docs\agent-guide.md" (
    echo ERROR: dist\1c-config-server\_internal\docs\agent-guide.md missing after build.
    echo Check the datas entry in 1c-config-server.spec.
    exit /b 1
)

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
