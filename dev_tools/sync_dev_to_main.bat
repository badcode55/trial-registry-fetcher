@echo off
cd /d "%~dp0\.."
python dev_tools\sync_dev_to_main.py %*
