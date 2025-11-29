from dataclasses import dataclass

@dataclass
class Order:
    order_id: int
    side: str
    price: float
    size: float
    ts: float

# class Order:
#     def __init__(self, order_id, side, price, size, ts):
#         self.order_id = order_id
#         self.side = side
#         self.price = price
#         self.size = size
#         self.ts = ts

#     def __repr__(self):
#         return (f"Order(id={self.order_id}, side='{self.side}', "
#                 f"px={self.price}, sz={self.size}, ts={self.ts})")