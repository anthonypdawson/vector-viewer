@echo off
REM Run Vector Viewer application

cd /d %~dp0src
pdm run python -m vector_inspector.main
