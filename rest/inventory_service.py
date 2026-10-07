"""Inventory Service (REST version).

Flask app on port 5001.
GET /inventory/<item_id>?quantity=<int>
  200 {"item_id", "requested_quantity", "available", "stock"}
  404 {"error": ...}        for unknown items
  400 {"error": ...}        for missing/invalid quantity
Set env var INVENTORY_DELAY (seconds) to simulate a slow service.
"""
import os
import time
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)

INVENTORY = {"widget": 100, "gadget": 25, "sprocket": 0}


@app.route("/inventory/<item_id>", methods=["GET"])
def check_inventory(item_id):
    delay = float(os.environ.get("INVENTORY_DELAY", "0") or 0)
    if delay > 0:
        time.sleep(delay)

    qty_raw = request.args.get("quantity")
    try:
        quantity = int(qty_raw)
    except (TypeError, ValueError):
        print(f"[{datetime.now()}] GET /inventory/{item_id}?quantity={qty_raw} -> 400 (bad quantity)",
              flush=True)
        return jsonify({"error": "quantity must be an integer"}), 400
    if quantity < 0:
        print(f"[{datetime.now()}] GET /inventory/{item_id}?quantity={quantity} -> 400 (negative)",
              flush=True)
        return jsonify({"error": "quantity must be non-negative"}), 400

    if item_id not in INVENTORY:
        print(f"[{datetime.now()}] GET /inventory/{item_id}?quantity={quantity} -> 404 (unknown item)",
              flush=True)
        return jsonify({"error": f"unknown item: {item_id}"}), 404

    stock = INVENTORY[item_id]
    available = stock >= quantity
    print(f"[{datetime.now()}] GET /inventory/{item_id}?quantity={quantity} "
          f"-> 200 (available={available}, stock={stock})", flush=True)
    return jsonify({
        "item_id": item_id,
        "requested_quantity": quantity,
        "available": available,
        "stock": stock,
    }), 200


if __name__ == "__main__":
    print(f"[{datetime.now()}] Inventory Service (REST) starting on port 5001, "
          f"INVENTORY_DELAY={os.environ.get('INVENTORY_DELAY', '0')}", flush=True)
    app.run(host="127.0.0.1", port=5001, use_reloader=False)
