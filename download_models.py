"""
Downloads the Kokoro models required for TTS.
Run once before starting the game:

    python download_models.py
"""
import os
import urllib.request

MODELS_DIR = "models"
FILES = {
    "kokoro-v1.0.onnx": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/kokoro-v1.0.onnx"
    ),
    "voices-v1.0.bin": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
        "model-files-v1.0/voices-v1.0.bin"
    ),
}

os.makedirs(MODELS_DIR, exist_ok=True)

for filename, url in FILES.items():
    dest = os.path.join(MODELS_DIR, filename)
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / 1_000_000
        print(f"{filename} already present ({size_mb:.0f} MB), skipping.")
        continue

    print(f"Downloading {filename}...")

    def _progress(count, block_size, total_size):
        if total_size > 0:
            pct = min(100, count * block_size * 100 // total_size)
            print(f"  {pct}%", end="\r", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    size_mb = os.path.getsize(dest) / 1_000_000
    print(f"  {filename} downloaded ({size_mb:.0f} MB).        ")

print("\nModels ready. You can now run: python app.py")
