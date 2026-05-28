---
name: Tailored CV Export Flow
description: End-to-end flow for generating, rendering, and downloading a tailored CV for a specific job, including LLM prompt and model tier
type: project
---

# Tailored CV Export Flow (per job)

**Entry point:** `POST /api/jobs/{job_id}/cv/generate` → `app/routes/cv.py:68`

## 1. Input assembly — `cv_tailoring.build_tailoring_inputs` (`app/services/cv_tailoring.py:56`)

- Loads `Job` via `JobRepository.get_job`.
- Loads user `Profile` (skills, titles, LinkedIn URL) and latest `UploadedCV` (LinkedIn PDF parsed to `LinkedInProfile` JSON). Rejects with 422 if both empty.
- Reads `job.intelligence_json` (required_skills, preferred_skills, tech_stack, seniority_level, red_flags). Falls back to regex keyword extraction from `job.description` if missing.
- Builds `candidate` dict (LinkedIn full experience preferred over compact Profile fields) and `job_ctx` (title/company/location/description truncated to 6000 chars + intelligence block).

## 2. LLM call — `tailor_cv` (`app/services/cv_tailoring.py:181`)

- **Model tier:** `recommend` (e.g. `llama-3.3-70b-versatile` on Groq, `gemini-2.5-flash` on Vertex, or configured Ollama model), via `_get_model("recommend")`.
- **Type:** single `_chat_complete` call with `json_mode=True`, `temperature=0.4`, `max_tokens=4096`.
- **System prompt** (`cv_tailoring.py:124`):
  > "You are an expert CV writer. Given a candidate's full profile and a target job posting, you rewrite the CV to maximize relevance to that job. You ALWAYS return valid JSON only."
- **User prompt** (`_PROMPT_TEMPLATE`, `cv_tailoring.py:129`): includes `TARGET JOB` (title, company, location, intelligence JSON, truncated description) + `CANDIDATE PROFILE` (JSON, capped at 12,000 chars) + explicit JSON shape:
  ```
  { tailored_summary, prioritized_skills[≤12],
    experience[{title,company,location,start_date,end_date,is_current,description}],
    education[], certifications[], projects[] }
  ```
  Rules: reverse-chronological experience, every role rewritten as exactly 3 action-verb bullets weighted toward `required_skills`+`tech_stack`, top-12 skills, ~5 items per education/cert/project section, no invented credentials, JSON only.

## 3. Parse & validate

- Response parsed via `_load_llm_json` (json-repair tolerant).
- Coerced into pydantic `CVData` (`app/schemas_core.py`) with `LinkedInExperience/Education/Certification/Project/Skill` items.
- Identity fields (name, email, phone, profile_url) pulled from LinkedIn PDF / Profile, NOT the LLM (anti-hallucination).

## 4. Render

- `render_tailored_pdf(cv)` → Jinja2 (`app/services/cv_export/templates/cv/tailored.html`, autoescape) → Playwright headless Chromium prints A4 PDF (`cv_renderer.py:23`).
- `render_tailored_docx(cv)` → python-docx (Calibri 10.5): Summary / Skills / Experience (bulleted) / Education / Certifications / Projects (`cv_renderer.py:58`).

## 5. Persist

- Bytes written atomically (tempfile + `os.replace`) to `data/uploads/tailored_cv/{job_id}.pdf` and `.docx`.
- `JobRepository.upsert_tailored_cv` stores `cv_json`, file paths, `model_used`.
- Response (`TailoredCVResponse`): `pdf_url=/api/jobs/{job_id}/cv/pdf`, `docx_url=/api/jobs/{job_id}/cv/docx`, `generated_at`, `model_used`, `CVData`.

## 6. Retrieve / download / delete

- `GET /api/jobs/{job_id}/cv` → stored `CVData` JSON (404 if not generated).
- `GET .../cv/pdf` and `.../cv/docx` → `FileResponse` with filename `{Company}_{Title}_CV.{ext}` (sanitized).
- `DELETE .../cv` → removes record.

**Why:** Reference for understanding/modifying tailored-CV generation without re-tracing the code path.
**How to apply:** Consult when user asks about CV generation behavior, prompt tuning, model selection, rendering, or download endpoints.
