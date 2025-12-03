"""
Emogo Backend API Service

This FastAPI application handles data collection from the Emogo React Native frontend.
It provides endpoints for:
- Receiving emotion records with location and video data
- Exporting records as HTML table
- Exporting records as CSV file

Features:
- Async support using FastAPI and Motor (async MongoDB driver)
- MongoDB Atlas integration for data persistence
- HTML templating with Jinja2
- Environment variable configuration
"""

import os
import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

import base64
import io
from zoneinfo import ZoneInfo 
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from bson import ObjectId
from bson.errors import InvalidId

# Load environment variables from .env file in development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================================
# Configuration
# ============================================================================

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Kyle:00000000@emogo.cyy5the.mongodb.net/emogo?retryWrites=true&w=majority")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "Emogo")
MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "records")

# ============================================================================
# Pydantic Models
# ============================================================================

class Record(BaseModel):
    """Model for individual emotion record"""
    id: int
    sentiment: str
    sentimentValue: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: datetime
    videoPath: str
    videoBase64: Optional[str] = None


class ExportPayload(BaseModel):
    """Model for the payload received from the React Native frontend"""
    exportDate: datetime
    recordCount: int
    records: List[Record]

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

def format_dt_taipei(dt: datetime) -> str:
    """
    將 datetime 轉成台北時間，格式為 'YYYY-MM-DD HH:MM:SS'
    如果原本沒有 tzinfo，假設是 UTC。
    """
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_taipei = dt.astimezone(TAIPEI_TZ)
    return dt_taipei.strftime("%Y-%m-%d %H:%M:%S")

def now_taipei_str() -> str:
    """回傳目前台北時間字串，用在頁面 footer。"""
    return datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="Emogo Backend",
    description="API service for Emogo emotion tracking application",
    version="1.0.0"
)

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")
templates.env.globals["now"] = now_taipei_str
# ============================================================================
# MongoDB Connection Management
# ============================================================================

# Global variables to hold MongoDB connection
mongodb_client: Optional[AsyncIOMotorClient] = None
mongodb_db: Optional[AsyncIOMotorDatabase] = None
mongodb_collection: Optional[AsyncIOMotorCollection] = None


async def connect_to_mongodb():
    """Establish connection to MongoDB Atlas on startup"""
    global mongodb_client, mongodb_db, mongodb_collection
    try:
        mongodb_client = AsyncIOMotorClient(MONGODB_URI)
        # Verify connection
        await mongodb_client.admin.command('ping')
        print("✓ Connected to MongoDB Atlas")
        
        mongodb_db = mongodb_client[MONGODB_DB_NAME]
        mongodb_collection = mongodb_db[MONGODB_COLLECTION_NAME]
        print(f"✓ Using database: {MONGODB_DB_NAME}, collection: {MONGODB_COLLECTION_NAME}")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        raise


async def close_mongodb():
    """Close MongoDB connection on shutdown"""
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        print("✓ Closed MongoDB connection")


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    await connect_to_mongodb()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    await close_mongodb()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """
    Health check endpoint
    Returns basic information about available endpoints
    """
    return {
        "message": "Emogo backend is running",
        "endpoints": {
            "POST /records": "Submit emotion records from the app",
            "GET /export": "View all records as HTML table",
            "GET /export/csv": "Download all records as CSV file"
        }
    }


@app.post("/records")
async def submit_records(payload: ExportPayload):
    """
    POST endpoint to receive emotion records from the React Native frontend.
    
    Accepts a JSON payload containing:
    - exportDate: timestamp when the export was initiated
    - recordCount: number of records being exported
    - records: list of Record objects
    
    Each record is stored in MongoDB with the exportDate field added.
    
    Returns:
    - inserted: number of records successfully inserted
    """
    try:
        # Prepare documents for insertion
        documents = []
        for record in payload.records:
            doc = record.model_dump()
            doc["exportDate"] = payload.exportDate
            documents.append(doc)
        
        # Insert all records into MongoDB
        if documents:
            result = await mongodb_collection.insert_many(documents)
            inserted_count = len(result.inserted_ids)
            print(f"✓ Inserted {inserted_count} records into MongoDB")
            return {
                "inserted": inserted_count,
                "message": f"Successfully inserted {inserted_count} record(s)"
            }
        else:
            return {"inserted": 0, "message": "No records to insert"}
            
    except Exception as e:
        print(f"✗ Error inserting records: {e}")
        return {"error": str(e)}, 500


