from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.modules.iam_users.router import router as iam_router
from src.modules.students_padron.router import router as students_router
from src.modules.attendance_events.router import router as attendance_router

app = FastAPI(
    title="CatePass API — Monolito Modular",
    description="Backend Multiplataforma para Gestión de Asistencia QR, Padrón e Inscripciones de Catequesis (v7.0)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Infraestructura"])
def health_check():
    """Endpoint ligero para monitoreo 24/7 (Cron-job / Render / Koyeb)."""
    return {"status": "ok", "service": "catepass-backend-monolith", "version": "1.0.0"}


API_PREFIX = "/api/v1"
app.include_router(iam_router, prefix=API_PREFIX)
app.include_router(students_router, prefix=API_PREFIX)
app.include_router(attendance_router, prefix=API_PREFIX)