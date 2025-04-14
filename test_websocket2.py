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
                    # Wait for a message from the server
                    message = await websocket.recv()

                    # Attempt to parse the received message as JSON
                    try:
                        data = json.loads(message)
                        print(f"📨 Received message: {data}")

                        # Handle different types of messages
                        if data.get("type") == "ride_request":
                            print(f"🚖 New ride request received!")
                            print(f"Pickup Location: {data.get('pickup_location')}")
                            print(f"Dropoff Location: {data.get('dropoff_location')}")
                            print(f"Fare: {data.get('fare')}")
                            print(f"Estimated Price: {data.get('estimated_price')}")
                            # You can add more logic here to handle the ride request
                        
                    except json.JSONDecodeError:
                        print("❌ Failed to decode message")

                    # Send a heartbeat every 30 seconds
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


# Start the WebSocket client for Driver 13
asyncio.run(websocket_client(13))