import types
import pytest
from app.services import llm_service as gs


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content_or_exc):
        self._c = content_or_exc
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if isinstance(self._c, Exception):
            raise self._c
        return _FakeResponse(self._c)


class _FakeChat:
    def __init__(self, content_or_exc):
        self.completions = _FakeCompletions(content_or_exc)


class _FakeClient:
    def __init__(self, content_or_exc):
        self.chat = _FakeChat(content_or_exc)


def _patch_client(monkeypatch, content_or_exc):
    fake = _FakeClient(content_or_exc)
    monkeypatch.setattr(gs, "_get_client", lambda: fake)
    return fake


def _make_job(**kw):
    defaults = dict(
        title="Eng", company="Acme", location="NYC",
        description="desc", salary_min=None, salary_max=None,
        salary_currency=None,
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def _make_profile(**kw):
    defaults = dict(
        linkedin_url=None, skills="python",
        current_title="Dev", target_title="Senior Dev",
        years_experience=5,
    )
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


# --- Parser tests ---

def test_parse_json_clean():
    out = gs._parse_json_response('{"fit_score": 80, "fit_summary": "good", "salary_estimated": null}')
    assert out == {"fit_score": 80, "fit_summary": "good", "salary_estimated": None}


def test_parse_json_with_code_fence():
    raw = '```json\n{"fit_score": 50, "fit_summary": "x", "salary_estimated": "$80k"}\n```'
    out = gs._parse_json_response(raw)
    assert out["fit_score"] == 50
    assert out["salary_estimated"] == "$80k"


def test_parse_json_garbage_returns_fallback():
    out = gs._parse_json_response("not json at all")
    assert out == gs.FIT_SAFE_FALLBACK


def test_parse_recommendations_clean():
    out = gs._parse_recommendations_response('{"recommendations": ["a","b","c"]}')
    assert out == ["a", "b", "c"]


def test_parse_recommendations_garbage():
    assert gs._parse_recommendations_response("garbage") == []


# --- Integration tests with mocked client ---

def test_get_fit_score_calls_correct_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    fake = _patch_client(monkeypatch,
        '{"fit_score": 75, "fit_summary": "solid", "salary_estimated": "$100k-$120k"}')
    result = gs.get_fit_score_and_salary(_make_job(), _make_profile())
    assert fake.chat.completions.last_kwargs["model"] == "llama-3.1-8b-instant"
    assert result["fit_score"] == 75
    assert result["fit_summary"] == "solid"
    assert result["salary_estimated"] == "$100k-$120k"


def test_get_fit_score_user_prompt_contains_job_and_profile(monkeypatch):
    fake = _patch_client(monkeypatch,
        '{"fit_score": 60, "fit_summary": "ok", "salary_estimated": null}')
    gs.get_fit_score_and_salary(
        _make_job(title="Backend Engineer"),
        _make_profile(target_title="Staff Engineer"),
    )
    msgs = fake.chat.completions.last_kwargs["messages"]
    user_content = msgs[1]["content"]
    assert "Backend Engineer" in user_content
    assert "Staff Engineer" in user_content


def test_get_fit_score_listed_salary_in_prompt(monkeypatch):
    fake = _patch_client(monkeypatch,
        '{"fit_score": 60, "fit_summary": "ok", "salary_estimated": null}')
    gs.get_fit_score_and_salary(
        _make_job(salary_min=100000, salary_max=120000, salary_currency="$"),
        _make_profile(),
    )
    user_content = fake.chat.completions.last_kwargs["messages"][1]["content"]
    assert "$100,000 - $120,000" in user_content
    # System prompt instructs to return null when salary is listed
    sys_content = fake.chat.completions.last_kwargs["messages"][0]["content"]
    assert "return null" in sys_content


def test_get_profile_recommendations_uses_quality_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    fake = _patch_client(monkeypatch,
        '{"recommendations": ["add aws","get cert","tighten title"]}')
    out = gs.get_profile_recommendations(_make_profile())
    assert fake.chat.completions.last_kwargs["model"] == "llama-3.3-70b-versatile"
    assert out == ["add aws", "get cert", "tighten title"]


def test_get_fit_score_swallows_exceptions(monkeypatch):
    _patch_client(monkeypatch, RuntimeError("network down"))
    out = gs.get_fit_score_and_salary(_make_job(), _make_profile())
    assert out == gs.FIT_SAFE_FALLBACK  # safe fallback, no raise


def test_get_profile_recommendations_swallows_exceptions(monkeypatch):
    _patch_client(monkeypatch, RuntimeError("boom"))
    assert gs.get_profile_recommendations(_make_profile()) == []
