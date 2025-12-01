from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import papers, audits, imports, research
from .database import Base, engine

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Newspaper Audit API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost",
        "http://127.0.0.1"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Register routers
app.include_router(papers.router, prefix="/papers", tags=["papers"])
app.include_router(audits.router, prefix="/audits", tags=["audits"])
app.include_router(imports.router, prefix="/imports", tags=["imports"])
app.include_router(research.router, prefix="/research", tags=["research"])

@app.get("/")
def root():
    return {"message": "Newspaper Audit API is running"}
