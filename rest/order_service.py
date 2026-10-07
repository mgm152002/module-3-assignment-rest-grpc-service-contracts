"""Order Service (REST version).

Flask app on port 5000.
POST /order {"item_id": ..., "quantity": ...}
Calls the Inventory Service at http://localhost:5001 with a 2s timeout and
maps the result:
  inventory 200 + available=true   -> 201 {"status": "confirmed", ...}
  inventory 404                     -> 404 {"error": "item not found"}
  inventory 200 + available=false   -> 409 {"status": "rejected", "reason": "insufficient stock"}
  requests.Timeout                  -> 504 {"error": "inventory service timeout"}
  connection/other errors           -> 502 {"error": "inventory service unavailable"}
The handler is wrapped in try/except so the server NEVER crashes on a failure.
"""
from datetime import datetime

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

INVENTORY_URL = "http://localhost:5001/inventory"
TIMEOUT_SECS = 2


@app.route("/order", methods=["POST"])
def create_order():
    try:
        data = request.get_json(force=True, silent=True) or {}
        item_id = data.get("item_id")
        quantity = data.get("quantity")
        if not item_id or not isinstance(quantity, int):
            print(f"[{datetime.now()}] POST /order -> 400 (bad request body: {data})", flush=True)
            return jsonify({"error": "request must be JSON with item_id (str) and quantity (int)"}), 400

        try:
            resp = requests.get(f"{INVENTORY_URL}/{item_id}",
                                params={"quantity": quantity},
                                timeout=TIMEOUT_SECS)
        except requests.Timeout:
            print(f"[{datetime.now()}] POST /order item={item_id} qty={quantity} -> 504 "
                  f"(inventory service timeout after {TIMEOUT_SECS}s)", flush=True)
            return jsonify({"error": "inventory service timeout"}), 504
        except requests.ConnectionError as exc:
            print(f"[{datetime.now()}] POST /order item={item_id} qty={quantity} -> 502 "
                  f"(cannot reach inventory service: {exc})", flush=True)
            return jsonify({"error": "inventory service unavailable"}), 502

        if resp.status_code == 404:
            print(f"[{datetime.now()}] POST /order item={item_id} qty={quantity} -> 404 (item not found)",
                  flush=True)
            return jsonify({"error": "item not found"}), 404

        payload = resp.json()
        if payload.get("available"):
            print(f"[{datetime.now()}] POST /order item={item_id} qty={quantity} -> 201 (confirmed)",
                  flush=True)
            return jsonify({"status": "confirmed", "item_id": item_id, "quantity": quantity}), 201

        print(f"[{datetime.now()}] POST /order item={item_id} qty={quantity} -> 409 (insufficient stock)",
              flush=True)
        return jsonify({"status": "rejected", "reason": "insufficient stock"}), 409
    except Exception as exc:  # never let the server crash
        print(f"[{datetime.now()}] POST /order -> 500 (unexpected error: {exc})", flush=True)
        return jsonify({"error": "internal error"}), 500


if __name__ == "__main__":
    print(f"[{datetime.now()}] Order Service (REST) starting on port 5000, "
          f"inventory timeout={TIMEOUT_SECS}s", flush=True)
    app.run(host="127.0.0.1", port=5000, use_reloader=False)
