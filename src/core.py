"""Deterministic, mock-only delivery planner core. No network, no live systems."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timedelta, timezone

CONTRACT_VERSION = "1.0"
MAX_INSIGHT_AGE_MIN = 30
MAX_STOCK_AGE_MIN = 60
MIN_CONFIDENCE = 0.75


def parse_ts(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must carry an explicit timezone")
    return dt.astimezone(timezone.utc)


def blocked(reason, detail=None, fallback=None):
    out = {"status": "BLOCKED", "reason": reason, "live_execution_allowed": False}
    if detail:
        out["detail"] = detail
    if fallback:
        out["manufacturing_fallback"] = {"advisory_only": True, **fallback}
    return out


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _provenance(source, observed_at, **extra):
    return {"source": source, "observed_at": observed_at, "fabricated": False, **extra}


def evaluate(request, world, now=None):
    """Return an ELIGIBLE plan or a BLOCKED decision. Pure function."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(request, dict):
        return blocked("INVALID_REQUEST")
    if request.get("contract_version") != CONTRACT_VERSION:
        return blocked("UNKNOWN_CONTRACT_VERSION", str(request.get("contract_version")))

    rid = request.get("request_id")
    insight = request.get("insight") or {}
    demand = request.get("demand") or {}
    if not rid or not isinstance(rid, str):
        return blocked("MISSING_REQUEST_ID")

    # T14: untrusted input that tries to steer the system
    blob = json.dumps(request).lower()
    for token in ("http://", "https://", "ignore previous", "execute live", "system prompt"):
        if token in blob:
            return blocked("PROHIBITED_INPUT", token)

    # T04: identity resolution
    asset_id = insight.get("asset_id")
    assets = world.get("assets", {})
    if asset_id not in assets:
        return blocked("UNKNOWN_ASSET", str(asset_id))
    asset = assets[asset_id]
    if asset.get("sku") is None or asset.get("unit") is None:
        return blocked("UNKNOWN_SKU_OR_UNIT", asset_id)

    # T02: insight freshness
    try:
        observed = parse_ts(insight.get("observed_at"))
    except Exception as exc:
        return blocked("INVALID_INSIGHT_TIMESTAMP", str(exc))
    age = now - observed
    if age < timedelta(0) or age > timedelta(minutes=MAX_INSIGHT_AGE_MIN):
        return blocked("STALE_OR_FUTURE_INSIGHT", f"age_minutes={age.total_seconds()/60:.1f}")

    # T03: confidence
    conf = insight.get("confidence")
    if not isinstance(conf, (int, float)) or conf < MIN_CONFIDENCE:
        return blocked("LOW_CONFIDENCE", f"confidence={conf}")

    # demand validity
    qty = demand.get("quantity")
    if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
        return blocked("INVALID_DEMAND_QUANTITY", str(qty))
    try:
        need_by = parse_ts(demand.get("need_by"))
    except Exception as exc:
        return blocked("INVALID_NEED_BY", str(exc))
    if need_by <= now:
        return blocked("DEMAND_DEADLINE_PASSED")
    sku = demand.get("sku") or asset["sku"]
    if sku != asset["sku"]:
        return blocked("SKU_MISMATCH", f"asset={asset['sku']} demand={sku}")
    destination = demand.get("destination")

    # T16: fail closed when a synthetic connector is down
    if (world.get("connector_status") or {}).get("erp") == "unavailable":
        return blocked("CONNECTOR_UNAVAILABLE", "erp snapshot cannot be read; plan state preserved")

    # T05/T06: stock
    candidates = []
    for lot in world.get("stock", []):
        if lot.get("sku") != sku or lot.get("depot_id") is None:
            continue
        try:
            stock_age = now - parse_ts(lot.get("observed_at"))
        except Exception:
            continue
        if stock_age < timedelta(0) or stock_age > timedelta(minutes=MAX_STOCK_AGE_MIN):
            continue  # stale snapshot is unusable
        if not isinstance(lot.get("quantity"), int) or lot["quantity"] <= 0 or lot["quantity"] < qty:
            continue
        if lot.get("maintenance_hold") or not lot.get("serviceable", False):
            continue
        candidates.append((lot, stock_age))

    if not candidates:
        mfg = (world.get("manufacturing") or {}).get(sku)
        if mfg and mfg.get("available"):
            return blocked("NO_ELIGIBLE_STOCK", "manufacturing fallback advisory only", fallback=mfg)
        return blocked("NO_ELIGIBLE_STOCK_OR_MAINTENANCE")

    # T07: certification vs ETA ; T08/T09: route
    reasons = []
    for lot, stock_age in candidates:
        for route in world.get("routes", []):
            if route.get("depot_id") != lot["depot_id"]:
                continue
            if route.get("destination") != destination:
                continue
            if not route.get("mock_trade_clearance") or not route.get("mock_route_eligible"):
                reasons.append(f"{lot['depot_id']}:TRADE_OR_ROUTE_NOT_CLEARED")
                continue
            eta = now + timedelta(days=route["transit_days"])
            if eta > need_by:
                reasons.append(f"{lot['depot_id']}:ETA_AFTER_NEED_BY")
                continue
            cert = (world.get("certifications") or {}).get(asset_id)
            if not cert or parse_ts(cert) <= eta:
                reasons.append(f"{lot['depot_id']}:CERTIFICATION_EXPIRES_BEFORE_ETA")
                continue
            plan = {
                "request_id": rid,
                "asset_id": asset_id,
                "sku": sku,
                "quantity": qty,
                "depot_id": lot["depot_id"],
                "destination": destination,
                "eta": eta.isoformat(),
                "need_by": need_by.isoformat(),
                "policy": {
                    "max_insight_age_minutes": MAX_INSIGHT_AGE_MIN,
                    "max_stock_age_minutes": MAX_STOCK_AGE_MIN,
                    "min_confidence": MIN_CONFIDENCE,
                    "illustrative": True,
                },
                "provenance": [
                    _provenance("synthetic_rt_insight", insight.get("observed_at"), asset_id=asset_id, confidence=conf),
                    _provenance("synthetic_erp_stock", lot.get("observed_at"), depot_id=lot["depot_id"], stock_age_minutes=round(stock_age.total_seconds()/60, 1)),
                    _provenance("synthetic_route_table", now.isoformat(), transit_days=route["transit_days"]),
                    _provenance("synthetic_cmms_certification", now.isoformat(), source_id=asset_id),
                ],
                "restrictions": ["mock_only", "no_physical_movement", "human_approval_required"],
                "uncertainty": {"confidence": conf, "basis": "deterministic_policy"},
                "human_authority": "approval_required_before_any_execution",
                "live_execution_allowed": False,
            }
            return {"status": "ELIGIBLE", "plan": plan, "plan_hash": plan_hash(plan), "considered": reasons}
    # T10 fallback considered only when no route worked
    mfg = (world.get("manufacturing") or {}).get(sku)
    if mfg and mfg.get("available"):
        return blocked("NO_FEASIBLE_ROUTE", "; ".join(reasons[:4]), fallback=mfg)
    return blocked("NO_FEASIBLE_ROUTE", "; ".join(reasons[:4]) or "no matching route")


_TOKEN_RE = None

def expand_world(world, now=None):
    """Replace __now__, __now-10m__, __now+3d__ style tokens with ISO timestamps."""
    import re
    now = now or datetime.now(timezone.utc)
    pattern = re.compile(r"^__now([+-]\d+)([mhd])__$")

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if x == "__now__":
            return now.isoformat()
        if isinstance(x, str):
            m = pattern.match(x)
            if m:
                n, unit = int(m.group(1)), m.group(2)
                delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
                return (now + delta).isoformat()
        return x

    return walk(world)
