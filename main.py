import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from supabase import create_client, Client

load_dotenv()

# -----------------------------
# Config
# -----------------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY env vars.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

JOBS_TABLE = "jobs"

JobStatus = Literal["queued", "processing", "completed", "failed"]
JobMode = Literal["FAST", "SLOW"]
MixContext = Literal["FULL_MIX", "LOOP", "VOCAL", "DRUMS"]

POLL_INTERVAL_SECONDS = 2
WORKER_ENABLED = os.getenv("MIX_WORKER_ENABLED", "false").lower() in ("1", "true", "yes")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_audit_results(context: str) -> dict:
    common = {
        "meta": {
            "tool": "mix_intelligence",
            "version": "0.1.0",
            "generated_at": now_utc_iso(),
            "context": context,
        },
        "summary": {
            "headline": "Mix audit generated",
            "what_to_fix_first": [
                "Check harshness in 2–5 kHz",
                "Check low-end overlap (kick vs bass)",
                "Check headroom and limiter behavior",
            ],
        },
        "checks": [
            {"id": "headroom", "status": "unknown", "note": "Reserve ~-6 dBFS pre-limiter for easier mastering."},
            {"id": "low_end", "status": "unknown", "note": "Confirm kick fundamental vs bass fundamental aren’t stacking."},
            {"id": "harshness", "status": "unknown", "note": "Sweep 2–5 kHz for piercing resonances."},
            {"id": "stereo", "status": "unknown", "note": "Keep sub mono; widen mids/highs carefully."},
        ],
        "recommendations": {
            "immediate": [
                "Pull master chain off and gain-stage to -6 dBFS peak.",
                "High-pass non-bass elements to clear sub mud.",
                "Use a dynamic EQ dip around the harshest band if needed.",
            ],
            "optional": [
                "Add gentle bus glue (1–2 dB GR) if the mix feels disjointed.",
                "Use transient shaping on drums if punch is lacking.",
            ],
        },
        "disclaimer": "Early audit template. Replace 'unknown' with measured metrics once DSP is wired in.",
    }

    if context == "LOOP":
        common["summary"]["what_to_fix_first"] = [
            "Prevent loop peaking or harsh resonances",
            "Ensure loop is drag-and-drop friendly (headroom)",
            "Avoid unnecessary master limiting",
        ]
        common["recommendations"]["immediate"].insert(0, "Remove any loudness maximizer. Deliver loops with headroom.")
    elif context == "VOCAL":
        common["summary"]["what_to_fix_first"] = [
            "Sibilance control (5–9 kHz)",
            "Mud cleanup (150–350 Hz)",
            "Consistent vocal level (compression automation)",
        ]
    elif context == "DRUMS":
        common["summary"]["what_to_fix_first"] = [
            "Kick and snare transient clarity",
            "Tame cymbal harshness",
            "Bus clipping vs limiting choice",
        ]

    return common


async def process_one_mix_job(job_id: Optional[str] = None) -> Optional[dict]:
    """
    If job_id is provided: process that job if queued.
    Else: process the oldest queued MIX_INTELLIGENCE job.
    """
    q = (
        supabase.table(JOBS_TABLE)
        .select("*")
        .eq("type", "MIX_INTELLIGENCE")
        .eq("status", "queued")
    )

    if job_id:
        q = q.eq("id", job_id)
    else:
        q = q.order("created_at", desc=False).limit(1)

    resp = q.execute()
    rows = getattr(resp, "data", None) or []
    if not rows:
        return None

    job = rows[0]
    jid = job["id"]

    # Claim it
    claim = (
        supabase.table(JOBS_TABLE)
        .update(
            {
                "status": "processing",
                "started_at": now_utc_iso(),
                "stage": "analyzing",
                "progress": 5,
                "error_message": None,
            }
        )
        .eq("id", jid)
        .eq("status", "queued")
        .execute()
    )

    claimed = getattr(claim, "data", None) or []
    if not claimed:
        return None

    context = (job.get("context") or "FULL_MIX").upper()
    audit = build_audit_results(context)

    await asyncio.sleep(0.25)

    done = (
        supabase.table(JOBS_TABLE)
        .update(
            {
                "status": "completed",
                "completed_at": now_utc_iso(),
                "stage": "done",
                "progress": 100,
                "audit_results": audit,
            }
        )
        .eq("id", jid)
        .execute()
    )

    return (getattr(done, "data", None) or [None])[0]


async def mix_worker_loop():
    while True:
        try:
            processed = await process_one_mix_job()
            if processed is None:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[mix_worker] error: {e}")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


# -----------------------------
# API
# -----------------------------
app = FastAPI(title="Infinite Audio Backend", version="0.1.0")


class MixJobRequest(BaseModel):
    user_id: str = Field(default="00000000-0000-0000-0000-000000000000")
    context: MixContext = Field(default="FULL_MIX")
    mode: JobMode = Field(default="SLOW")

    input_bucket_key: str = Field(..., description="Bucket name, e.g. ia-uploads")
    input_object_key: str = Field(..., description="Object key/path, e.g. dev/test.wav")

    filename: str = Field(..., description="Original filename, e.g. test.wav")
    content_type: str = Field(..., description="audio/wav or audio/mpeg")
    size_bytes: int = Field(..., ge=1, description="File size in bytes")
    duration_seconds: int = Field(..., ge=1, le=600, description="Audio duration in seconds (1-600)")

    priority: int = Field(default=0, ge=0, le=100)
    plan_snapshot: Dict[str, Any] = Field(default_factory=dict)


class MixJobCreateResponse(BaseModel):
    inserted: List[Dict[str, Any]]


@app.on_event("startup")
async def _startup():
    if WORKER_ENABLED:
        app.state.mix_worker_task = asyncio.create_task(mix_worker_loop())


@app.on_event("shutdown")
async def _shutdown():
    task = getattr(app.state, "mix_worker_task", None)
    if task:
        task.cancel()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/mix-intelligence/create", response_model=MixJobCreateResponse)
def create_mix_job(request: MixJobRequest):
    job_id = str(uuid.uuid4())

    job_data: Dict[str, Any] = {
        "id": job_id,
        "user_id": request.user_id,
        "type": "MIX_INTELLIGENCE",
        "status": "queued",
        "mode": request.mode,
        "context": request.context,
        "progress": 0,
        "priority": request.priority,
        "plan_snapshot": request.plan_snapshot,
        "input_bucket_key": request.input_bucket_key,
        "input_object_key": request.input_object_key,
        "filename": request.filename,
        "content_type": request.content_type,
        "size_bytes": request.size_bytes,
        "duration_seconds": request.duration_seconds,
        # back-compat
        "input_file_size_bytes": request.size_bytes,
        "stage": "created",
    }

    try:
        res = supabase.table(JOBS_TABLE).insert(job_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Insert returned no data.")
        return {"inserted": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@app.post("/mix-intelligence/process-next")
async def process_next_mix_job(job_id: Optional[str] = Query(default=None)):
    processed = await process_one_mix_job(job_id=job_id)
    if processed is None:
        return {"processed": False, "message": "No queued MIX_INTELLIGENCE jobs found (or job not queued)."}
    return {"processed": True, "job": processed}


@app.get("/mix-intelligence/result/{job_id}")
def get_mix_result(job_id: str):
    res = supabase.table(JOBS_TABLE).select("*").eq("id", job_id).limit(1).execute()
    rows = getattr(res, "data", None) or []
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job": rows[0]}