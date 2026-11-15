from datetime import datetime
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SESSIONS_URL = "https://whatson-api.parliament.uk/calendar/sessions/list.json"
BILLS_URL = "https://bills-api.parliament.uk/api/v1/Bills"
TAKE = 1000
REQUEST_DELAY_SECONDS = 0.2
DETAIL_FIELDS = ("sponsors", "agent")


def fetch_json(url: str, retries: int = 2):
    req = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "uk-parliament-dashboard/1.0",
        },
    )
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (HTTPError, URLError) as err:
            status = getattr(err, "code", None)
            if attempt < retries and status in (None, 429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


def find_current_session_id(today: str):
    for session in fetch_json(SESSIONS_URL):
        start = (session.get("StartDate") or "")[:10]
        end = (session.get("EndDate") or "")[:10]
        if start and end and start <= today <= end:
            return session.get("SessionId")
    return None


def enrich_bills(bills: list[dict]):
    total = len(bills)
    for idx, bill in enumerate(bills, start=1):
        if idx > 1:
            time.sleep(REQUEST_DELAY_SECONDS)

        bill_id = bill.get("billId")
        print(f"[{idx}/{total}] Fetching details for bill {bill_id}...", flush=True)
        try:
            detail = fetch_json(f"{BILLS_URL}/{bill_id}")
            for field in DETAIL_FIELDS:
                bill[field] = detail.get(field)
        except (HTTPError, URLError) as err:
            print(f"  Warning: failed to fetch bill {bill_id}: {err}", file=sys.stderr, flush=True)
            bill["sponsors"] = []
            bill["agent"] = None


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("bills.json")
    today = datetime.now(ZoneInfo("Europe/London")).date().isoformat()

    session_id = find_current_session_id(today)
    if session_id is None:
        data = {"items": [], "totalResults": 0, "itemsPerPage": TAKE}
    else:
        data = fetch_json(f"{BILLS_URL}?Session={session_id}&Take={TAKE}")
        enrich_bills(data.get("items") or [])

    data["fetchedDate"] = today

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote {len(data.get('items', []))} bills (sessionId={session_id}) to {out_path}")


if __name__ == "__main__":
    main()
