import os
from fastapi import Body, FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import File, UploadFile
from dotenv import load_dotenv
from .selenium_scraper import SeleniumJobScraper
from .playwright_scraper import PlaywrightJobScraper
from .parser import to_dataframe
from .normalizer import clean_basic
from .extract_resume_text import extract_resume_text
from .embeddings import embed_resume, embed_desc
from .job_match import cosine_similarity
import uuid
from pydantic import BaseModel


# --- FastAPI setup ---
load_dotenv()
app = FastAPI(
    title="Indeed Scraper API",
    description="Scrapes Indeed job listings using Playwright or Selenium.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

USER_RESUMES = {}
MAX_RESUME_SIZE = 10 * 1024 * 1024

# --- Routes ---
@app.get("/")
def home():
    return {"message": "Job Board Scraper API is running", "docs": "/docs"}

@app.get("/api/scrape")
async def scrape_jobs(
    search: str = Query(..., description="Job title or keyword"),
    location: str = Query(..., description="Job location"),
    date_range: int = Query(24, description="Filter by hours: 24, 48, 72"),
    engine: str = Query("play", description="Scraper engine: play or selenium")
):
    try:
        print(f"Executing with: {engine.upper()}")
        base_url = os.getenv("BASE_URL")
        if not base_url:
            raise ValueError("Base URL is not set")
        
        engine = engine.lower()
        if engine == "selenium":
            scraper = SeleniumJobScraper(base_url, search, location, date_range)
            raw_jobs = scraper.scrape()
            scraper.close()
        else:
            scraper = PlaywrightJobScraper()
            raw_jobs = await scraper.scrape(base_url, search, location, date_range)

        df = to_dataframe(raw_jobs)
        df = clean_basic(df)
        data = df.to_dict(orient="records")

        return JSONResponse(content={"engine": engine, "count": len(data), "jobs": data})
    except Exception as e:
        print("Error:", e)
        if not engine == "play":
            scraper.close() # type: ignore
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    
    if file.size and file.size > MAX_RESUME_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 10MB.")
    
    data = await file.read()
    resume_text = extract_resume_text(file, data)
    resume_embedding = embed_resume(resume_text)

    user_id = str(uuid.uuid4())
    USER_RESUMES[user_id] = {
        "text":resume_text,
        "embedding":resume_embedding
    }

    return {
        "message": "Resume uploaded successfully.",
        "user_id": user_id,
        "embedding": len(resume_embedding),
        "filename": file.filename,
        "preview": resume_text[:500] + "..." if len(resume_text) > 500 else resume_text
        }
    


class MatchRequest(BaseModel):
    user_id: str
    desc: str

@app.post("/api/match")
async def match_jobs(req: MatchRequest
    ) -> dict[str, float]:
    desc_embedding = embed_desc(req.desc)
    resume_embedding = USER_RESUMES[req.user_id]["embedding"]
    score = cosine_similarity(desc_embedding, resume_embedding)
    return {"match_score": float(score)}

@app.get("/api/get_resume")
async def resume_get(user_id: str) -> str:
    saved_resume = USER_RESUMES[user_id]["text"]
    return saved_resume