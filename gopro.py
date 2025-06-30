import requests
import socket
import time
from typing import Optional


def _enable_wifi_via_bluetooth(mac_address: str) -> None:
    """Best effort attempt to enable WiFi on the GoPro using BLE.

    This implementation follows the gist of GoPro's tutorial which writes a
    specific value over BLE to enable the WiFi access point.  It silently
    ignores all errors so that the capture can continue even if BLE support is
    not available on the host system.
    """

    try:
        from bleak import BleakClient
        import asyncio
    except Exception:
        return

    async def _run() -> None:
        char = "d44bc439-abfd-45a2-b575-925416129600"
        async with BleakClient(mac_address) as client:
            await client.write_gatt_char(char, b"\x03")

    try:
        asyncio.run(_run())
    except Exception:
        pass


def _wait_for_ip(ip_address: str, port: int, timeout: int = 30) -> None:
    """Wait until a TCP connection to the given IP address succeeds."""

    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            with socket.create_connection((ip_address, port), timeout=2):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"Unable to connect to {ip_address}:{port}")

# Attempt to enable the camera WiFi using Bluetooth LE and wait for IP
# connectivity before capturing a photo.  The BLE procedure follows the
# `enable_wifi_ap.py` example from the OpenGoPro tutorials but any failures are
# ignored to keep the function usable on systems without BLE capabilities.

def capture_gopro_photo(
    ip_address: str = "10.5.5.9",
    output_file: Optional[str] = None,
    timeout: int = 5,
    root_ca: Optional[str] = None,
    ble_mac: Optional[str] = None,
) -> bytes:
    """Capture a photo from a GoPro over WiFi.

    This function triggers the shutter on a GoPro camera and downloads the
    most recent photo using the camera's built-in HTTP API.

    Args:
        ip_address: IP address of the GoPro (default is 10.5.5.9).
        output_file: Optional path to save the downloaded image.
        timeout: Timeout in seconds for the HTTP requests.
        root_ca: Optional PEM-encoded certificate authority to verify HTTPS
            connections.
        ble_mac: Optional Bluetooth MAC address of the camera used to enable
            WiFi if it is not already running.

    Returns:
        The raw bytes of the captured JPEG image.

    Raises:
        requests.RequestException: If any of the network calls fail.
    """

    scheme = "https" if root_ca else "http"
    verify_path = True
    temp_file = None
    if root_ca:
        import tempfile, os

        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file.write(root_ca.encode())
        temp_file.close()
        verify_path = temp_file.name

    if ble_mac:
        _enable_wifi_via_bluetooth(ble_mac)

    # Wait for the camera to become reachable over the network
    port = 443 if scheme == "https" else 80
    _wait_for_ip(ip_address, port, timeout)

    # Set the control mode to pro
    control_mode_url = f"{scheme}://{ip_address}/api/v1/camera/setting"
    requests.post(
        control_mode_url,
        json={"setting_id": 175, "value": 1},
        timeout=timeout,
        verify=verify_path,
    )

    # Set the preset to photo night
    preset_url = f"{scheme}://{ip_address}/api/v1/camera/preset"
    requests.post(
        preset_url,
        json={"preset_id": 65539},
        timeout=timeout,
        verify=verify_path,
    )

    trigger_url = f"{scheme}://{ip_address}/api/v1/command/shutter"
    requests.post(
        trigger_url,
        timeout=timeout,
        verify=verify_path,
    )

    # Small delay to allow the camera to process the capture
    time.sleep(2)

    # Retrieve the media list to find the latest file. The OpenGoPro API returns
    # a list of directories with the files they contain. We support both the
    # older `d`/`fs` fields as well as the newer `directory`/`files` names.
    media_list_url = f"{scheme}://{ip_address}/api/v1/media/list"
    resp = requests.get(media_list_url, timeout=timeout, verify=verify_path)
    resp.raise_for_status()
    data = resp.json()

    media_entries = data.get("media") or data.get("results", {}).get("media")
    if not media_entries:
        raise RuntimeError("No media information returned from GoPro")

    latest_dir_info = media_entries[-1]
    latest_dir = latest_dir_info.get("directory") or latest_dir_info.get("d")

    if "filename" in latest_dir_info:
        latest_file = latest_dir_info["filename"]
    else:
        files = latest_dir_info.get("files") or latest_dir_info.get("fs")
        if not files:
            raise RuntimeError("No files returned by GoPro")
        latest_file_info = files[-1]
        latest_file = latest_file_info.get("filename") or latest_file_info.get("n")

    photo_url = f"{scheme}://{ip_address}/api/v1/media/{latest_dir}/{latest_file}"
    photo_resp = requests.get(photo_url, timeout=timeout, verify=verify_path)
    photo_resp.raise_for_status()

    if output_file:
        with open(output_file, "wb") as f:
            f.write(photo_resp.content)

    if temp_file:
        import os

        os.unlink(temp_file.name)

    return photo_resp.content
