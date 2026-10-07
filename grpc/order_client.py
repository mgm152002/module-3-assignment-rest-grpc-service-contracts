"""Order client (gRPC version).

Usage: python3 grpc/order_client.py <item_id> <quantity>
Calls InventoryService.CheckInventory with a 2.0s deadline and prints the
outcome. Handles DEADLINE_EXCEEDED, NOT_FOUND and FAILED_PRECONDITION cleanly.
Exit code is 0 for every handled case.
Run from the repo root.
"""
import os
import sys

import grpc

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import inventory_pb2
import inventory_pb2_grpc

DEADLINE_SECS = 2.0
# gRPC target. Default is TCP 127.0.0.1:50051. Override with GRPC_TARGET, e.g.
# GRPC_TARGET=unix:/abs/path/grpc/inventory.sock (needed in sandboxes whose
# network filter blocks TCP; the server also listens on that unix socket).
DEFAULT_TARGET = "127.0.0.1:50051"


def main():
    if len(sys.argv) != 3:
        print("usage: python3 grpc/order_client.py <item_id> <quantity>")
        sys.exit(2)
    item_id = sys.argv[1]
    try:
        quantity = int(sys.argv[2])
    except ValueError:
        print("error: quantity must be an integer")
        sys.exit(2)

    # Disable HTTP proxying: the sandbox sets http_proxy/https_proxy env vars,
    # which would otherwise route this localhost call through the egress proxy.
    target = os.environ.get("GRPC_TARGET", DEFAULT_TARGET)
    print(f"Target: {target}")
    channel = grpc.insecure_channel(
        target, options=[("grpc.enable_http_proxy", 0)])
    stub = inventory_pb2_grpc.InventoryServiceStub(channel)
    request = inventory_pb2.CheckRequest(item_id=item_id, quantity=quantity)
    print(f"Request: item_id={item_id!r} quantity={quantity} (deadline={DEADLINE_SECS}s)")

    try:
        response = stub.CheckInventory(request, timeout=DEADLINE_SECS)
    except grpc.RpcError as exc:
        code = exc.code()
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            print(f"DEADLINE_EXCEEDED: inventory service did not respond within "
                  f"{DEADLINE_SECS}s (details: {exc.details()})")
        elif code == grpc.StatusCode.NOT_FOUND:
            print(f"NOT_FOUND: {exc.details()}")
        elif code == grpc.StatusCode.FAILED_PRECONDITION:
            print(f"FAILED_PRECONDITION: {exc.details()}")
        else:
            print(f"{code.name}: {exc.details()}")
        return 0

    print(f"OK: available={response.available} stock={response.stock} "
          f"message={response.message!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
