import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models  # noqa: F401 — register tables
from app.models import Company, Job, JobStatus, ManualOverride, RejectAuditLog, RejectRule
from app.repository import JobRepository
from app.services import reject_service


@pytest.fixture
def session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_conn, _):
        c = dbapi_conn.cursor()
        c.execute("PRAGMA journal_mode=WAL")
        c.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    yield s
    s.close()


def _mk_job(session, **overrides) -> Job:
    defaults = dict(
        title="Senior Software Engineer",
        company="Acme",
        location="Tel Aviv",
        source="linkedin",
        job_hash=overrides.get("job_hash", "h" + str(id(overrides))),
    )
    defaults.update(overrides)
    j = Job(**defaults)
    session.add(j)
    session.commit()
    session.refresh(j)
    return j


# --- Title keyword matcher ---

def test_title_keyword_whole_word_match(session):
    j1 = _mk_job(session, title="Software Engineer", job_hash="h1")
    j2 = _mk_job(session, title="Engineering Manager", job_hash="h2")
    rule = RejectRule(rule_type="title_keyword", value="engineer", is_enabled=True)
    session.add(rule); session.commit(); session.refresh(rule)
    assert reject_service.rule_matches_job(session, rule, j1) is True
    assert reject_service.rule_matches_job(session, rule, j2) is False


def test_title_keyword_case_insensitive(session):
    j = _mk_job(session, title="DATA ENTRY clerk", job_hash="h3")
    rule = RejectRule(rule_type="title_keyword", value="data entry", is_enabled=True)
    session.add(rule); session.commit(); session.refresh(rule)
    assert reject_service.rule_matches_job(session, rule, j) is True


def test_title_keyword_regex_metachar_escaped(session):
    j = _mk_job(session, title="C++ Developer", job_hash="h4")
    rule = RejectRule(rule_type="title_keyword", value="c++", is_enabled=True)
    session.add(rule); session.commit(); session.refresh(rule)
    assert reject_service.rule_matches_job(session, rule, j) is True


# --- Location matcher ---

def test_location_match_case_insensitive(session):
    j = _mk_job(session, location="  Tel Aviv  ", job_hash="hL")
    rule = RejectRule(rule_type="location", value="tel aviv", is_enabled=True)
    session.add(rule); session.commit(); session.refresh(rule)
    assert reject_service.rule_matches_job(session, rule, j) is True


def test_location_no_partial_match(session):
    j = _mk_job(session, location="Tel Aviv", job_hash="hL2")
    rule = RejectRule(rule_type="location", value="Aviv", is_enabled=True)
    session.add(rule); session.commit(); session.refresh(rule)
    assert reject_service.rule_matches_job(session, rule, j) is False


# --- Property matcher ---

def test_property_company_match(session):
    j = _mk_job(session, company="Acme Corp", job_hash="hP")
    rule = RejectRule(rule_type="property", property_name="company", value="acme corp", is_enabled=True)
    session.add(rule); session.commit(); session.refresh(rule)
    assert reject_service.rule_matches_job(session, rule, j) is True


# --- OR evaluation, attribution by lowest id ---

def test_or_evaluation_first_rule_wins_attribution(session):
    j = _mk_job(session, title="Engineer", company="Acme", job_hash="hOR")
    r1 = RejectRule(rule_type="title_keyword", value="engineer", is_enabled=True)
    r2 = RejectRule(rule_type="property", property_name="company", value="Acme", is_enabled=True)
    session.add_all([r1, r2]); session.commit(); session.refresh(r1); session.refresh(r2)
    match = reject_service.find_first_matching_rule(session, j)
    assert match.id == r1.id


# --- Retroactive scan ---

def test_create_rule_retroactive(session):
    j_match = _mk_job(session, title="Data Entry Clerk", job_hash="ha")
    j_skip = _mk_job(session, title="Backend Engineer", job_hash="hb")
    repo = JobRepository(session)
    rule = repo.add_reject_rule(rule_type="title_keyword", value="data entry")
    affected = reject_service.apply_rule_retroactive(session, rule)
    session.refresh(j_match); session.refresh(j_skip)
    assert affected == 1
    assert j_match.is_rejected is True
    assert j_match.rejected_by_rule_id == rule.id
    assert j_skip.is_rejected is False
    audit = session.query(RejectAuditLog).filter_by(job_id=j_match.id).all()
    assert len(audit) == 1
    assert audit[0].action == "rejected"


