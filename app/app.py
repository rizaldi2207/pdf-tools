import os
import re
import uuid
import zipfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template, abort
from werkzeug.utils import secure_filename
from pdf2image import convert_from_path
import pikepdf
import mammoth

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 52428800))

UPLOAD_DIR = Path("/app/uploads")
OUTPUT_DIR = Path("/app/outputs")
DPI = int(os.environ.get("OUTPUT_DPI", 150))
ALLOWED_EXT = {"pdf"}
ALLOWED_DOCX_EXT = {"docx"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def allowed_docx_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOCX_EXT


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


def save_docx_upload(file, job_id: str) -> Path:
    path = UPLOAD_DIR / f"{job_id}.docx"
    file.save(path)
    return path


_LATIN1_MAP = str.maketrans({
    "•": "-",    # bullet •
    "–": "-",    # en dash –
    "—": "--",   # em dash —
    "‘": "'",    # left single quote '
    "’": "'",    # right single quote '
    "“": '"',    # left double quote "
    "”": '"',    # right double quote "
    "…": "...",  # ellipsis …
    " ": " ",    # non-breaking space
    "‑": "-",    # non-breaking hyphen
    "‒": "-",    # figure dash
    "―": "--",   # horizontal bar
})


def _to_latin1(text: str) -> str:
    text = text.translate(_LATIN1_MAP)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.replace("\t", "    ")
    return text.encode("latin-1", errors="replace").decode("latin-1")


def docx_to_pdf(src: Path, output_dir: Path) -> Path:
    from fpdf import FPDF
    from fpdf.enums import WrapMode

    with open(str(src), "rb") as f:
        md = mammoth.convert_to_markdown(f).value

    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    def write(style: str, size: int, text: str, line_h: float) -> None:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", style, size)
        pdf.multi_cell(0, line_h, text, wrapmode=WrapMode.CHAR)

    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
        elif stripped.startswith("### "):
            write("B", 12, _to_latin1(stripped[4:]), 7)
            pdf.ln(1)
        elif stripped.startswith("## "):
            write("B", 14, _to_latin1(stripped[3:]), 9)
            pdf.ln(2)
        elif stripped.startswith("# "):
            write("B", 18, _to_latin1(stripped[2:]), 11)
            pdf.ln(3)
        elif re.match(r"^[*\-] ", stripped):
            write("", 11, "- " + _to_latin1(stripped[2:]), 7)
        else:
            clean = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
            clean = re.sub(r"\*(.+?)\*", r"\1", clean)
            write("", 11, _to_latin1(clean), 7)

    pdf_path = output_dir / "converted.pdf"
    pdf.output(str(pdf_path))
    return pdf_path


def docx_to_md(src: Path, output_dir: Path) -> Path:
    with open(str(src), "rb") as f:
        result = mammoth.convert_to_markdown(f)
    md_path = output_dir / "converted.md"
    md_path.write_text(result.value, encoding="utf-8")
    return md_path


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
def home():
    return render_template("landing.html")


@app.route("/pdf-tools/convert")
def index():
    return render_template("index.html", active_page="converter")


@app.route("/pdf-tools/protect")
def protect_page():
    return render_template("protect.html", active_page="protect")


@app.route("/pdf-tools/docx-converter", methods=["GET"])
def docx_converter_page():
    return render_template("docx_converter.html", active_page="docx_converter")


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


# ── Convert: PDF → PPTX ───────────────────────────────────────────────────────

def pdf_to_pptx(pdf_path: Path, output_dir: Path, dpi: int) -> Path:
    """Renders each PDF page as an image and places it full-bleed on its own slide."""
    import io
    from pptx import Presentation
    from pptx.util import Emu

    pages = convert_from_path(str(pdf_path), dpi=dpi)
    if not pages:
        raise RuntimeError("PDF has no pages")

    prs = Presentation()
    # Slide size follows the first page's aspect ratio, 10 inches wide.
    first = pages[0]
    slide_w = Emu(9144000)
    slide_h = Emu(int(slide_w * first.height / first.width))
    prs.slide_width = slide_w
    prs.slide_height = slide_h
    blank_layout = prs.slide_layouts[6]

    for page in pages:
        slide = prs.slides.add_slide(blank_layout)
        buf = io.BytesIO()
        page.convert("RGB").save(buf, "JPEG", quality=92)
        buf.seek(0)

        # Fit page inside the slide while preserving its aspect ratio, centered.
        scale = min(slide_w / page.width, slide_h / page.height)
        w, h = int(page.width * scale), int(page.height * scale)
        left, top = (slide_w - w) // 2, (slide_h - h) // 2
        slide.shapes.add_picture(buf, left, top, width=w, height=h)

    pptx_path = output_dir / "converted.pptx"
    prs.save(str(pptx_path))
    return pptx_path


def _clean_font_name(name: str) -> str:
    """'ABCDEF+Arial-BoldMT' → 'Arial', 'TimesNewRoman,Bold' → 'TimesNewRoman'."""
    name = name.split("+")[-1]
    name = re.split(r"[,-]", name)[0]
    name = re.sub(r"(MT|PS)$", "", name)
    return name or "Arial"


def pdf_to_pptx_editable(pdf_path: Path, output_dir: Path, dpi: int) -> Path:
    """
    Builds a PPTX with editable text: each horizontal text line becomes a text box
    (position, size, font, color, bold/italic preserved). The page with its text
    removed (images, vector graphics, backgrounds) is rendered as the slide background.
    """
    import io
    import pymupdf
    from PIL import Image
    from pptx import Presentation
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import MSO_AUTO_SIZE

    EMU_PER_PT = 12700

    doc = pymupdf.open(str(pdf_path))
    if doc.page_count == 0:
        raise RuntimeError("PDF has no pages")

    prs = Presentation()
    first = doc[0].rect
    prs.slide_width = Emu(int(first.width * EMU_PER_PT))
    prs.slide_height = Emu(int(first.height * EMU_PER_PT))
    blank_layout = prs.slide_layouts[6]

    for page in doc:
        page_w, page_h = page.rect.width, page.rect.height
        scale = min(prs.slide_width / (page_w * EMU_PER_PT), prs.slide_height / (page_h * EMU_PER_PT))
        off_x = (prs.slide_width - page_w * EMU_PER_PT * scale) / 2
        off_y = (prs.slide_height - page_h * EMU_PER_PT * scale) / 2

        def emu(v: float, offset: float) -> Emu:
            return Emu(int(offset + v * EMU_PER_PT * scale))

        # 1. Collect horizontal text lines (rotated text stays in the background image).
        lines = []
        text = page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)
        for block in text["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                dx, dy = line["dir"]
                if abs(dy) > 0.01 or dx <= 0:
                    continue
                spans = [s for s in line["spans"] if s["text"]]
                if not spans or not "".join(s["text"] for s in spans).strip():
                    continue
                lines.append((pymupdf.Rect(line["bbox"]), spans))

        # 2. Remove extracted text from the page, keep images and vector graphics.
        for rect, spans in lines:
            for s in spans:
                page.add_redact_annot(pymupdf.Rect(s["bbox"]), fill=False)
        if lines:
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
            )

        # 3. Background: render the text-free page.
        slide = prs.slides.add_slide(blank_layout)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        buf.seek(0)
        slide.shapes.add_picture(
            buf, emu(0, off_x), emu(0, off_y),
            width=emu(page_w, 0), height=emu(page_h, 0),
        )

        # 4. Editable text boxes, one per line.
        for rect, spans in lines:
            box = slide.shapes.add_textbox(
                emu(rect.x0, off_x), emu(rect.y0, off_y),
                emu(rect.width, 0), emu(rect.height, 0),
            )
            tf = box.text_frame
            tf.word_wrap = False
            tf.auto_size = MSO_AUTO_SIZE.NONE
            tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
            para = tf.paragraphs[0]
            for s in spans:
                run = para.add_run()
                run.text = s["text"]
                font = run.font
                font.size = Pt(max(1, round(s["size"] * scale, 1)))
                font.name = _clean_font_name(s["font"])
                font.bold = bool(s["flags"] & pymupdf.TEXT_FONT_BOLD) or "bold" in s["font"].lower()
                font.italic = bool(s["flags"] & pymupdf.TEXT_FONT_ITALIC)
                c = s["color"]
                font.color.rgb = RGBColor((c >> 16) & 255, (c >> 8) & 255, c & 255)

    doc.close()
    pptx_path = output_dir / "converted.pptx"
    prs.save(str(pptx_path))
    return pptx_path


