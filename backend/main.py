from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import csv
import uuid

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
    if (not file.filename.endswith(".csv")):
        raise HTTPException(status_code=400, detail="File must end with .csv")

    contents = await file.read(file.size)
    format_contents = contents.decode("utf-8")

    buffer = io.StringIO(format_contents)
    reader = csv.DictReader(buffer)

    passengers = []
    required_items = ["passenger_id", "period_start", "period_end"]
    for col in required_items:
        if col not in reader.fieldnames:
            raise HTTPException(status_code=400, detail=f'Column {col} is required')

    for row in reader:
        pass_id = row.get("passenger_id")
        if pass_id is None:
            raise HTTPException(status_code=400, detail="Passenger id is required")

        passengers.append({
                "passenger_id": pass_id,
                "period_start": "2017-10-01",
                "period_end": "2017-10-30",
                "display_name": None,
                "score": 0.82,
                "flagged": True,
                "observations": [{"feature": "flights_30d", "value": 24}],
                "model_explanation": None,
                "quality_warnings": [],
                "history_available": False
            })

    if (len(passengers) == 0):
        raise HTTPException(status_code=400, detail="File is empty")

    return {
        "analysis_id": str(uuid.uuid4()),
        "results": passengers
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