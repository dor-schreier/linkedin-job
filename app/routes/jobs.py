from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import JobStatus
from app.repository import JobRepository

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

PAGE_SIZE = 50


@router.get("/jobs", response_class=HTMLResponse)
def jobs_list(
    request: Request,
    status: Optional[str] = None,
    company: Optional[str] = None,
    salary_min: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(get_session),
):
    repo = JobRepository(db)

    # Validate and coerce status
    status_enum: Optional[JobStatus] = None
    if status:
        try:
            status_enum = JobStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {status}")

    # Validate and coerce salary_min
    salary_min_f: Optional[float] = None
    if salary_min:
        try:
            salary_min_f = float(salary_min)
        except ValueError:
            raise HTTPException(status_code=422, detail="salary_min must be numeric")

    offset = (page - 1) * PAGE_SIZE
    jobs = repo.list_jobs(
        status=status_enum,
        company=company or None,
        salary_min_filter=salary_min_f,
        limit=PAGE_SIZE,
        offset=offset,
    )
    total = repo.count_jobs_filtered(
        status=status_enum,
        company=company or None,
        salary_min_filter=salary_min_f,
    )
    has_more = (offset + PAGE_SIZE) < total

    # Determine if this is an HTMX partial request
    is_htmx = request.headers.get("HX-Request") == "true"
    template = "partials/job_list.html" if is_htmx else "jobs.html"

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "jobs": jobs,
            "total": total,
            "page": page,
            "has_more": has_more,
            "filters": {
                "status": status or "",
                "company": company or "",
                "salary_min": salary_min or "",
            },
            "job_statuses": [s.value for s in JobStatus],
        },
    )


@router.post("/jobs/{job_id}/status")
async def update_job_status(
    job_id: int,
    status: str = Form(...),
    db: Session = Depends(get_session),
):
    if job_id <= 0:
        raise HTTPException(status_code=422, detail="Invalid job_id")
    try:
        status_enum = JobStatus(status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid status value: {status}")

    repo = JobRepository(db)
    job = repo.update_job_status(job_id, status_enum)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Return 204 No Content — HTMX hx-swap="none" expects no body
    return Response(status_code=204)
