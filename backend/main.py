from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok", "model_loaded": False}

@app.post("/api/analyze")
async def analyze_csv(file: UploadFile = File(...)):
    return {
        "analysis_id": "demo_123",
        "results": [
            {
                "passenger_id": "DEMO001",
                "period_start": "2017-10-01",
                "period_end": "2017-10-30",
                "display_name": None,
                "score": 0.82,
                "flagged": True,
                "observations": [{"feature": "flights_30d", "value": 24}],
                "model_explanation": None,
                "quality_warnings": [],
                "history_available": False
            }
        ]
    }

@app.get("/api/analyses/{analysis_id}/passengers/{passenger_id}")
async def get_passenger_card(analysis_id: str, passenger_id: str, period_start: str, period_end: str):
    return {
        "analysis_id": analysis_id,
        "passenger_id": passenger_id,
        "period_start": period_start,
        "period_end": period_end,
        "message": "Это заглушка для карточки пассажира"
    }

@app.get("/api/analyses/{analysis_id}/export")
async def export_analysis(analysis_id: str):
    return {"message": "Здесь будет выгрузка файла csv", "analysis_id": analysis_id}