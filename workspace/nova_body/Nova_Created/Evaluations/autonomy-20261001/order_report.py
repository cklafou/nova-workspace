# Last updated: 2026-10-04 13:57:46
import json
import sys

def summarize(orders):
    paid = [order for order in orders if order["status"].strip().lower() == "paid"]
    return {"paid_orders": len(paid), "total_cents": sum(order["unit_cents"] * order["quantity"] for order in paid)}

if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as source:
        print(json.dumps(summarize(json.load(source))))