@app.route("/convert-pptx", methods=["POST"])
def convert_pptx():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file. Only PDF is allowed"}), 400

    dpi = request.form.get("dpi", DPI)
    try:
        dpi = max(72, min(int(dpi), 300))
    except (ValueError, TypeError):
        dpi = DPI

    mode = request.form.get("mode", "editable").lower()
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

        if mode == "image":
            pdf_to_pptx(pdf_path, job_dir, dpi)
        else:
            pdf_to_pptx_editable(pdf_path, job_dir, dpi)
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
    return jsonify({"job_id": job_id, "download_url": f"/download-pptx/{job_id}"})


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


# ── Convert: DOCX → PDF / Markdown ───────────────────────────────────────────

@app.route("/convert-docx-to-pdf", methods=["POST"])
def convert_docx_to_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_docx_file(file.filename):
        return jsonify({"error": "Invalid file. Only DOCX is allowed"}), 400

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    upload_path = save_docx_upload(file, job_id)

    try:
        docx_to_pdf(upload_path, job_dir)
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
    finally:
        upload_path.unlink(missing_ok=True)

    cleanup_old_jobs()
    return jsonify({"job_id": job_id, "download_url": f"/download-pdf-from-docx/{job_id}"})


@app.route("/convert-docx-to-md", methods=["POST"])
def convert_docx_to_md():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_docx_file(file.filename):
        return jsonify({"error": "Invalid file. Only DOCX is allowed"}), 400

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    upload_path = save_docx_upload(file, job_id)

    try:
        docx_to_md(upload_path, job_dir)
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"Conversion failed: {str(e)}"}), 500
    finally:
        upload_path.unlink(missing_ok=True)

    cleanup_old_jobs()
    return jsonify({"job_id": job_id, "download_url": f"/download-md-from-docx/{job_id}"})


