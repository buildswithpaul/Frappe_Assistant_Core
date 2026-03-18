# Frappe Assistant Core - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
PaddleOCR model pre-download utility.

Pre-downloads PaddleOCR models during app installation so the first OCR
call doesn't trigger a slow download that may exceed the subprocess timeout.
"""

import json
import subprocess
import sys

import frappe


def warm_paddleocr_models():
    """Pre-download PaddleOCR models in a subprocess.

    Called from the after_install hook. Non-blocking — if the download
    fails (e.g. no network), it logs a warning and the models will be
    downloaded on the first OCR call instead.
    """
    logger = frappe.logger("model_warmup")

    # Read configured language, falling back to "en"
    try:
        settings = frappe.get_single("Assistant Core Settings")
        language = getattr(settings, "ocr_language", "en") or "en"
    except Exception:
        language = "en"

    print(f"Pre-downloading PaddleOCR models for language '{language}'...")
    logger.info(f"Starting PaddleOCR model pre-download (language={language})")

    request_data = json.dumps(
        {
            "action": "warm",
            "language": language,
        }
    )

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "frappe_assistant_core.utils.ocr_subprocess"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Generous timeout — first download on slow networks can take minutes
        stdout, stderr = proc.communicate(
            input=request_data.encode("utf-8"),
            timeout=600,
        )

        if proc.returncode == 0:
            try:
                result = json.loads(stdout.decode("utf-8"))
                logger.info(f"PaddleOCR model pre-download complete: {result.get('message', 'OK')}")
                print(f"PaddleOCR models ready: {result.get('message', 'OK')}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.info("PaddleOCR model pre-download complete (no JSON response)")
                print("PaddleOCR models ready.")
        else:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.warning(
                f"PaddleOCR model pre-download failed (exit {proc.returncode}): {error_msg[:500]}. "
                "Models will be downloaded on the first OCR call."
            )
            print(
                "Warning: PaddleOCR model pre-download failed. "
                "Models will be downloaded automatically on first use."
            )

    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        logger.warning(
            "PaddleOCR model pre-download timed out after 600s. "
            "Models will be downloaded on the first OCR call."
        )
        print(
            "Warning: PaddleOCR model download timed out. "
            "Models will be downloaded automatically on first use."
        )

    except Exception as e:
        logger.warning(
            f"PaddleOCR model pre-download skipped: {str(e)}. "
            "Models will be downloaded on the first OCR call."
        )
        print(
            f"Warning: PaddleOCR model pre-download skipped ({str(e)}). "
            "Models will be downloaded automatically on first use."
        )
