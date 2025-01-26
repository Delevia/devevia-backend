import httpx
from fastapi import HTTPException
from dotenv import load_dotenv
import os
from typing import List, Optional



ONESIGNAL_APP_ID = "09a1effe-4f8e-4bfa-9823-bdbfc5cf2d53"
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY")

load_dotenv()


async def send_push_notification(
    title: str,
    message: str,
    external_ids: List[str] = None,  # External IDs are optional
    segment: str = None,  # Target user segment (optional)
):
    """
    Sends a push notification via OneSignal using External IDs or a segment.

    Args:
        title (str): Notification title.
        message (str): Notification message.
        external_ids (list[str]): List of external user IDs to target (optional).
        segment (str): OneSignal segment to target (optional).

    Raises:
        HTTPException: If the request to OneSignal fails.
    """
    # Ensure at least one targeting option is provided
    if not external_ids and not segment:
        raise HTTPException(
            status_code=400,
            detail="Either 'external_ids' or 'segment' must be provided.",
        )

    url = "https://onesignal.com/api/v1/notifications"
    headers = {
        "Authorization": f"Basic {ONESIGNAL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "app_id": ONESIGNAL_APP_ID,
        "headings": {"en": title},
        "contents": {"en": message},
    }

    # Include external user IDs if provided
    if external_ids:
        payload["include_external_user_ids"] = external_ids

    # Include segment if provided
    if segment:
        payload["included_segments"] = [segment]

    # Make the request to OneSignal
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to send notification: {response.text}",
            )

        response_data = response.json()

        # Log the entire response for debugging
        print(f"OneSignal Response: {response_data}")

        # Check for errors in the response
        if "errors" in response_data:
            raise HTTPException(
                status_code=400,
                detail=f"OneSignal errors: {response_data['errors']} {response_data}",
            )

        # Handle the case where external_id is null
        if response_data.get("response", {}).get("external_id") is None:
            print("No external_id returned in the response.")

        return response_data
