@echo off
cd /d "%~dp0\.."
python scripts\sync_dev_to_main.py %*
