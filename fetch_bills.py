from collections import Counter
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
REQUEST_DELAY_SECONDS = 1
DETAIL_FIELDS = ("sponsors", "agent")
VALID_HOUSES = {"Commons", "Lords"}
FIRST_OR_SECOND_READING_STAGE_IDS = {
    1,  # 1st reading (Lords)
    2,  # 2nd reading (Lords)
    6,  # 1st reading (Commons)
    7,  # 2nd reading (Commons)
    25,  # Second reading committee (Commons)
    30,  # Second reading committee (Lords)
}
ROYAL_ASSENT_STAGE_ID = 11
PING_PONG_STAGE_IDS = {
    12,  # Consideration of Lords amendments (Commons)
    13,  # Consideration of Commons amendments and / or reasons (Lords)
    42,  # Consideration of Lords message (Commons)
}


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


def fetch_paged_items(base_url: str) -> list[dict]:
    all_items: list[dict] = []
    skip = 0

    while True:
        time.sleep(REQUEST_DELAY_SECONDS)
        url = f"{base_url}?Take={TAKE}"
        if skip:
            url += f"&Skip={skip}"

        page = fetch_json(url)
        items = page.get("items") or []
        all_items.extend(items)

        skip += len(items)
        total_results = page.get("totalResults") or 0
        if not items or skip >= total_results:
            break

    return all_items


def fetch_bill_stages(bill_id: int) -> list[dict]:
    return fetch_paged_items(f"{BILLS_URL}/{bill_id}/Stages")


def count_decisions(decisions) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for decision in decisions:
        key = decision if isinstance(decision, str) and decision else "Unknown"
        counts[key] += 1
    return dict(counts)


def fetch_amendment_decisions(bill_id: int, stage_id: int) -> dict[str, int]:
    items = fetch_paged_items(f"{BILLS_URL}/{bill_id}/Stages/{stage_id}/Amendments")
    return count_decisions(item.get("decision") for item in items)


def fetch_ping_pong_decisions(bill_id: int, stage_id: int) -> dict[str, int]:
    items = fetch_paged_items(f"{BILLS_URL}/{bill_id}/Stages/{stage_id}/PingPongItems")
    return count_decisions(
        (item.get("motion") or item.get("amendment") or {}).get("decision")
        for item in items
    )


def is_first_house_early_reading(bill: dict) -> bool:
    stage = bill.get("currentStage") or {}
    orig_house = bill.get("originatingHouse")
    return (
        orig_house in VALID_HOUSES
        and stage.get("house") == orig_house
        and stage.get("stageId") in FIRST_OR_SECOND_READING_STAGE_IDS
    )


def enrich_bills(bills: list[dict]):
    bills_to_enrich = [b for b in bills if not is_first_house_early_reading(b)]
    skipped = len(bills) - len(bills_to_enrich)
    if skipped:
        print(
            f"Skipping {skipped} 1st House 1R/2R bills; enriching {len(bills_to_enrich)} bills...",
            flush=True,
        )

    total = len(bills_to_enrich)
    for idx, bill in enumerate(bills_to_enrich, start=1):
        time.sleep(REQUEST_DELAY_SECONDS)

        bill_id = bill.get("billId")
        stage = bill.get("currentStage") or {}
        stage_id = stage.get("id")
        stage_type_id = stage.get("stageId")
        is_ra = stage_type_id == ROYAL_ASSENT_STAGE_ID
        is_ping_pong = stage_type_id in PING_PONG_STAGE_IDS
        has_stage_sittings = any(
            s.get("date") for s in (stage.get("stageSittings") or [])
        )
        needs_stages = stage_id is not None and not is_ra and not has_stage_sittings
        stages_note = " + stage history" if needs_stages else ""

        if stage_id is None:
            print(
                f"[{idx}/{total}] Fetching details for bill {bill_id} (no current stage)...",
                flush=True,
            )
        elif is_ra:
            print(
                f"[{idx}/{total}] Fetching details for bill {bill_id} (Royal Assent; skipping amendments)...",
                flush=True,
            )
        elif is_ping_pong:
            print(
                f"[{idx}/{total}] Fetching details and ping-pong items{stages_note} (stage {stage_id}) for bill {bill_id}...",
                flush=True,
            )
        else:
            print(
                f"[{idx}/{total}] Fetching details and amendments{stages_note} (stage {stage_id}) for bill {bill_id}...",
                flush=True,
            )

        try:
            detail = fetch_json(f"{BILLS_URL}/{bill_id}")
            for field in DETAIL_FIELDS:
                bill[field] = detail.get(field)
        except (HTTPError, URLError) as err:
            print(
                f"  Warning: failed to fetch bill {bill_id}: {err}",
                file=sys.stderr,
                flush=True,
            )
            bill["sponsors"] = []
            bill["agent"] = None

        if stage_id is None or is_ra:
            bill["amendmentDecisions"] = {}
        else:
            fetch_fn = (
                fetch_ping_pong_decisions
                if is_ping_pong
                else fetch_amendment_decisions
            )
            try:
                bill["amendmentDecisions"] = fetch_fn(bill_id, stage_id)
            except (HTTPError, URLError) as err:
                kind = "ping-pong items" if is_ping_pong else "amendments"
                print(
                    f"  Warning: failed to fetch {kind} for bill {bill_id} stage {stage_id}: {err}",
                    file=sys.stderr,
                    flush=True,
                )
                bill["amendmentDecisions"] = {}

        if needs_stages:
            try:
                bill["stages"] = fetch_bill_stages(bill_id)
            except (HTTPError, URLError) as err:
                print(
                    f"  Warning: failed to fetch stages for bill {bill_id}: {err}",
                    file=sys.stderr,
                    flush=True,
                )
                bill["stages"] = []


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
    print(
        f"Wrote {len(data.get('items', []))} bills (sessionId={session_id}) to {out_path}"
    )


if __name__ == "__main__":
    main()
