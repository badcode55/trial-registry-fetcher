@echo off
cd /d "%~dp0\.."
python -m trial_registry.cli --input-file examples\literature_ids.txt --input-format txt --formats csv --output-dir output
echo.
echo Done. Results are in the output folder.
pause
