# Convert the raw CSv into a structured Python dictionary
from typing import Optional, Dict
from datetime import datetime

def parse_csv_line(header: Dict[str, int], decode_line: str) -> Optional[dict]:
    """Parse the MBO CSV line into a normalized event dictionary"""
        
    # Remove newline → split into CSV fields → drop the feed timestamp (first column)
    parts = decode_line.rstrip("\n").split(",")[1: ]
    # print(repr(parts))

    if len(parts) < len(header):
        return None
    
    # Helper function to fetch a field by name
    def get(name: str, default=None):
        idx = header.get(name) # e.g., 4 for "action"
        if idx is None:
            return default
        val = parts[idx].strip()
        return val if val != "" else default

    # Convert to ISO-8601 ts with nanosecond precision and timezone
    ts_str = get("ts_event", "")
    dt = datetime.fromisoformat(ts_str)
    ts_ns = int(dt.timestamp() * 1_000_000_000)

    action_code = (get("action", "") or "").upper()
    side = (get("side", "N") or "N").upper()
    price = float(get("price", 0.0) or 0.0)
    size = float(get("size", 0.0) or 0.0)
    order_id = int(get("order_id", 0) or 0)
    symbol = get("symbol", "UNKNOWN")

    ACTION_MAP = {
        "A": "ADD",
        "M": "MOD",
        "C": "CXL",
        "T": "TRD",
        "F": "FILL",
        "R": "CLR",
        "N": "CLR"
    }
    action = ACTION_MAP.get(action_code)
    if not action:
        return None
    
    return {
        "ts": ts_ns,
        "action": action,
        "order_id": order_id,
        "side": side,
        "price": price,
        "size": size,
        "instrument": symbol
    }