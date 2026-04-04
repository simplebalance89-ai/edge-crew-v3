#!/bin/bash
# Edge Crew v3.0 Start Script for Railway

# Install dependencies
pip install -r requirements.txt

# Start the app
uvicorn main:app --host 0.0.0.0 --port $PORT
