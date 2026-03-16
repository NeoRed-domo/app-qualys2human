@echo off
setlocal enableextensions
title Qualys2Human - Installation
echo.
echo ================================================
echo   Qualys2Human - Installation
echo   NeoRed (c) 2026
echo ================================================
echo.

:: Check admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERREUR] Ce script doit etre execute en tant qu'administrateur.
    echo Faites un clic droit ^> Executer en tant qu'administrateur.
    pause
    exit /b 1
)

:: Use embedded Python from the package
set "PYTHON=%~dp0..\python\python.exe"
if not exist "%PYTHON%" (
    echo [ERREUR] Python embarque non trouve: %PYTHON%
    echo Le package semble incomplet.
    pause
    exit /b 1
)

:: Run the setup script
echo Lancement de l'installateur...
echo.
"%PYTHON%" "%~dp0setup.py" %*

if %errorlevel% neq 0 (
    echo.
    echo [ERREUR] L'installation a echoue. Consultez les messages ci-dessus.
    pause
    exit /b 1
)

echo.
pause
