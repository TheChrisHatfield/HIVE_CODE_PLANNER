import asyncio, time, websockets
async def one(i):
    t = time.monotonic()
    async with websockets.connect('ws://127.0.0.1:8998/api/chat', open_timeout=400, max_size=None) as ws:
        first = await asyncio.wait_for(ws.recv(), 400)
        print(f'conn{i} first_byte={first[:1]!r} handshake_s={time.monotonic()-t:.1f}', flush=True)
async def main():
    await one(1)
    await one(2)
asyncio.run(main())
