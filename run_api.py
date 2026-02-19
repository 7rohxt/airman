#!/usr/bin/env python
"""
Quick test of the FastAPI app without Docker.

Run: python run_api.py

Then open browser: http://localhost:8000/docs
"""
import sys
sys.path.insert(0, ".")

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )