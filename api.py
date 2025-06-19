from fastapi import FastAPI
from main import check_driver_license

app = FastAPI()

@app.get("/check_driver/")
async def check_driver(date: str):
    return check_driver_license(date)
