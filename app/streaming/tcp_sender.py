import asyncio, aiofiles
import time 

async def send_mbo(reader_path, host="127.0.0.1", port=9999, rate=50000):
    """Start a non-blocking TCP server that streams MBO data to connected clients."""
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, reader_path, rate),
        host, port
    )
    print(f"TCP server started on {host}:{port}, streaming {reader_path}")

    async with server:
        await server.serve_forever()


async def handle_client(reader, writer, reader_path, rate):
    """Stream file lines (MBO data) to a connected client at approx 'rate' lines/sec"""
    addr = writer.get_extra_info("peername") # Log the connected client address
    print(f"Connected : {addr}")

    sent = 0
    start = time.time()
    
    async with aiofiles.open(reader_path, "rb") as f:
        while True:
            chunk = await f.readline()
            # chunk = await f.readexactly(n) # for efficiency
            if not chunk:
                break

            # [Debug]
            # chunk_1 = await f.readline() # Read one line from the input file/stream
            # chunk_2 = await f.readline() # Read the next line

            # if chunk_2:
            #     timestamp = time.time()
            #     print(f"\n[Send] timestamp={timestamp} ({type(str(timestamp).encode())})")
            #     print(f"Data: {chunk_2.strip()} ({type(chunk_2)})\n")
            #     timestamp = str(time.time()).encode() + b"," + chunk_2
            #     print(f"[Send Updated] {timestamp}")
            #     writer.write(chunk_2) # Queue bytes for sending via the transport buffer
            
            # Prefix timestamp for latency measurement
            timestamp = str(time.time()).encode() + b"," + chunk
            writer.write(timestamp) 
            print(f"Sending: {chunk.strip()}")
            sent += 1

            # Occasionally wait for the transport buffer to flush.
            # (Backpressure management) – prevents message queues from overflowing.
            if sent % 256 == 0:
                await writer.drain()

            # Simple rate limiter: send 'rate' lines per second
            if sent % rate == 0:
                elapsed = time.time() - start
                if elapsed < 1:
                    await asyncio.sleep(1 - elapsed)
                start = time.time()
                
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    print(f"Finished streaming to {addr} (sent {sent} lines)")
        
if __name__=="__main__":
    asyncio.run(send_mbo("data/processed/CLX5_mbo.txt"))