@echo off
setlocal
set SCRIPT_DIR=%~dp0
if exist "%SCRIPT_DIR%\..\python\python.exe" (
    "%SCRIPT_DIR%\..\python\python.exe" "%SCRIPT_DIR%restore-db.py" %*
) else if exist "%SCRIPT_DIR%python\python.exe" (
    "%SCRIPT_DIR%python\python.exe" "%SCRIPT_DIR%restore-db.py" %*
) else (
    python "%SCRIPT_DIR%restore-db.py" %*
)
