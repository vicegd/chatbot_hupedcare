@echo off
setlocal

:: Navigate to the script's folder, then UP one level to the project root
cd /d "%~dp0.."

call npx.cmd --yes @mermaid-js/mermaid-cli -i docs\images\architecture_overview.mmd -o docs\images\architecture_overview.png
if errorlevel 1 exit /b 1

call npx.cmd --yes @mermaid-js/mermaid-cli -i docs\images\experimental_workflow.mmd -o docs\images\experimental_workflow.png
if errorlevel 1 exit /b 1

echo Mermaid diagrams exported successfully.
