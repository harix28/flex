import builtins
import importlib
import sys

import pytest


def test_audit_dossier_module_import_does_not_require_matplotlib(monkeypatch):
    original_import = builtins.__import__

    def raising_import(name, *args, **kwargs):
        if name == "matplotlib" or name.startswith("matplotlib."):
            raise ModuleNotFoundError("No module named 'matplotlib'", name="matplotlib")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", raising_import)
    sys.modules.pop("sentinel.audit.dossier", None)
    dossier = importlib.import_module("sentinel.audit.dossier")

    with pytest.raises(RuntimeError, match="matplotlib is required"):
        dossier.generate_audit_dossier_pdf(
            machine_code="ENG-001",
            machine_id="m1",
            tenant_id="t1",
            source_binding={},
            data_quality={},
            latest_prediction=None,
            observations=[],
            related_work_orders=[],
        )
