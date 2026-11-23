"""Download the pinned Kokoro voice model into /opt/kokoro (run at image build; sha256-checked)."""
import hashlib, os, urllib.request
d = "/opt/kokoro"; os.makedirs(d, exist_ok=True)
files = [
    ("kokoro-v1.0-timestamped.onnx",
     "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped/resolve/"
     "dd4401a9add81ac692d20e240d22ec9dda82cc29/onnx/model.onnx",
     "651ea8291843a92276a4a003581a215cb07d15e47dde6fcfb1b768f9a1682054"),
    ("voices-v1.0.bin",
     "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
     "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
]
for name, url, sha in files:
    path = os.path.join(d, name)
    for attempt in range(4):
        try:
            urllib.request.urlretrieve(url, path)
            break
        except Exception as e:
            if attempt == 3:
                raise
            print("retrying", name, e)
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    assert got == sha, f"{name}: sha256 {got} != {sha}"
    print("ok", name, os.path.getsize(path))
