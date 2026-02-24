# -*- coding: utf-8 -*-
"""
Author: rahn
Datum: 24.02.2026
Version: 1.0
Beschreibung: Ergänzende Regressionstests fuer E-Mail- und Request-ID-Redaktion.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.library_sanitizer import (
    sanitize_text,
    sanitize_structure,
    prepare_archive_payload,
)


def test_redact_email():
    text = "Kontakt: user@example.com"
    sanitized = sanitize_text(text)
    assert sanitized == "Kontakt: [REDACTED_EMAIL]"


def test_redact_request_id():
    text = "Request ID: 123e4567-e89b-12d3-a456-426614174000"
    sanitized = sanitize_text(text)
    assert sanitized == "Request ID: [REDACTED_REQUEST_ID]"


def test_sanitize_structure_redacts_email():
    value = {"message": "Mail user@example.com"}
    sanitized = sanitize_structure(value)
    assert sanitized["message"] == "Mail [REDACTED_EMAIL]"


def test_prepare_archive_payload_redacts_request_id():
    project = {"entries": [{"type": "log", "content": "Request ID: 123e4567-e89b-12d3-a456-426614174000"}]}
    sanitized = prepare_archive_payload(project)
    assert sanitized["entries"][0]["content"] == "Request ID: [REDACTED_REQUEST_ID]"
