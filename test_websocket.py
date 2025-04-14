import websockets
import asyncio
import json  # Import json module



async def websocket_client(driver_id):
    uri = f"ws://localhost:8000/ws/drivers/{driver_id}"

    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"✅ Connected to WebSocket as Driver {driver_id}")

                while True:
                    await asyncio.sleep(30)
                    heartbeat_message = {
                        "type": "heartbeat",
                        "driver_id": driver_id
                    }
                    await websocket.send(json.dumps(heartbeat_message))
                    print(f"💓 Sent heartbeat for Driver {driver_id}")

        except websockets.ConnectionClosed:
            print("❌ Connection lost. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

asyncio.run(websocket_client(13))