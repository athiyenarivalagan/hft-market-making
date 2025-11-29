from typing import OrderedDict
from .order import Order # <- import the Order class

class PriceLevel:
    """
    Manages all resting orders at a single price level.
    Uses an OrderedDict to preserve time-priority (FIFO excution).
    """

    def __init__(self):
        self.orders = OrderedDict()

    def add(self, o: Order) -> None:
        """Insert a new order into this price level (FIFO maintained by OrderedDict)."""
        self.orders[o.order_id] = o

    def remove(self, order_id: int) -> None:
        """Remove an order from this price level (ignore if not present)"""
        self.orders.pop(order_id, None)

    def best_qty(self) -> float:
        """Remove the total quantity resting at this price level."""
        return sum(o.size for o in self.orders.values())

    def __repr__(self):
        return f"PriceLevel({list(self.orders.values())})"