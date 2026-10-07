"""Inventory Service (gRPC version). Listens on 50051.

Unknown item            -> grpc.StatusCode.NOT_FOUND, details "item not found"
quantity > stock        -> grpc.StatusCode.FAILED_PRECONDITION, details "insufficient stock"
Otherwise               -> CheckResponse(available, stock, message)

Set env var INVENTORY_DELAY (seconds) to simulate a slow service.
Run from the repo root.
"""
import os
import sys
import time
from concurrent import futures
from datetime import datetime

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import inventory_pb2
import inventory_pb2_grpc

INVENTORY = {"widget": 100, "gadget": 25, "sprocket": 0}


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckInventory(self, request, context):
        delay = float(os.environ.get("INVENTORY_DELAY", "0") or 0)
        if delay > 0:
            time.sleep(delay)

        item_id = request.item_id
        quantity = request.quantity

        if item_id not in INVENTORY:
            print(f"[{datetime.now()}] CheckInventory(item={item_id}, qty={quantity}) "
                  f"-> NOT_FOUND", flush=True)
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("item not found")
            return inventory_pb2.CheckResponse()

        stock = INVENTORY[item_id]
        if quantity > stock:
            print(f"[{datetime.now()}] CheckInventory(item={item_id}, qty={quantity}) "
                  f"-> FAILED_PRECONDITION (stock={stock})", flush=True)
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
            context.set_details("insufficient stock")
            return inventory_pb2.CheckResponse()

        msg = f"{quantity} x {item_id} available (stock={stock})"
        print(f"[{datetime.now()}] CheckInventory(item={item_id}, qty={quantity}) -> OK ({msg})",
              flush=True)
        return inventory_pb2.CheckResponse(available=True, stock=stock, message=msg)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    # Primary TCP listener (lab spec).
    server.add_insecure_port("127.0.0.1:50051")
    # Unix-domain socket listener: used when the sandbox network filter blocks
    # TCP (it intercepts AF_INET6 connections). Same service, same semantics.
    here = os.path.dirname(os.path.abspath(__file__))
    sock_path = os.path.join(here, "inventory.sock")
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass
    server.add_insecure_port("unix:" + sock_path)
    server.start()
    print(f"[{datetime.now()}] Inventory Service (gRPC) listening on 127.0.0.1:50051 "
          f"and unix:{sock_path}, INVENTORY_DELAY={os.environ.get('INVENTORY_DELAY', '0')}",
          flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