# --- Disable / delete reverse evaluation ---

def test_disable_rule_repoints_when_other_rule_matches(session):
    repo = JobRepository(session)
    j = _mk_job(session, title="Data Entry Clerk", company="Acme", job_hash="hd")
    r1 = repo.add_reject_rule(rule_type="title_keyword", value="data entry")
    r2 = repo.add_reject_rule(rule_type="property", property_name="company", value="Acme")
    reject_service.apply_rule_retroactive(session, r1)
    reject_service.apply_rule_retroactive(session, r2)
    session.refresh(j)
    assert j.rejected_by_rule_id == r1.id  # earlier rule wins
    # Disable r1 — j should repoint to r2 (no audit unrejected)
    r1.is_enabled = False
    session.commit()
    reject_service.reverse_rule_evaluation(session, r1)
    session.refresh(j)
    assert j.is_rejected is True
    assert j.rejected_by_rule_id == r2.id


def test_disable_rule_unrejects_when_no_other_match(session):
    repo = JobRepository(session)
    j = _mk_job(session, title="Data Entry Clerk", job_hash="hu")
    r1 = repo.add_reject_rule(rule_type="title_keyword", value="data entry")
    reject_service.apply_rule_retroactive(session, r1)
    session.refresh(j)
    assert j.is_rejected is True
    r1.is_enabled = False
    session.commit()
    reject_service.reverse_rule_evaluation(session, r1)
    session.refresh(j)
    assert j.is_rejected is False
    assert j.rejected_by_rule_id is None
    audit = session.query(RejectAuditLog).filter_by(job_id=j.id, action="unrejected").all()
    assert len(audit) == 1


# --- Manual override ---

def test_manual_unreject_persists_against_re_evaluation(session):
    repo = JobRepository(session)
    j = _mk_job(session, title="Data Entry Clerk", job_hash="hm")
    r1 = repo.add_reject_rule(rule_type="title_keyword", value="data entry")
    reject_service.apply_rule_retroactive(session, r1)
    session.refresh(j)
    assert j.is_rejected is True
    reject_service.manual_unreject(session, j.id)
    session.refresh(j)
    assert j.is_rejected is False
    assert reject_service.is_manually_overridden(session, j.id) is True
    # New rule should NOT auto-re-reject this job
    r2 = repo.add_reject_rule(rule_type="title_keyword", value="data")
    affected = reject_service.apply_rule_retroactive(session, r2)
    session.refresh(j)
    assert j.is_rejected is False
    assert affected == 0  # the only candidate was overridden


# --- Insert-time evaluation ---

def test_evaluate_on_insert_flags_matching_job(session):
    repo = JobRepository(session)
    repo.add_reject_rule(rule_type="title_keyword", value="intern")
    j = _mk_job(session, title="Software Intern", job_hash="hi")
    reject_service.evaluate_job_on_insert(session, j)
    session.refresh(j)
    assert j.is_rejected is True


# --- list_jobs filters rejected by default ---

def test_list_jobs_excludes_rejected_by_default(session):
    repo = JobRepository(session)
    repo.add_reject_rule(rule_type="title_keyword", value="intern")
    j_ok = _mk_job(session, title="Senior Engineer", job_hash="ho1")
    j_bad = _mk_job(session, title="Software Intern", job_hash="ho2")
    reject_service.evaluate_job_on_insert(session, j_bad)
    visible = repo.list_jobs(limit=100)
    visible_ids = {x.id for x in visible}
    assert j_ok.id in visible_ids
    assert j_bad.id not in visible_ids
    # include_rejected returns it back
    all_jobs = repo.list_jobs(limit=100, include_rejected=True)
    assert j_bad.id in {x.id for x in all_jobs}


# --- property-values endpoint logic ---

def test_property_values_excludes_null(session):
    _mk_job(session, company="Acme", job_hash="hpv1")
    _mk_job(session, company="", job_hash="hpv2")
    repo = JobRepository(session)
    vals = repo.get_distinct_property_values("company")
    assert "Acme" in vals
    assert "" not in vals


def test_unique_rule_dedupe(session):
    repo = JobRepository(session)
    r1 = repo.add_reject_rule(rule_type="title_keyword", value="intern")
    r2 = repo.add_reject_rule(rule_type="title_keyword", value="intern")
    assert r1.id == r2.id
