import pytest


@pytest.fixture(autouse=True)
def no_external_analyst_in_unit_tests(monkeypatch):
    """Like mocked Ollama clients, unit tests must not depend on installed models.

    Analyst-specific tests inject a deterministic backend. Real Argos is verified
    separately by the local end-to-end smoke test.
    """
    from arayzt.analyst import ArgosBackend
    def unavailable(self):
        raise RuntimeError('analyst_test_backend_unavailable')
    monkeypatch.setattr(ArgosBackend, '__init__', unavailable)
