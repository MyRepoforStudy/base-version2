from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


class ZabbixApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ZabbixHostState:
    hostid: str
    host_name: str
    agent_availability: str
    problem_count: int
    monitoring_status: str
    url: str


class ZabbixClient:
    def __init__(
        self,
        base_url: str,
        api_token: str,
        timeout: int = 20,
        verify_ssl: bool = True,
        ca_file: str | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("ZABBIX_URL is required")
        if not api_token:
            raise ValueError("ZABBIX_API_TOKEN is required")
        normalized_url = base_url.rstrip("/")
        if normalized_url.endswith("/api_jsonrpc.php"):
            self.api_url = normalized_url
            self.base_url = normalized_url[: -len("/api_jsonrpc.php")]
        else:
            self.base_url = normalized_url
            self.api_url = self._api_url(self.base_url)
        self.api_token = api_token
        self.timeout = timeout
        self.ssl_context = self._ssl_context(verify_ssl, ca_file)
        self._request_id = 0

    def _api_url(self, base_url: str) -> str:
        if base_url.endswith("/api_jsonrpc.php"):
            return base_url
        return urljoin(f"{base_url}/", "api_jsonrpc.php")

    def _ssl_context(self, verify_ssl: bool, ca_file: str | None) -> ssl.SSLContext | None:
        if not self.api_url.startswith("https://"):
            return None
        if not verify_ssl:
            return ssl._create_unverified_context()
        if ca_file:
            ca_path = Path(ca_file)
            if not ca_path.is_file():
                raise ZabbixApiError(f"ZABBIX_CA_FILE must point to a certificate file: {ca_file}")
            return ssl.create_default_context(cafile=ca_file)
        return ssl.create_default_context()

    def _call(self, method: str, params: dict[str, Any]) -> Any:
        self._request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }
        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json-rpc",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout, context=self.ssl_context) as response:
                data = json.loads(response.read().decode("utf-8"))
        except ssl.SSLError as exc:
            raise ZabbixApiError(f"Zabbix API SSL error: {exc}") from exc
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ZabbixApiError(f"Zabbix API HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise ZabbixApiError(f"Cannot reach Zabbix API: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ZabbixApiError("Zabbix API returned invalid JSON") from exc

        if "error" in data:
            error = data["error"]
            message = error.get("message", "Zabbix API error")
            details = error.get("data")
            if details:
                message = f"{message}: {details}"
            raise ZabbixApiError(message)
        return data.get("result")

    def get_host_groups_by_names(self, group_names: list[str]) -> list[dict[str, Any]]:
        if not group_names:
            return []
        return self._call(
            "hostgroup.get",
            {
                "output": ["groupid", "name"],
                "filter": {"name": group_names},
            },
        )

    def get_hosts_by_groupids(self, groupids: list[str]) -> list[dict[str, Any]]:
        if not groupids:
            return []
        return self._call(
            "host.get",
            {
                "output": ["hostid", "host", "name", "status"],
                "groupids": groupids,
                "selectInterfaces": [
                    "interfaceid",
                    "type",
                    "main",
                    "available",
                    "ip",
                    "dns",
                    "useip",
                    "error",
                ],
                "selectInventory": self._inventory_fields(),
                "selectTags": ["tag", "value"],
                "sortfield": ["name", "host"],
            },
        )

    def _inventory_fields(self) -> list[str]:
        return ["os", "os_full", "os_short", "vendor", "model", "hardware", "hardware_full", "location"]

    def get_latest_item_values(self, hostid: str, item_keys: list[str] | tuple[str, ...]) -> dict[str, str]:
        if not item_keys:
            return {}
        items = self._call(
            "item.get",
            {
                "output": ["itemid", "key_", "lastvalue"],
                "hostids": [str(hostid)],
                "filter": {"key_": list(item_keys)},
            },
        )
        item_values: dict[str, str] = {}
        for item in items or []:
            key = item.get("key_")
            value = item.get("lastvalue")
            if key and value not in (None, ""):
                item_values[str(key)] = str(value)
        return item_values

    def get_latest_item_values_bulk(
        self, hostids: list[str], item_keys: list[str] | tuple[str, ...]
    ) -> dict[str, dict[str, str]]:
        if not hostids or not item_keys:
            return {}
        items = self._call(
            "item.get",
            {
                "output": ["hostid", "key_", "lastvalue"],
                "hostids": hostids,
                "filter": {"key_": list(item_keys)},
            },
        )
        by_host: dict[str, dict[str, str]] = {}
        for item in items or []:
            hostid = str(item.get("hostid"))
            key = item.get("key_")
            value = item.get("lastvalue")
            if not hostid or not key or value in (None, ""):
                continue
            by_host.setdefault(hostid, {})[str(key)] = str(value)
        return by_host

    def get_latest_item_values_bulk_by_prefix(
        self,
        hostids: list[str],
        key_prefixes: list[str] | tuple[str, ...],
    ) -> dict[str, dict[str, str]]:
        if not hostids or not key_prefixes:
            return {}
        by_host: dict[str, dict[str, str]] = {}
        for key_prefix in key_prefixes:
            items = self._call(
                "item.get",
                {
                    "output": ["hostid", "key_", "lastvalue"],
                    "hostids": hostids,
                    "search": {"key_": key_prefix},
                    "startSearch": True,
                },
            )
            for item in items or []:
                hostid = str(item.get("hostid"))
                key = item.get("key_")
                value = item.get("lastvalue")
                if not hostid or not key or value in (None, ""):
                    continue
                by_host.setdefault(hostid, {})[str(key)] = str(value)
        return by_host

    def get_current_problems(self, hostid: str) -> list[dict[str, Any]]:
        return self._call(
            "problem.get",
            {
                "output": ["eventid", "name", "severity", "clock"],
                "hostids": [hostid],
                "sortfield": "eventid",
                "sortorder": "DESC",
            },
        )

    def get_current_problems_bulk(self, hostids: list[str]) -> dict[str, list[dict[str, Any]]]:
        # Zabbix's problem.get has no reliable way to attribute problems back to
        # a host when queried for multiple hostids at once, so this is one
        # problem.get call per host (same as the reference implementation).
        return {hostid: self.get_current_problems(hostid) for hostid in hostids}

    def host_state_from_host(self, host: dict[str, Any], problem_count: int | None = None) -> ZabbixHostState:
        hostid = str(host["hostid"])
        if problem_count is None:
            problem_count = len(self.get_current_problems(hostid))
        availability = self.agent_availability_from_host(host)
        status = self.monitoring_status_from_host(host, availability, problem_count)

        return ZabbixHostState(
            hostid=hostid,
            host_name=host.get("name") or host.get("host") or hostid,
            agent_availability=availability,
            problem_count=problem_count,
            monitoring_status=status,
            url=self.build_host_url(hostid),
        )

    def primary_interface_address(self, host: dict[str, Any]) -> str | None:
        interfaces = host.get("interfaces") or []
        if not interfaces:
            return None
        primary = next((interface for interface in interfaces if str(interface.get("main")) == "1"), None)
        selected = primary or interfaces[0]
        if str(selected.get("useip")) == "1" and selected.get("ip"):
            return selected["ip"]
        if selected.get("dns"):
            return selected["dns"]
        return selected.get("ip")

    def build_host_url(self, hostid: str) -> str:
        return f"{self.base_url}/zabbix.php?action=host.dashboard.view&hostid={quote(str(hostid))}"

    def agent_availability_from_host(self, host: dict[str, Any]) -> str:
        interfaces = host.get("interfaces") or []
        agent_interfaces = [interface for interface in interfaces if str(interface.get("type")) == "1"]
        primary = next((interface for interface in agent_interfaces if str(interface.get("main")) == "1"), None)
        selected = primary or (agent_interfaces[0] if agent_interfaces else None)
        if not selected:
            return "unknown"
        return self._availability_label(selected.get("available"))

    def _availability_label(self, value: Any) -> str:
        return {
            "0": "unknown",
            "1": "available",
            "2": "unavailable",
        }.get(str(value), "unknown")

    def monitoring_status_from_host(self, host: dict[str, Any], availability: str, problem_count: int) -> str:
        if str(host.get("status")) == "1":
            return "disabled"
        if problem_count > 0:
            return "problem"
        if availability == "unavailable":
            return "down"
        if availability == "available":
            return "ok"
        return "unknown"
