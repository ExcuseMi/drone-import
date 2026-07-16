from __future__ import annotations

import requests


def trigger_scan(url: str, api_key: str, library_id: str) -> bool:
    if not api_key or not library_id:
        return False
    try:
        resp = requests.post(
            f"{url.rstrip('/')}/Items/{library_id}/Refresh",
            headers={"X-Emby-Authorization": f'MediaBrowser Token="{api_key}"'},
            timeout=10,
        )
        return resp.ok
    except requests.RequestException:
        return False
