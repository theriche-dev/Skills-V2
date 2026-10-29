@echo off
chcp 65001 >nul
title Telecommande TV
cd /d "%~dp0"
echo.
echo  === Telecommande TV ===
echo.

rem Trouve Python : le lanceur "py", sinon "python", sinon une installation par utilisateur.
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY call :find_installed

if not defined PY (
  echo  Python n'est pas installe. Installation automatique, patiente une minute...
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  call :find_installed
)

if not defined PY (
  echo.
  echo  Impossible d'installer Python automatiquement.
  echo  Installe-le depuis https://www.python.org/downloads/ en cochant "Add python.exe to PATH",
  echo  puis double-clique encore sur ce fichier.
  echo.
  pause
  exit /b 1
)

echo  Si Windows demande d'autoriser Python sur le reseau : coche "Reseaux prives" puis "Autoriser".
echo  Sinon l'iPhone ne pourra pas joindre la telecommande.
echo.
%PY% ".claude\skills\tv-detox\remote\remote.py" --open %*
echo.
pause
exit /b

:find_installed
for %%P in ("%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" "%WINDIR%\py.exe") do (
  if exist %%P set "PY="%%~P" -3" & exit /b
)
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
  if exist "%%D\python.exe" set "PY="%%D\python.exe"" & exit /b
)
exit /b
