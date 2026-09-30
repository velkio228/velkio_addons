"""Rebuild current presentation without overwriting it with legacy branding."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'tools'))
from build_app_presentation import build
if __name__ == '__main__':
    build('access', Path(__file__).resolve().parent)
