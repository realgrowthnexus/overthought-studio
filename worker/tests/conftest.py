import base64, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MASTER_KEY", base64.b64encode(b"k" * 32).decode())
