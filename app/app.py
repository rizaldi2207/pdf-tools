import os
import uuid
import zipfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, abort
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import pikepdf

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 52428800))

UPLOAD_DIR = Path("/app/uploads")
OUTPUT_DIR = Path("/app/outputs")
DPI = int(os.environ.get("OUTPUT_DPI", 150))
ALLOWED_EXT = {"pdf"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def cleanup_old_jobs(max_jobs: int = 50):
    jobs = sorted(
        (p for p in OUTPUT_DIR.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
    )
    for job in jobs[:-max_jobs]:
        shutil.rmtree(job, ignore_errors=True)


def save_upload(file, job_id: str) -> Path:
    path = UPLOAD_DIR / f"{job_id}.pdf"
    file.save(path)
    return path


def decrypt_pdf(src: Path, password: str, job_id: str) -> Path:
    """Opens a password-protected PDF and saves a decrypted copy."""
    out = UPLOAD_DIR / f"{job_id}_dec.pdf"
    try:
        with pikepdf.open(str(src), password=password) as pdf:
            pdf.save(str(out))
    except pikepdf.PasswordError:
        raise ValueError("Incorrect PDF password")
    return out


# ── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", active_page="converter")


@app.route("/protect")
def protect_page():
    return render_template("protect.html", active_page="protect")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ── Convert: PDF → Images ─────────────────────────────────────────────────────

@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file. Only PDF is allowed"}), 400

    fmt = request.form.get("format", "png").lower()
    if fmt not in ("png", "jpeg"):
        fmt = "png"

    dpi = request.form.get("dpi", DPI)
    try:
        dpi = int(dpi)
        dpi = max(72, min(dpi, 300))
    except (ValueError, TypeError):
        dpi = DPI

    password = request.form.get("password", "").strip()

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    upload_path = save_upload(file, job_id)
    decrypted_path = None

    try:
        if password:
            decrypted_path = decrypt_pdf(upload_path, password, job_id)
            pdf_path = decrypted_path
        else:
            pdf_path = upload_path

        pages = convert_from_path(str(pdf_path), dpi=dpi)
    except ValueError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
    finally:
        upload_path.unlink(missing_ok=True)
        if decrypted_path:
            decrypted_path.unlink(missing_ok=True)

    ext = "jpg" if fmt == "jpeg" else "png"
    images = []
    for i, page in enumerate(pages, start=1):
        filename = f"page_{i:03d}.{ext}"
        page.save(str(job_dir / filename), fmt.upper())
        images.append({
            "page": i,
            "filename": filename,
            "url": f"/image/{job_id}/{filename}",
            "width": page.width,
            "height": page.height,
        })

    cleanup_old_jobs()

    return jsonify({
        "job_id": job_id,
        "total_pages": len(pages),
        "format": fmt,
        "dpi": dpi,
        "images": images,
        "zip_url": f"/download/{job_id}",
    })


# ── Convert: PDF → DOCX ───────────────────────────────────────────────────────

@app.route("/convert-docx", methods=["POST"])
def convert_docx():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file. Only PDF is allowed"}), 400

    password = request.form.get("password", "").strip()

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    upload_path = save_upload(file, job_id)
    decrypted_path = None

    try:
        if password:
            decrypted_path = decrypt_pdf(upload_path, password, job_id)
            pdf_path = decrypted_path
        else:
            pdf_path = upload_path

        from pdf2docx import Converter
        cv = Converter(str(pdf_path))
        cv.convert(str(job_dir / "converted.docx"))
        cv.close()
    except ValueError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
    finally:
        upload_path.unlink(missing_ok=True)
        if decrypted_path:
            decrypted_path.unlink(missing_ok=True)

    cleanup_old_jobs()
    return jsonify({"job_id": job_id, "download_url": f"/download-docx/{job_id}"})


# ── Protect: Add password to PDF ─────────────────────────────────────────────

@app.route("/add-password", methods=["POST"])
def add_password():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file. Only PDF is allowed"}), 400

    user_pw = request.form.get("user_password", "").strip()
    if not user_pw:
        return jsonify({"error": "Open password is required"}), 400

    owner_pw = request.form.get("owner_password", "").strip() or user_pw
    current_pw = request.form.get("current_password", "").strip()
    enc = request.form.get("encryption", "256")
    R = 6 if enc == "256" else 4

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    upload_path = save_upload(file, job_id)

    try:
        open_kwargs = {"password": current_pw} if current_pw else {}
        with pikepdf.open(str(upload_path), **open_kwargs) as pdf:
            pdf.save(
                str(job_dir / "protected.pdf"),
                encryption=pikepdf.Encryption(
                    user=user_pw,
                    owner=owner_pw,
                    R=R,
                    allow=pikepdf.Permissions(print_highres=True, extract=True),
                ),
            )
    except pikepdf.PasswordError:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "Incorrect current password"}), 400
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"Failed to protect PDF: {str(e)}"}), 500
    finally:
        upload_path.unlink(missing_ok=True)

    cleanup_old_jobs()
    return jsonify({"job_id": job_id, "download_url": f"/download-protected/{job_id}"})


# ── File serving ──────────────────────────────────────────────────────────────

@app.route("/image/<job_id>/<filename>")
def serve_image(job_id: str, filename: str):
    safe_filename = secure_filename(filename)
    path = OUTPUT_DIR / job_id / safe_filename
    if not path.exists() or not path.is_file():
        abort(404)
    return send_file(str(path))


@app.route("/download/<job_id>")
def download_zip(job_id: str):
    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists():
        abort(404)
    zip_path = OUTPUT_DIR / f"{job_id}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in sorted(job_dir.iterdir()):
            zf.write(img, img.name)
    response = send_file(str(zip_path), as_attachment=True, download_name="converted_pages.zip")
    zip_path.unlink(missing_ok=True)
    return response


@app.route("/download-docx/<job_id>")
def download_docx(job_id: str):
    path = OUTPUT_DIR / job_id / "converted.docx"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="converted.docx")


@app.route("/download-protected/<job_id>")
def download_protected(job_id: str):
    path = OUTPUT_DIR / job_id / "protected.pdf"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="protected.pdf")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
