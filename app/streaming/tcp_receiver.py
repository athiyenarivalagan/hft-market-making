import time
import asyncio

from app.mbo.mbo_parser import parse_csv_line
from app.orderbook.orderbook import OrderBook
from app.strategy.market_maker import StrategyConfig, MarketMaker
from app.oms.oms import OMS
from app.monitoring.logging import get_logger
from app.monitoring.metrics import Metrics


async def receive_mbo(host="127.0.0.1", port=9999):
    """Main event loop for:
    - receiving TCP MBO data
    - updating the order book
    - executing strategy 
    - logging + monitoring
    """

    log = get_logger()
    metrics = Metrics()

    # reconnection logic
    # While True: 
    #     try:

    # Connect to TCP feed
    reader, writer = await asyncio.open_connection(host, port)

    # Core system modules
    book = OrderBook()
    oms = OMS()
    cfg = StrategyConfig()
    # cfg = StrategyConfig(
    #     tick_size=0.01,
    #     base_spread=0.04,
    #     quote_size=1.0,
    #     max_position=10.0
    # )
    strategy = MarketMaker(cfg)

    # --- Read header line ---
    header_line = await reader.readline()
    if not header_line:
        print("Empty stream: no header received.")
        writer.close()
        await writer.wait_closed()
        return
    
    header_cols = [h.strip() for h in header_line.decode().split(",")]
    # Skip first column (feed timestamp) and map remaining header names to column indices
    header = {name: i for i, name in enumerate(header_cols[1: ])}
    # print("Header map:", header)
    
    # "\n" disappears in print() because it prints it and moves to the next line
    # repr() does not interpret escape characters — it shows them literally
    # print(repr(decode_line))

    # Stats
    msg_count = 0
    last_print = time.time()

    # Main loop
    while True:
        line = await reader.readline()
        # Pure feed-arrival latency (network-only)
        if not line:
            print("Connection closed by sender.")
            break

        # Pure feed-arrival latency (network-only)
        process_message(line, log)

        # -----------------------
        # INTERNAL LATENCY START
        # -----------------------
        start_ns = time.time_ns()

        # -----------------------
        # 1. Parse event
        # -----------------------
        try:
            evt = parse_csv_line(header, line.decode())
        except Exception as e:
            log.error("Parse error: %s | Line: %s", e, line)
            continue

        # log.info("Received event %s", evt)

        act = evt["action"]
        ts = evt["ts"]

        # -----------------------
        # 2. Update order book
        # -----------------------        
        if act == "ADD":
            book.on_add(evt["order_id"], evt["side"], evt["price"], evt["size"], ts)
        elif act == "MOD":
            book.on_modify(evt["order_id"], evt["price"], evt["size"], ts)
        elif act == "CXL":
            book.on_cancel(evt["order_id"])
        elif act == "TRD":
            book.on_trade(evt["order_id"], evt["size"], ts) 
        elif act == "FILL":
            book.on_trade(evt["order_id"], evt["size"], ts)
        elif act == "CLR":
            book.clear()

        # print("ORDERS:", book.lookup)
        # print("BIDS:", book.bids)     
        # print("ASKS:", book.asks)

        # -----------------------
        # 3. Run strategy
        # -----------------------
        strategy.on_book_event(book, oms, ts)
        # print("OMS:", oms.orders)
        # strategy.on_own_trade(side, price, size)

        # -----------------------
        # INTERNAL LATENCY END
        # -----------------------
        end_ns = time.time_ns()
        metrics.record_latency(end_ns - start_ns) 

        # -----------------------
        # 4. Throughput stats
        # -----------------------
        msg_count += 1
        now = time.time()
        if now - last_print >= 1.0:
            thr, p99 = metrics.summary()

            # log.info("Throughput: %.1f msg/s | p99 latency: %.3f ms",
            #          thr, p99)
            
            # Reset counters for clean next-second stats
            metrics.reset()
            last_print = now
            msg_count = 0


        # except ConnectionRefusedError:
        #     print("Sender not ready. Retrying in 2s... ")
        #     await asyncio.sleep(2)

        # except ConnectionResetError:
        #     print("Connection reset. Retrying in 2s...")
        #     await asyncio.sleep(2)
        
        # except asyncio.TimeoutError:
        #     print("Connection timed out. Retrying in 2s...")
        #     await asyncio.sleep(2)
        
        # except Exception as e:
        #     print("Unexpected error: {e}. Retrying in 2s...")
        #     await.ayncio.sleep(2)
    
        # finally:
        #     try:
        #         writer.close()
        #         await writer.wait_closed()
        #     except Exception:
        #         pass

    # Cleanup
    writer.close()
    await writer.wait_closed()
    print("Connection closed.")


def process_message(line, log):
    """Calculate Market Data Arrival Latency and log high latency warnings."""
    try:
        # Decode bytes -> extract timestamp and payload
        sent_ts, payload = line.decode().split(",", 1)
        latency_ms = (time.time() - float(sent_ts)) * 1000

        # Print message latency in milliseconds (ms)
        print(f"Latency: {latency_ms:.3f} ms | Data: {payload.strip()}")

        # Log warning if > 5ms
        if latency_ms > 5.0:
            log.warning("High latency: %.3f ms", latency_ms)

    except Exception as e:
        # print(f"Malformed line ({e}):", line)
        log.error("Malformed line (%s): %s", e, line)

if __name__=="__main__":
    asyncio.run(receive_mbo())