@app.get("/export", response_class=HTMLResponse)
async def export_html(request: Request):
    """
    GET endpoint to display all records as an HTML table.
    
    Retrieves all records from MongoDB, sorts them by timestamp (oldest first),
    and renders them using the Jinja2 template.
    
    Returns:
    - HTML page with a table of all records and a CSV download link
    """
    try:
        # Fetch all records from MongoDB, sorted by timestamp
        records = await mongodb_collection.find().sort("timestamp", 1).to_list(None)
        
        # Convert datetime objects to strings for template rendering
        for record in records:
            if isinstance(record.get("timestamp"), datetime):
                record["timestamp"] = format_dt_taipei(record["timestamp"])
            if isinstance(record.get("exportDate"), datetime):
                record["exportDate"] = format_dt_taipei(record["exportDate"])

            # 把 MongoDB 的 _id 轉成字串，給前端當下載用的 ID
            if "_id" in record:
                record["mongoId"] = str(record["_id"])
        
        # Render template with records
        return templates.TemplateResponse(
            "export.html",
            {"request": request, "records": records}
        )
        
    except Exception as e:
        print(f"✗ Error fetching records: {e}")
        return f"<h1>Error</h1><p>{str(e)}</p>"


@app.get("/export/csv")
async def export_csv():
    """
    下載所有紀錄為 CSV 檔（欄位與 /export 頁面的表格對齊）

    欄位：
    ID, 心情, 心情值, 緯度, 經度, 記錄時間（台北時間）, 上傳時間（台北時間）, 影片路徑
    """
    try:
        # 依 timestamp 由舊到新抓全部紀錄
        records = await mongodb_collection.find().sort("timestamp", 1).to_list(None)

        # 建立 CSV 內容
        output = io.StringIO()
        writer = csv.writer(output)

        # 中文表頭，順序跟 export.html 的表格一致
        writer.writerow([
            "ID",
            "心情",
            "心情值",
            "緯度",
            "經度",
            "記錄時間（台北時間）",
            "上傳時間（台北時間）",
            "影片路徑",
        ])

        # 寫入每一列資料
        for record in records:
            ts = record.get("timestamp")
            exd = record.get("exportDate")

            # 跟網頁一樣，用 format_dt_taipei 轉成台北時間字串
            ts_str = format_dt_taipei(ts) if isinstance(ts, datetime) else ""
            exd_str = format_dt_taipei(exd) if isinstance(exd, datetime) else ""

            writer.writerow([
                record.get("id", ""),
                record.get("sentiment", ""),
                record.get("sentimentValue", ""),
                record.get("latitude", ""),
                record.get("longitude", ""),
                ts_str,
                exd_str,
                record.get("videoPath", ""),
            ])

        # 回傳 StreamingResponse
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=emogo_records.csv"
            },
        )

    except Exception as e:
        print(f"✗ Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail="Error exporting CSV")
    

@app.get("/records/{record_id}/video")
async def download_video(record_id: str):
    """
    依照 MongoDB 的 _id 下載影片(mp4)
    - record_id 現在是一個 ObjectId 的字串（例如 "674f3c0c8d7b2f..."）
    """
    try:
        # 把字串轉成真正的 ObjectId，如果格式錯會丟 400
        try:
            oid = ObjectId(record_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail="Invalid record id")

        # 用 _id 查 MongoDB 的紀錄（這是唯一、不會重複的）
        record = await mongodb_collection.find_one({"_id": oid})
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        video_b64 = record.get("videoBase64")
        if not video_b64:
            raise HTTPException(status_code=404, detail="No video stored for this record")

        try:
            video_bytes = base64.b64decode(video_b64)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error decoding video: {e}")

        # 用 StreamingResponse 回傳 mp4
        # 檔名可以照舊用 record 裡的 id（App 的流水號），只是名字而已
        return StreamingResponse(
            io.BytesIO(video_bytes),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="emogo_record_{record.get("id", "unknown")}.mp4"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Error serving video for record {record_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
