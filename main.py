import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client, Client

# =========================
# Load Environment
# =========================
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("SUPABASE_URL_RAW_PREVIEW")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

JOBS_TABLE = "jobs"
JOB_RESULTS_TABLE = "job_results"

# =========================
# FastAPI App
# =========================
app = FastAPI(title="Infinite Audio Backend", version="0.1.0")


# =========================
# Models
# =========================
MixContext = Literal["FULL_MIX", "VOCAL_ONLY", "INSTRUMENTAL"]
MixMode = Literal["FAST", "DEEP"]


class MixJobRequest(BaseModel):
    user_id: uuid.UUID = Field(
        ...,
        description="User UUID",
        examples=["00000000-0000-0000-0000-000000000000"],
    )
    context: MixContext = Field(..., examples=["FULL_MIX"])
    mode: MixMode = Field(default="FAST", examples=["FAST"])

    input_bucket_key: str = Field(..., examples=["ia-uploads"])
    input_object_key: str = Field(..., examples=["dev/test.wav"])

    filename: str = Field(..., examples=["test.wav"])
    content_type: str = Field(..., examples=["audio/wav"])
    size_bytes: int = Field(..., ge=0, examples=[12345])
    duration_seconds: int = Field(..., ge=0, examples=[10])

    priority: int = Field(default=0, examples=[0])
    plan_snapshot: Dict[str, Any] = Field(default_factory=dict)


class MixJobCreateResponse(BaseModel):
    inserted: Dict[str, Any]


# =========================
# Helpers
# =========================
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_mix_audit(context: str) -> Dict[str, Any]:
    # Stubbed audit for now. Replace later with real analysis.
    return {
        "meta": {
            "tool": "mix_intelligence",
            "version": "0.1.0",
            "generated_at": now_utc_iso(),
            "context": context,
        },
        "summary": {
            "headline": "Mix audit generated (stub)",
            "what_to_fix_first": [
                "Check harshness in 2–5 kHz",
                "Check low-end overlap (kick vs 808)",
                "Check headroom before limiter",
            ],
        },
        "recommendations": {
            "immediate": [
                "Gain stage to -6 dB peak before processing",
                "High-pass non-bass elements",
                "Check dynamic EQ for harsh bands",
            ],
        },
    }


def require_uuid_string(u: str) -> None:
    try:
        uuid.UUID(u)
    except Exception:
        raise HTTPException(status_code=400, detail="user_id must be a valid UUID.")


# =========================
# Routes
# =========================
@app.get("/health")
def health() -> Dict[str, bool]:
    return {"ok": True}


@app.post("/mix-intelligence/create", response_model=MixJobCreateResponse)
def create_mix_job(req: MixJobRequest) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    user_id_str = str(req.user_id)

    job_row = {
        "id": job_id,
        "user_id": user_id_str,
        "type": "MIX_INTELLIGENCE",
        "status": "queued",
        "mode": req.mode,
        "created_at": now_utc_iso(),
        "started_at": None,
        "completed_at": None,
        "duration_seconds": req.duration_seconds,
        "input_bucket_key": req.input_bucket_key,
        "input_file_size_bytes": req.size_bytes,
        "input_audio_seconds": None,
        "input_sample_rate": None,
        "progress": 0,
        "stage": "created",
        "plan_snapshot": req.plan_snapshot or {},
        "priority": req.priority,
        "error_message": None,
        "input_object_key": req.input_object_key,
        "filename": req.filename,
        "content_type": req.content_type,
        "size_bytes": req.size_bytes,
        "context": req.context,
        "audit_results": None,
    }

    res = supabase.table(JOBS_TABLE).insert(job_row).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {res}")

    return {"inserted": res.data[0]}


@app.post("/mix-intelligence/process-next")
# =========================
# Result Fetch Endpoint
# =========================

@app.get("/mix-intelligence/result/{job_id}")
def get_mix_result(job_id: str):
    """
    Fetch a job + its processed result payload.
    Looks up:
      - public.jobs (by id)
      - public.job_results (by job_id)  [latest row]
      - public.job_audits (by job_id)   [latest row, optional]
    """
    # 1) job
    job_resp = (
        supabase.table("jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    if not job_resp.data:
        raise HTTPException(status_code=404, detail="Job not found.")

    job = job_resp.data[0]

    # 2) result (latest by created_at)
    result_resp = (
        supabase.table("job_results")
        .select("*")
        .eq("job_id", job_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    result = result_resp.data[0] if result_resp.data else None

    # 3) audit (latest by created_at) - optional
    audit = None
    try:
        audit_resp = (
            supabase.table("job_audits")
            .select("*")
            .eq("job_id", job_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        audit = audit_resp.data[0] if audit_resp.data else None
    except Exception:
        audit = None

    return {
        "job": job,
        "result": result,
        "audit": audit,
    }
def process_next_mix_job() -> Dict[str, Any]:
    # 1) Find next queued MIX_INTELLIGENCE job
    q = (
        supabase.table(JOBS_TABLE)
        .select("*")
        .eq("type", "MIX_INTELLIGENCE")
        .eq("status", "queued")
        .order("priority", desc=True)
        .order("created_at", desc=False)
        .limit(1)
        .execute()
    )

    if not q.data:
        return {"processed": False}

    job = q.data[0]
    job_id = job["id"]
    user_id = job["user_id"]
    context = job.get("context") or "FULL_MIX"

    require_uuid_string(user_id)

    # 2) Mark as processing (best-effort)
    supabase.table(JOBS_TABLE).update(
        {"status": "processing", "stage": "analyzing", "started_at": now_utc_iso(), "progress": 5}
    ).eq("id", job_id).execute()

    # 3) Generate audit (stub)
    audit = build_mix_audit(context)

    # 4) Write output row (Path B)
    out_row = {
        "job_id": job_id,
        "user_id": user_id,
        "tool": "mix_intelligence",
        "output": audit,
    }
    out_res = supabase.table(JOB_RESULTS_TABLE).upsert(out_row).execute()

    if not out_res.data:
        # fail the job cleanly
        supabase.table(JOBS_TABLE).update(
            {"status": "failed", "stage": "failed", "error_message": "Failed to write job_results."}
        ).eq("id", job_id).execute()
        raise HTTPException(status_code=500, detail="Failed to write job_results row.")

    # 5) Mark job complete + store audit in jobs.audit_results too (optional redundancy)
    supabase.table(JOBS_TABLE).update(
        {
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "completed_at": now_utc_iso(),
            "audit_results": audit,
            "error_message": None,
        }
    ).eq("id", job_id).execute()

    return {"processed": True, "job_id": job_id, "result_id": out_res.data[0]["id"]}