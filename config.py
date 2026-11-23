"""Load .env (if present) into os.environ. Import this before anything else."""
import os

if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
