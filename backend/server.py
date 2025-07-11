from fastapi import FastAPI, APIRouter, BackgroundTasks
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime

# Import medical consultation module
from medical_consultation import (
    run_medical_consultation, 
    set_progress_callback, 
    cleanup_session
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

class ConsultationRequest(BaseModel):
    question: str
    model: str = "gpt-4o-mini"

class ConsultationResponse(BaseModel):
    session_id: str
    question: str
    experts: List[dict] = []
    round_opinions: dict = {}
    final_answers: dict = {}
    decision: str
    duration: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None

# Store active consultations
active_consultations = {}

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Multi-Agent Medical Consultation System"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

@api_router.post("/consultation/start")
async def start_consultation(request: ConsultationRequest, background_tasks: BackgroundTasks):
    """Start a new medical consultation"""
    try:
        session_id = str(uuid.uuid4())
        
        # Store consultation request
        consultation_data = {
            "session_id": session_id,
            "question": request.question,
            "model": request.model,
            "status": "processing",
            "progress": 0.0,
            "current_step": "开始会诊...",
            "start_time": datetime.now(),
            "result": None
        }
        
        active_consultations[session_id] = consultation_data
        await db.consultations.insert_one(consultation_data)
        
        # Start consultation in background
        background_tasks.add_task(process_consultation, session_id, request.question, request.model)
        
        return {"session_id": session_id, "status": "started"}
        
    except Exception as e:
        logger.error(f"Error starting consultation: {str(e)}")
        return {"error": str(e)}, 500

@api_router.get("/consultation/{session_id}/progress")
async def get_consultation_progress(session_id: str):
    """Get consultation progress"""
    try:
        if session_id in active_consultations:
            consultation = active_consultations[session_id]
            return {
                "session_id": session_id,
                "status": consultation["status"],
                "progress": consultation["progress"],
                "current_step": consultation["current_step"],
                "result": consultation.get("result")
            }
        else:
            # Try to get from database
            consultation = await db.consultations.find_one({"session_id": session_id})
            if consultation:
                return {
                    "session_id": session_id,
                    "status": consultation["status"],
                    "progress": consultation["progress"],
                    "current_step": consultation["current_step"],
                    "result": consultation.get("result")
                }
            else:
                return {"error": "Session not found"}, 404
                
    except Exception as e:
        logger.error(f"Error getting consultation progress: {str(e)}")
        return {"error": str(e)}, 500

@api_router.get("/consultation/{session_id}/stream")
async def stream_consultation_progress(session_id: str):
    """Stream consultation progress using Server-Sent Events"""
    async def generate():
        try:
            while True:
                if session_id in active_consultations:
                    consultation = active_consultations[session_id]
                    
                    # Send progress update
                    data = {
                        "session_id": session_id,
                        "status": consultation["status"],
                        "progress": consultation["progress"],
                        "current_step": consultation["current_step"],
                        "result": consultation.get("result")
                    }
                    
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    # If completed, send final result and break
                    if consultation["status"] == "completed":
                        break
                        
                    await asyncio.sleep(1)  # Update every second
                else:
                    # Session not found
                    yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
                    break
                    
        except Exception as e:
            logger.error(f"Error streaming consultation progress: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/plain")

async def process_consultation(session_id: str, question: str, model: str):
    """Process medical consultation in background"""
    try:
        # Set up progress callback
        def progress_callback(progress: float, step: str):
            if session_id in active_consultations:
                active_consultations[session_id]["progress"] = progress
                active_consultations[session_id]["current_step"] = step
                
                # Update database
                asyncio.create_task(
                    db.consultations.update_one(
                        {"session_id": session_id},
                        {"$set": {"progress": progress, "current_step": step}}
                    )
                )
        
        set_progress_callback(session_id, progress_callback)
        
        # Run consultation
        result = await run_medical_consultation(question, model, session_id)
        
        # Update consultation status
        if session_id in active_consultations:
            active_consultations[session_id]["status"] = "completed"
            active_consultations[session_id]["result"] = result
            active_consultations[session_id]["progress"] = 100.0
            active_consultations[session_id]["current_step"] = "会诊完成！"
        
        # Update database
        await db.consultations.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "completed",
                "result": result,
                "progress": 100.0,
                "current_step": "会诊完成！",
                "end_time": datetime.now()
            }}
        )
        
        # Clean up after a delay
        await asyncio.sleep(300)  # Keep in memory for 5 minutes
        cleanup_session(session_id)
        if session_id in active_consultations:
            del active_consultations[session_id]
            
    except Exception as e:
        logger.error(f"Error processing consultation {session_id}: {str(e)}")
        
        # Update with error status
        if session_id in active_consultations:
            active_consultations[session_id]["status"] = "error"
            active_consultations[session_id]["result"] = {"error": str(e)}
        
        await db.consultations.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "error",
                "result": {"error": str(e)},
                "end_time": datetime.now()
            }}
        )

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()