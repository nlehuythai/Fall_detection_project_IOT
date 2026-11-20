
import os

import httpx
from fastapi import HTTPException


CENTRAL_AI_API_URL = os.getenv(
    "CENTRAL_AI_API_URL",
    "http://127.0.0.1:8001"
)

CENTRAL_AI_API_KEY = os.getenv("CENTRAL_AI_API_KEY")


def get_headers():
    if not CENTRAL_AI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Central AI API key is not configured"
        )

    return {
        "X-Internal-API-Key": CENTRAL_AI_API_KEY
    }


def start_camera(camera_id: int, stream_url: str):
    try:
        response = httpx.post(
            f"{CENTRAL_AI_API_URL}/internal/cameras/{camera_id}/start",
            json={
                "stream_url": stream_url
            },
            headers=get_headers(),
            timeout=30.0
        )

        response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get(
                "detail",
                "Central AI Server error"
            )
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Central AI Server"
        )


def stop_camera(camera_id: int):
    try:
        response = httpx.post(
            f"{CENTRAL_AI_API_URL}/internal/cameras/{camera_id}/stop",
            headers=get_headers(),
            timeout=30.0
        )

        response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get(
                "detail",
                "Central AI Server error"
            )
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Central AI Server"
        )
def get_cameras():
    try:
        response = httpx.get(
            f"{CENTRAL_AI_API_URL}/internal/cameras",
            headers=get_headers(),
            timeout=10.0
        )

        response.raise_for_status()

        return response.json()

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail="Central AI Server returned an error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Central AI Server"
        )
async def open_camera_stream(camera_id: int):
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, read=None)
    )

    try:
        request = client.build_request(
            "GET",
            f"{CENTRAL_AI_API_URL}/internal/cameras/{camera_id}/stream",
            headers=get_headers()
        )

        response = await client.send(
            request,
            stream=True
        )

        if response.status_code != 200:
            await response.aread()

            try:
                detail = response.json().get(
                    "detail",
                    "Central AI Server streaming error"
                )
            except ValueError:
                detail = "Central AI Server streaming error"

            status_code = response.status_code

            await response.aclose()
            await client.aclose()

            raise HTTPException(
                status_code=status_code,
                detail=detail
            )

        return client, response

    except HTTPException:
        raise

    except httpx.RequestError:
        await client.aclose()

        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Central AI Server"
        )