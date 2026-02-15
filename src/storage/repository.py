from collections import defaultdict


class DeviceRepository:
    def __init__(self) -> None:
        self._devices: dict[str, list[dict[str, str]]] = defaultdict(list)

    def register(self, user_id: str, platform: str, token: str) -> None:
        devices = [d for d in self._devices[user_id] if d["token"] != token]
        devices.append({"platform": platform, "token": token})
        self._devices[user_id] = devices

    def list_tokens(self, user_id: str, platform: str | None = None) -> list[str]:
        devices = self._devices.get(user_id, [])
        if platform:
            return [d["token"] for d in devices if d["platform"] == platform]
        return [d["token"] for d in devices]

    def all_tokens_by_platform(self, platform: str) -> list[str]:
        tokens: list[str] = []
        for devices in self._devices.values():
            tokens.extend([d["token"] for d in devices if d["platform"] == platform])
        return tokens
