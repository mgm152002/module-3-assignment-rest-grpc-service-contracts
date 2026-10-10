"""Place an order through the persistent gRPC Order Service.

Usage: python3 grpc/place_order.py <item_id> <quantity>
Calls OrderService.PlaceOrder with a 2.0s deadline and prints the outcome.
Handles DEADLINE_EXCEEDED, NOT_FOUND, FAILED_PRECONDITION and
INVALID_ARGUMENT cleanly. Exit code is 0 for every handled case.

Order-service target comes from ORDER_TARGET (default 127.0.0.1:50052);
e.g. ORDER_TARGET=unix:/abs/path/grpc/order.sock in sandboxes whose
network filter blocks TCP.
Run from the repo root.
"""
import os
import sys

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import order_pb2
import order_pb2_grpc

DEADLINE_SECS = 2.0
DEFAULT_TARGET = "127.0.0.1:50052"


def main():
    if len(sys.argv) != 3:
        print("usage: python3 grpc/place_order.py <item_id> <quantity>")
        sys.exit(2)
    item_id = sys.argv[1]
    try:
        quantity = int(sys.argv[2])
    except ValueError:
        print("error: quantity must be an integer")
        sys.exit(2)

    # Disable HTTP proxying: the sandbox sets http_proxy/https_proxy env vars,
    # which would otherwise route this localhost call through the egress proxy.
    target = os.environ.get("ORDER_TARGET", DEFAULT_TARGET)
    print(f"Target: {target}")
    channel = grpc.insecure_channel(
        target, options=[("grpc.enable_http_proxy", 0)])
    stub = order_pb2_grpc.OrderServiceStub(channel)
    request = order_pb2.PlaceOrderRequest(item_id=item_id, quantity=quantity)
    print(f"Request: item_id={item_id!r} quantity={quantity} (deadline={DEADLINE_SECS}s)")

    try:
        response = stub.PlaceOrder(request, timeout=DEADLINE_SECS)
    except grpc.RpcError as exc:
        code = exc.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            print(f"DEADLINE_EXCEEDED: order service did not respond within "
                  f"{DEADLINE_SECS}s (details: {exc.details()})")
        elif code == grpc.StatusCode.NOT_FOUND:
            print(f"NOT_FOUND: {exc.details()}")
        elif code == grpc.StatusCode.FAILED_PRECONDITION:
            print(f"FAILED_PRECONDITION: {exc.details()}")
        elif code == grpc.StatusCode.INVALID_ARGUMENT:
            print(f"INVALID_ARGUMENT: {exc.details()}")
        else:
            print(f"{code.name}: {exc.details()}")
        return 0

    print(f"OK: status={response.status!r} item_id={response.item_id!r} "
          f"quantity={response.quantity}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
