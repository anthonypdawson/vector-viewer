#!/bin/bash
# Run Vector Viewer application

cd "$(dirname "$0")/.."
cd src
pdm run python -m vector_inspector.main
