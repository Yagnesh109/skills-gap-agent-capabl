from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from profile_parsing.document_extractor import extract_text_from_file
from profile_parsing.gemini_client import parse_resume_with_gemini

app = FastAPI(title="Skill Gap to Job Matching Agent API")

# Allow the frontend dev server to call the API during local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/profile/parse")
async def parse_profile(file: UploadFile = File(...)):
    """Parse a PDF, DOC, DOCX, or TXT resume and return structured profile data."""
    if not file:
        raise HTTPException(status_code=400, detail="No resume uploaded.")

    filename = file.filename or ""
    if not filename.lower().endswith((".pdf", ".doc", ".docx", ".txt")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a PDF, DOC, DOCX, or TXT file.",
        )

    try:
        pdf_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file.") from exc

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="No resume uploaded.")

    try:
        resume_text = extract_text_from_file(pdf_bytes, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        parsed_profile = parse_resume_with_gemini(resume_text)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"success": True, "profile": parsed_profile}
