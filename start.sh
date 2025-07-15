#!/bin/bash
gunicorn bot:run_bot --workers 1 --threads 1 --bind 0.0.0.0:$PORT --timeout 0
