import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/convert")
def convert():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(error="Missing file"), 400
    if not uploaded.filename.lower().endswith(".pptx"):
        return jsonify(error="Only .pptx files are supported"), 400

    workdir = Path(tempfile.mkdtemp(prefix="pptx2pdf-"))
    try:
        source = workdir / "input.pptx"
        uploaded.save(source)
        subprocess.run(
            [
                "libreoffice", "--headless", "--convert-to", "pdf",
                "--outdir", str(workdir), str(source)
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        output = workdir / "input.pdf"
        if not output.exists():
            return jsonify(error="PDF was not generated"), 500
        download_name = Path(uploaded.filename).stem + ".pdf"
        return send_file(
            output,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=download_name,
        )
    except subprocess.TimeoutExpired:
        return jsonify(error="Conversion timed out"), 504
    except subprocess.CalledProcessError as exc:
        return jsonify(error="LibreOffice conversion failed"), 500
    finally:
        # send_file reads the file before teardown in the normal Flask flow.
        pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
