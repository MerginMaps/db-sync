@echo off

set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul') do (
	if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
	echo Python was not found on PATH.
	exit /b 1
)

for %%D in ("%PYTHON_EXE%") do set "PYTHON_DIR=%%~dpD"

set "SQLITE3_DLL="
for /f "delims=" %%S in ('where /r %PYTHON_DIR% sqlite3.dll 2^>nul') do (
	if not defined SQLITE3_DLL set "SQLITE3_DLL=%%S"
)

if not defined SQLITE3_DLL (
	echo sqlite3.dll was not found in Python directory. Check your Python environment.
	exit /b 1
)

for /f "delims=" %%G in ('python -c "import pygeodiff, os, glob; d = os.path.dirname(os.path.abspath(pygeodiff.__file__)); pyd = glob.glob(os.path.join(d, 'pygeodiff*.pyd')); print(pyd[0] if pyd else '')" 2^>nul') do set "PYGEODIFF_PYD=%%G"

if not exist "%PYGEODIFF_PYD%" (
	echo pygeodiff*.pyd was not found. Check your Python environment.
	exit /b 1
)

pyinstaller ../dbsync_daemon.py ^
	-c ^
	--noconfirm ^
	--add-binary="./windows_binaries/geodiff.exe;lib" ^
	--hidden-import dynaconf ^
	--hidden-import sqlite3 ^
	--hidden-import pygeodiff ^
	--collect-all mergin ^
	--collect-all sqlite3 ^
	--collect-all pygeodiff ^
	--add-binary="%PYGEODIFF_PYD%;pygeodiff" ^
	--add-binary="%SQLITE3_DLL%;." ^
	--clean ^
	-F