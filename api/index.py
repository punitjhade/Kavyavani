# Vercel entry point: exposes the Flask app as a serverless function.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app  # noqa: E402,F401
