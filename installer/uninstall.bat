@echo off
setlocal enableextensions
title Qualys2Human - Desinstallation
echo.
echo ================================================
echo   Qualys2Human - Desinstallation
echo   NeoRed (c) 2026
echo ================================================
echo.

:: Check admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Ce script doit etre execute en tant qu'administrateur.
    pause
    exit /b 1
)

:: Use embedded Python from the package
set "PYTHON=%~dp0..\python\python.exe"
if not exist "%PYTHON%" (
    echo [ERREUR] Python embarque non trouve: %PYTHON%
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0uninstall.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] La desinstallation a echoue.
    pause
    exit /b 1
)

echo.
pause
