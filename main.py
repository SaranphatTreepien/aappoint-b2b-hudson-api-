from fastapi import FastAPI, Query
from dotenv import load_dotenv
import requests
import os

load_dotenv()

app = FastAPI()

BASE_URL = os.getenv("AAPPOINT_BASE_URL")
BASIC = os.getenv("AAPPOINT_BASIC")
USERNAME = os.getenv("AAPPOINT_USERNAME")
PASSWORD = os.getenv("AAPPOINT_PASSWORD")


def get_token():
    res = requests.post(
        f"{BASE_URL}/auth/token",
        headers={
            "Authorization": f"Basic {BASIC}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "password", "username": USERNAME, "password": PASSWORD},
    )
    return res.json()["access_token"]


@app.get("/shop/{shop_id}/events")
def get_events(shop_id: int, from_ts: int = Query(...), to_ts: int = Query(...)):
    token = get_token()
    res = requests.get(
        f"{BASE_URL}/shop/{shop_id}/event?from={from_ts}&to={to_ts}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()


@app.get("/shop/{shop_id}/events/{event_id}/customer")
def get_customer(shop_id: int, event_id: int):
    token = get_token()
    res = requests.get(
        f"{BASE_URL}/shop/{shop_id}/event/{event_id}/user",
        headers={"Authorization": f"Bearer {token}"},
    )
    users = res.json().get("users", [])
    customer = next((u for u in users if u["user"]["resource_type"] == "human"), None)
    return customer
