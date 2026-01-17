#!/bin/bash
# Run Vector Viewer application

cd "$(dirname "$0")/src"
pdm run python -m vector_viewer.main
