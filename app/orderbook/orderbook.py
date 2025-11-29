from collections import defaultdict
from .order import Order
from .price_level import PriceLevel


class OrderBook:
    def __init__(self) -> None:
        """
        PURE Exchange Order Book (L2/L3).
        - Tracks exchange orders only
        - Does NOT track your strategy's own orders
        """

        self.bids = defaultdict(PriceLevel)
        self.asks = defaultdict(PriceLevel)
        self.lookup = {} # order_id : Orders (exchange orders ONLY) 

    def _side_map(self, side: str):
        """
        Map DataBento side:
           'B' -> bids
           'A' -> asks
           'N' -> no update (neutral event)
        """

        if not isinstance(side, str):
            # Alternatively, be strict and reject non-string sides:
            raise ValueError(f"Side must be a string: {side}")
        
        s = side.upper()
        if s == "B":
            return self.bids
        if s == "A":
            return self.asks
        if s == "N":
            return None # meaning: nothing to update
        
        # Unknown value 
        raise ValueError(f"Unknown side {side}")
    
    # def _side_map(self, side: str):
    #     s = side.upper()
    #     if s == "B": return self.bids
    #     if s == "A": return self.asks
    #     return None


    # -------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------
    def on_add(self, order_id: int, side: str, price: float, size: float,
               ts: float) -> None:
        """Add a new EXCHANGE order."""

        # remove duplicate ID (rare but safe)
        if order_id in self.lookup: 
            self.on_cancel(order_id)
        
        # Order(...) creates an instance of the Order class, not a dict.
        # Order(
        #   id=8058566314544,
        #   side='A',
        #   px=64.83, 
        #   sz=1.0, 
        #   ts=1758742200000859904
        # ) 
        o = Order(order_id, side, price, size, ts) 
        self.lookup[order_id] = o 
        
        side_map = self._side_map(side)
        if side_map is None:
            return
        side_map[price].add(o)

    def on_modify(self, order_id: int, new_price: float, new_size: float,
                 ts: float) -> None:
        """
        Modifying EXCHANGE order.

        - If price changes: remove it from the current price level and
          insert it into the new price level (maintains price-time priority).
        - Always update size and timestamp.
        """

        o = self.lookup.get(order_id)
        if not o:
            return # Order doesn't exist in the book

        side_map = self._side_map(o.side)

        # If price changes, move it to the new price level
        if new_price != o.price:
            side_map[o.price].remove(order_id)
            o.price = new_price # update price to the existing order
            side_map[o.price].add(o)
        
        # Update size + timestamp
        o.size = new_size
        o.ts = ts

    def on_cancel(self, order_id: int) -> None:
        """Cancel EXCHANGE order - used for cancel or full trade fills"""

        o = self.lookup.pop(order_id, None) 
        if not o:
            return
        side_map = self._side_map(o.side)
        side_map[o.price].remove(order_id)

    def on_trade(self, order_id: int, executed: float, ts: float) -> None:
        """Remove an order's remaining qauntity when part/all of it trades.
            Remove it if size hits zero"""
        
        o = self.lookup.get(order_id)
        if not o:
            return
        
        o.size -= executed
        o.ts = ts

        if o.size <= 0:
            self.on_cancel(order_id)

    def on_fill(self, order_id: int, executed: float, ts: float) -> None:
        self.on_trade(order_id, executed, ts)

    def on_clear(self) -> None:
        """Clear entire exchange order book."""
        self.lookup.clear() 
        self.bids.clear()
        self.asks.clear()

    
    # -------------------------------------------------------
    # Best prices (L1)
    # -------------------------------------------------------

    # Strategy engine will call these methods on every event.
    # The best bid/ask is computed every time a new event arrives\
    # (ADD, MODIFY, CANCEL, TRADE -> any event that changes the book).
    # Can be made faster using 'heapq' or 'sortedcontainers'
    def best_bid(self):
        """Return the highest bid price, or None if no bids"""
        if not self.bids:
            return None
        return max(self.bids.keys())
        # return self.bids.keys() if self.bids else None
    
    def best_ask(self):
        """Return the highest ask price, or None if no asks"""
        if not self.asks:
            return None
        return min(self.asks.keys())
    
    def best_bid_size(self):
        """Return total size at the best bid price"""
        best = self.best_bid()
        if best is None:
            return 0.0
        level = self.bids[best]
        # sum the total bid sizes of the best bid
        return sum(order.size for order in level.orders.values())

    def best_ask_size(self):
        """Return total size at the best ask price"""
        best = self.best_ask()
        if best is None:
            return 0.0 
        level = self.asks[best]
        return sum(order.size for order in level.orders.values())