"""Standalone examples must be safe to inspect/import without running their work."""

import builtins
import importlib
import sys

import pytest


@pytest.mark.parametrize("module", [
    "tender_iq.prompts.extraction_prompt",
    "tender_iq.extraction.scripts.structured_extractor",
    "tender_iq.extraction.scripts.extract_text",
    "tender_iq.extraction.scripts.extract_table",
    "tender_iq.extraction.scripts.extract_block",
])
def test_import_does_not_start_pdf_or_model_work(module, monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.startswith(("pymupdf", "langchain", "tender_iq.config")):
            raise AssertionError("Importing an example must not load its PDF/model runtime.")
        return original_import(name, *args, **kwargs)

    def no_file_work(*args, **kwargs):
        raise AssertionError("Importing an example must not read/write document files.")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(builtins, "open", no_file_work)
    sys.modules.pop(module, None)
    loaded = importlib.import_module(module)
    assert callable(loaded.main)
