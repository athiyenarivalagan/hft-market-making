from app.monitoring.logging import get_logger
#  from dataclasses import dataclass 

log = get_logger()

# @dataclass
# class OMSOrder:
#     order_id: int
#     side: str
#     price: float
#     size: float
#     ts: float

class OMSOrder:
    def __init__(self, order_id, side, price, size, ts):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.size = size
        self.ts = ts

    def __repr__(self):
        return (f"OMSOrder(id={self.order_id}, side='{self.side}', "
                f"px={self.price}, sz={self.size}, ts={self.ts})")


class OMS:
    """Tracks your strategy’s orders only."""

    def __init__(self):
        self.orders = {}   # order_id -> OMSOrder

    def register(self, order_id, side, price, size, ts):
        if price <= 0 or size <= 0:
            message = f"Invalid order: {order_id}, price={price}, size={size}"
            log.error("OMS reject", message)
            return

        self.orders[order_id] = OMSOrder(order_id, side, price, size, ts)

    def modify(self, order_id, new_price, new_size, ts):
        o = self.orders.get(order_id)
        if not o:
            return
        o.price = new_price
        o.size = new_size
        o.ts = ts

    def cancel(self, order_id):
        self.orders.pop(order_id, None)

    def get(self, order_id):
        return self.orders.get(order_id)