from app.orderbook.orderbook import OrderBook
# from app.oms.oms import OMS
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass
class StrategyConfig:
    tick_size: float = 0.01

    # base quoting behaviour
    base_spread: float = 0.04 # base spread (in price units)
    min_spread: float = 0.02  # min allowed spread
    max_spread: float = 0.1   # widens when risky
    quote_size: float = 1.0   # per-side quote size

    # Inventory / risk
    inventory_target: float = 0.0        # target position (usually 0) 
    inventory_sensitivity: float = 0.005 # how much spread widens per unit of inventory
    max_position: float = 10.0           # hard inventory limit

    # Throttling / staleness
    min_quote_interval_ns: int = 5_000_000  # 5 millisecond
    price_move_threshold_ticks: float = 1.0 # only re-quote if move >= 1 tick 

class MarketMaker:
    """
    Event-driven market-making strategy:
    - quotes one bid and one ask around microprice / mid
    - adapts spread based on inventory
    - throttles quote updates to avoid spam
    """

    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg

        # Current working quotes
        self.current_bid_id: Optional[int] = None
        self.current_ask_id: Optional[int] = None

        self.current_bid_px: Optional[float] = None
        self.current_ask_px: Optional[float] = None

        # Inventory / PnL
        self.position: float = 0.0
        self.cash: float = 0.0

        # For throttling
        self.last_quote_ns: int = 0

        self.order_seq = 0

    # --------------------------
    # Public API
    # --------------------------

    def on_book_event(self, order_book, oms, ts_ns: int) -> None:
        """
        Call this on every market data event after applying it to the order book.

        order_book: your OrderBook instance
        oms:        your OMS instance
        ts_ns:      event timestamp in nanoseconds 
        """

        top = self._get_top_of_book(order_book)
        if top is None:
            return

        # best_bid = highest buyer
        # best_ask = lowest seller
        # sizes = liquidity on each side
        best_bid_px, best_bid_sz, best_ask_px, best_ask_sz = top

        if best_bid_px is None or best_ask_px is None:
            return

        # Throttling (Rate Limiting)
        # This prevents:
        #   - spamming the exchange.
        #   - blowing up message rate limits. 
        #   - excessive latency
        if ts_ns - self.last_quote_ns < self.cfg.min_quote_interval_ns:
            return

        # microprice predicts the next mid-move direction
        micro = self._compute_microprice(
            best_bid_px, best_bid_sz, best_ask_px, best_ask_sz
        )

        # Compute working spread adjusted for inventory 
        spread = self._compute_working_spread()
        bid_px = micro - spread / 2.0
        ask_px = micro + spread / 2.0

        # Apply inventory hard limits: only quote in the direction that reduces risk
        quote_bid = True
        quote_ask = True

        if self.position >= self.cfg.max_position:
            quote_bid = False
        if self.position <= -self.cfg.max_position:
            quote_ask = False

        if quote_bid:
            self._update_quote(
                side="B",
                new_price=bid_px,
                oms=oms,
                ts_ns=ts_ns,
            )
        else:
            self._cancel_bid_if_any(oms)

        if quote_ask:
            self._update_quote(
                side="A",
                new_price=ask_px,
                oms=oms,
                ts_ns=ts_ns
            )
        else:
            self._cancel_ask_if_any(oms)

    def on_own_trade(self, side: str, price: float, size: float) -> None:
        """
        Call this whenever one of your orders gets filled.
        side: 'B' or 'A'
        """
        if side == "B":
            # Bought size
            self.position += size
            self.cash -= price * size
        elif side == "A":
            # Sold size 
            self.position -= size
            self.cash += price * size


    # --------------------------
    # Internal helpers
    # --------------------------
    def _get_top_of_book(self, order_book):
        """
        Adapter helper. Adjust this to match you OrderBook API.

        Expected return:
            (best_bid_px, best_bid_size, best_ask_px, best_ask_size)
        """
        # Example assuming your OrderBook has methods:
        # best_bid() -> Optional[float]
        # best_ask() -> Optional[float] 
        # best_bid_size() -> Optional[float]
        # best_ask_size() -> Optional[float]

        # getattr(order_book, "best_bid")' is similar to 'order_book.best_bid'.
        # If the named attribute does not exist, default is returned
        best_bid_px = getattr(order_book, "best_bid", lambda: None)()
        best_ask_px = getattr(order_book, "best_ask", lambda: None)()

        if best_bid_px is None or best_ask_px is None:
            return None

        best_bid_sz = getattr(order_book, "best_bid_size", lambda: 0.0)()
        best_ask_sz = getattr(order_book, "best_ask_size", lambda: 0.0)()

        return best_bid_px, best_bid_sz, best_ask_px, best_ask_sz
    
    def _compute_microprice(
            self,
            bid_px: float,
            bid_sz: float,
            ask_px: float,
            ask_sz: float,
    ) -> float:
        # If we don't have sizes, fall back to mid
        if bid_sz <= 0 or ask_sz <= 0:
            return (bid_px + ask_px) / 2.0
        
        # If there is more size on the bid, price is more likely to go up
        # If there is more size on the ask, price is more likely to go down 
        return (ask_px * bid_sz + bid_px * ask_sz) / (bid_sz + ask_sz)

    def _compute_working_spread(self) -> float:
        """
        Spread widens as inventory moves away from target.
        """
        inv_deviation = abs(self.position - self.cfg.inventory_target)
        widened = self.cfg.base_spread * (1.0 + self.cfg.inventory_sensitivity * inv_deviation)

        spread = max(self.cfg.min_spread, min(widened, self.cfg.max_spread))
        return spread

    def _price_move_large_enough(self, old_px: Optional[float], new_px: float) -> bool:
        if old_px is None:
            return True
        tick = self.cfg.tick_size
        return abs(new_px - old_px) >= self.cfg.price_move_threshold_ticks * tick

    def _update_quote(self, side: str, new_price: float, oms, ts_ns: int) -> None:
        """
        Create or replace our working quote on a given side. 
        """
        if side == "B":
            current_id = self.current_bid_id
            current_px = self.current_bid_px
        else:
            current_id = self.current_ask_id
            current_px = self.current_ask_px

        # Only re-quote when prices has moved enough
        if not self._price_move_large_enough(current_px, new_price):
            return

        # If we already have an order -> cancel it
        if current_id is not None:
            oms.cancel(current_id)

        # Generate new order ID
        self.order_seq += 1
        order_id = self.order_seq

        # Send new order
        oms.register(
            order_id=order_id,
            side=side,
            price=new_price,
            size=self.cfg.quote_size,
            ts=ts_ns
        )

        # Update local state 
        if side == "B":
            self.current_bid_id = order_id
            self.current_bid_px = new_price
        else:
            self.current_ask_id = order_id
            self.current_ask_px = new_price
            
        # Update last quote timestamp here
        self.last_quote_ns = ts_ns


    def _cancel_bid_if_any(self, oms) -> None:
        if self.current_bid_id is not None:
            oms.cancel(self.current_bid_id)
            self.current_bid_id = None
            self.current_bid_px = None
    
    def _cancel_ask_if_any(self, oms) -> None:
        if self.current_ask_id is not None:
            oms.cancel(self.current_ask_id)
            self.current_ask_id = None
            self.current_ask_px = None


# cfg = StrategyConfig(
#     tick_size=0.01,
#     base_spread=0.04,
#     quote_size=1.0,
#     max_position=10.0
# )

# strategy = MarketMaker(cfg)

"""
The best bid/ask is computed every time a new event arrives.
(ADD, MODIFY, CANCEL, TRADE -> any event that changes the book)

This keeps the strategy always up-to-date with the latest market prices.
"""

# for event in feed_events:
#     # 1. update order book
#     order_book.on_event(event) # or whatever your method is

#     # 2. run strategy on each event
    # ts_ns = evt["ts"] # you already store ns in your parser
    # strategy.on_book_event(order_book, oms, ts_ns)

#     # 3. when your own orders are filled, call:
#     strategy.on_your_trade(side, price, size) 