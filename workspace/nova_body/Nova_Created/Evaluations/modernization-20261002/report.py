# Last updated: 2026-10-04 13:57:46
import json
def report(orders):
    paid = [o for o in orders if o.get("paid")]
    return {"paid_orders": len(paid), "total_cents": sum(o["quantity"]*o["unit_cents"] for o in paid)}
if __name__=="__main__":
    from pathlib import Path
    print(json.dumps(report(json.loads(Path(__file__).with_name("orders.json").read_text()))))
