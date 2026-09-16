"""Lokaler Entwicklungsstart ohne Docker:  python run.py  (Daten landen in ./data)"""
import os

os.environ.setdefault("DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("BASE_URL", "http://localhost:8080")

from app import create_app  # noqa: E402

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8080, debug=True)
