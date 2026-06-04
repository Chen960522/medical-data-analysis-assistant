from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.analysis import router as analysis_router
from .api.v1.auth import router as auth_router
from .api.v1.chat import router as chat_router
from .api.v1.data import router as data_router
from .api.v1.literature import router as literature_router
from .api.v1.reports import router as reports_router
from .api.v1.translation import router as translation_router

app = FastAPI(
    title="医学数据分析助手 API",
    description="Medical Data Analysis Assistant Backend API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(data_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(literature_router, prefix="/api/v1")
app.include_router(translation_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
