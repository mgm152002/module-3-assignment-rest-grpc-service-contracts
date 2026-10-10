"""Order Service (gRPC version). A persistent server; listens on 50052.

PlaceOrder(item_id, quantity) calls InventoryService.CheckInventory with a
2.0s deadline and maps the outcome onto gRPC statuses, mirroring the REST
order service:
  quantity <= 0                    -> INVALID_ARGUMENT
  inventory NOT_FOUND               -> NOT_FOUND ("item not found")
  inventory FAILED_PRECONDITION     -> FAILED_PRECONDITION ("insufficient stock")
  inventory slower than 2.0s        -> DEADLINE_EXCEEDED
  otherwise                         -> PlaceOrderResponse(status="confirmed", ...)

The server stays up across all of these outcomes; a failed RPC never takes
the process down. Inventory target comes from GRPC_TARGET
(default 127.0.0.1:50051).
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
import order_pb2
import order_pb2_grpc

DEADLINE_SECS = 2.0
DEFAULT_INVENTORY_TARGET = "127.0.0.1:50051"


class OrderServicer(order_pb2_grpc.OrderServiceServicer):
    def __init__(self, inventory_target):
        channel = grpc.insecure_channel(
            inventory_target, options=[("grpc.enable_http_proxy", 0)])
        self.inventory = inventory_pb2_grpc.InventoryServiceStub(channel)

    def PlaceOrder(self, request, context):
        item_id = request.item_id
        quantity = request.quantity

        if not item_id or quantity <= 0:
            print(f"[{datetime.now()}] PlaceOrder(item={item_id!r}, qty={quantity}) "
                  f"-> INVALID_ARGUMENT", flush=True)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details("quantity must be a positive integer")
            return order_pb2.PlaceOrderResponse()

        try:
            inv = self.inventory.CheckInventory(
                inventory_pb2.CheckRequest(item_id=item_id, quantity=quantity),
                timeout=DEADLINE_SECS)
        except grpc.RpcError as exc:
            code = exc.code()
            if code == grpc.StatusCode.DEADLINE_EXCEEDED:
                print(f"[{datetime.now()}] PlaceOrder(item={item_id}, qty={quantity}) "
                      f"-> DEADLINE_EXCEEDED (inventory too slow)", flush=True)
                context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
                context.set_details("inventory service did not respond within "
                                    f"{DEADLINE_SECS}s")
            elif code == grpc.StatusCode.NOT_FOUND:
                print(f"[{datetime.now()}] PlaceOrder(item={item_id}, qty={quantity}) "
                      f"-> NOT_FOUND", flush=True)
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("item not found")
            elif code == grpc.StatusCode.FAILED_PRECONDITION:
                print(f"[{datetime.now()}] PlaceOrder(item={item_id}, qty={quantity}) "
                      f"-> FAILED_PRECONDITION", flush=True)
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("insufficient stock")
            else:
                print(f"[{datetime.now()}] PlaceOrder(item={item_id}, qty={quantity}) "
                      f"-> {code.name} (inventory error)", flush=True)
                context.set_code(grpc.StatusCode.UNAVAILABLE)
                context.set_details("inventory service unavailable")
            return order_pb2.PlaceOrderResponse()

        print(f"[{datetime.now()}] PlaceOrder(item={item_id}, qty={quantity}) "
              f"-> OK (confirmed)", flush=True)
        return order_pb2.PlaceOrderResponse(
            status="confirmed", item_id=item_id, quantity=quantity)


def serve():
    inventory_target = os.environ.get("GRPC_TARGET", DEFAULT_INVENTORY_TARGET)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_pb2_grpc.add_OrderServiceServicer_to_server(
        OrderServicer(inventory_target), server)
    # Primary TCP listener.
    bind = os.environ.get("ORDER_BIND", "127.0.0.1:50052")
    server.add_insecure_port(bind)
    # Unix-domain socket listener: used when the sandbox network filter blocks
    # TCP (it intercepts AF_INET6 connections). Same service, same semantics.
    here = os.path.dirname(os.path.abspath(__file__))
    sock_path = os.environ.get("ORDER_SOCKET", os.path.join(here, "order.sock"))
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        pass
    server.add_insecure_port("unix:" + sock_path)
    server.start()
    print(f"[{datetime.now()}] Order Service (gRPC) listening on {bind} "
          f"and unix:{sock_path}, inventory={inventory_target}, "
          f"deadline={DEADLINE_SECS}s", flush=True)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