# ── Unprotect: Remove password from PDF ──────────────────────────────────────

@app.route("/remove-password", methods=["POST"])
def remove_password():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file. Only PDF is allowed"}), 400

    password = request.form.get("password", "").strip()
    if not password:
        return jsonify({"error": "Password is required"}), 400

    job_id = uuid.uuid4().hex
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    upload_path = save_upload(file, job_id)

    try:
        with pikepdf.open(str(upload_path), password=password) as pdf:
            pdf.save(str(job_dir / "unprotected.pdf"))
    except pikepdf.PasswordError:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "Incorrect password"}), 400
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": f"Failed to remove password: {str(e)}"}), 500
    finally:
        upload_path.unlink(missing_ok=True)

    cleanup_old_jobs()
    return jsonify({"job_id": job_id, "download_url": f"/download-unprotected/{job_id}"})


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


@app.route("/download-pptx/<job_id>")
def download_pptx(job_id: str):
    path = OUTPUT_DIR / job_id / "converted.pptx"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="converted.pptx")


@app.route("/download-protected/<job_id>")
def download_protected(job_id: str):
    path = OUTPUT_DIR / job_id / "protected.pdf"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="protected.pdf")


@app.route("/download-unprotected/<job_id>")
def download_unprotected(job_id: str):
    path = OUTPUT_DIR / job_id / "unprotected.pdf"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="unprotected.pdf")


@app.route("/download-pdf-from-docx/<job_id>", methods=["GET"])
def download_pdf_from_docx(job_id: str):
    path = OUTPUT_DIR / job_id / "converted.pdf"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="converted.pdf")


@app.route("/download-md-from-docx/<job_id>", methods=["GET"])
def download_md_from_docx(job_id: str):
    path = OUTPUT_DIR / job_id / "converted.md"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name="converted.md")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
