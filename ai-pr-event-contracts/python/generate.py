"""Regenerate Python classes from the shared Avro schemas.

Usage:
    python generate.py
"""

import json
import os
import subprocess
import sys

SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "ai_pr_event_contracts")

if __name__ == "__main__":
    print("Avro schemas are the source of truth:")
    for name in sorted(os.listdir(SCHEMAS_DIR)):
        if name.endswith(".avsc"):
            print(" -", name)
    print()
    print("Python dataclasses in events.py mirror these schemas.")
    print("Update events.py manually when schemas change, or wire avro.codegen.")
