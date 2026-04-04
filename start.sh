#!/bin/bash
# Start Edge Crew v3.0

# Install deps
pip install -r requirements.txt

# Start with Railway's PORT (default 8000)
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
