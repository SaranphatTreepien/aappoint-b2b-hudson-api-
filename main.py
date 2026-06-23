from fastapi import FastAPI, Query
from dotenv import load_dotenv
import requests
import os
from datetime import datetime, timedelta

tz_bangkok = timedelta(hours=7)
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


@app.get("/shops")
def search_shops(name: str = ""):
    token = get_token()
    res = requests.get(f"{BASE_URL}/shop", headers={"Authorization": f"Bearer {token}"})
    data = res.json()

    if isinstance(data, dict):
        shops = data.get("shops") or data.get("data") or []
    elif isinstance(data, list):
        shops = data
    else:
        shops = []

    if name:
        name_lower = name.lower()
        shops = [
            s
            for s in shops
            if isinstance(s, dict)
            and (
                name_lower in s.get("name_en", "").lower()
                or name_lower in s.get("name_th", "").lower()
            )
        ]
    return shops


@app.get("/shop/{shop_id}/events")
def get_events(shop_id: int, from_ts: int = Query(...), to_ts: int = Query(...)):
    token = get_token()
    res = requests.get(
        f"{BASE_URL}/shop/{shop_id}/event?from={from_ts}&to={to_ts}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return res.json()


@app.get("/shop/{shop_id}/daily-summary")
def daily_summary(shop_id: int, date: str = Query(...)):
    token = get_token()

    # แปลง date เป็น unix timestamp
    from datetime import datetime

    tz_offset = 7 * 3600
    day_start = int(datetime.strptime(date, "%Y-%m-%d").timestamp()) - tz_offset
    day_end = day_start + 86399

    # ดึง events
    res = requests.get(
        f"{BASE_URL}/shop/{shop_id}/event?from={day_start}&to={day_end}",
        headers={"Authorization": f"Bearer {token}"},
    )
    events = res.json()
    if not isinstance(events, list):
        return {"error": "no data"}

    # คำนวณ summary
    confirmed_revenue = 0
    deposit_collected = 0
    bookings = []
    confirmed = pending = cancelled = 0

    for e in events:
        status = e.get("status", "")
        po = e.get("event_purchase_order", {})
        po_status = po.get("status", "")

        if status in ("confirmed", "completed"):
            confirmed += 1
            if po_status == "paid":
                confirmed_revenue += float(po.get("total", 0))
                deposit_collected += float(po.get("deposit_amount", 0))
        elif status in ("pending", "created"):
            pending += 1
        elif status == "cancelled":
            cancelled += 1

        # ดึง customer
        cust_res = requests.get(
            f"{BASE_URL}/shop/{shop_id}/event/{e['id']}/user",
            headers={"Authorization": f"Bearer {token}"},
        )
        users = cust_res.json().get("users", [])
        customer = next(
            (u for u in users if u["user"]["resource_type"] == "human"), None
        )
        start_raw = e.get("start_at", "")
        try:
            start_utc = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            start_local = start_utc + tz_bangkok
            start_local_str = start_local.strftime("%Y-%m-%dT%H:%M:%S+07:00")
        except Exception:
            start_local_str = start_raw
        bookings.append(
            {
                "event_id": e.get("id"),
                "status": status,
                "start_at": e.get("start_at"),
                "party_size": e.get("party_size"),
                "zone": e.get("additional_data", {}).get("zone"),
                "service": e.get("service", {}).get("name_en"),
                "total": po.get("total"),
                "deposit": po.get("deposit_amount"),
                "payment_status": po_status,
                "customer_name": (
                    f"{customer['user']['first_name']} {customer['user']['last_name']}"
                    if customer
                    else None
                ),
                "phone": customer["user"].get("phone_no") if customer else None,
                "email": customer["user"].get("email") if customer else None,
            }
        )

    return {
        "date": date,
        "shop_id": shop_id,
        "confirmed": confirmed,
        "pending": pending,
        "cancelled": cancelled,
        "confirmed_revenue": confirmed_revenue,
        "deposit_collected": deposit_collected,
        "bookings": bookings,
    }


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
