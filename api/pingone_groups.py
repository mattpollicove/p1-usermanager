"""PingOne Groups API adapter, using the existing client's OAuth credentials."""

import json
from urllib.parse import quote, urljoin, urlsplit

import httpx


class PingOneGroups:
    def __init__(self, client, http):
        self.client = client
        self.http = http

    async def request(self, method, url, **kwargs):
        base = self.client.base_url.rstrip("/") + "/"
        url = urljoin(base, url)
        target, origin = urlsplit(url), urlsplit(base)
        if target.netloc != origin.netloc or target.scheme != origin.scheme or not target.path.startswith(origin.path):
            raise ValueError("PingOne returned a link outside the target environment.")
        token = await self.client.get_token()
        if not token:
            raise RuntimeError("Could not authenticate to the target PingOne environment.")
        try:
            response = await self.http.request(method, url, headers=self.client._get_auth_headers(token), **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"PingOne {method} {target.path}: HTTP {exc.response.status_code} "
                               f"{exc.response.text[:500]}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"PingOne {method} {target.path}: {exc}. Rerun preflight to check the outcome.") from exc

    async def collection(self, url, name, params=None):
        records, visited = [], set()
        while url:
            if url in visited:
                raise ValueError("Repeated PingOne pagination link.")
            visited.add(url)
            page = await self.request("GET", url, **({"params": params} if params else {}))
            items = page.get("_embedded", {}).get(name)
            if items is None and (page.get("count") == 0 or page.get("size") == 0):
                items = []
            if not isinstance(items, list):
                raise ValueError(f"Missing {name} collection in PingOne response.")
            records.extend(items)
            url = page.get("_links", {}).get("next", {}).get("href")
            params = None
        return records

    async def groups(self):
        return await self.collection("groups", "groups")

    async def users(self):
        return await self.collection("users", "users")

    async def populations(self):
        return {pop["id"]: pop["name"] for pop in await self.collection("populations", "populations")}

    async def parents(self, group_id):
        records = await self.collection(f"groups/{quote(group_id, safe='')}/memberOfGroups", "groupMemberships")
        if any(record.get("type") not in {"DIRECT", "INDIRECT"} for record in records):
            raise ValueError("PingOne returned nesting with an unknown relationship type.")
        return {record["id"] for record in records if record["type"] == "DIRECT"}

    async def direct_members(self, group_id):
        return await self.collection("users", "users", {
            "filter": f'memberOfGroups[id eq {json.dumps(group_id)} and type eq "DIRECT"]'
        })

    async def create_group(self, group):
        body = {"name": group.name}
        if group.description:
            body["description"] = group.description
        if group.external_id:
            body["externalId"] = group.external_id
        if group.scope != "environment":
            body["population"] = {"id": group.scope}
        return (await self.request("POST", "groups", json=body))["id"]

    async def nest_group(self, child, parent):
        await self.request("POST", f"groups/{quote(child, safe='')}/memberOfGroups", json={"id": parent})

    async def add_member(self, user_id, group_id):
        await self.request("POST", f"users/{quote(user_id, safe='')}/memberOfGroups", json={"id": group_id})

    async def remove_member(self, user_id, group_id):
        await self.request("DELETE", f"users/{quote(user_id, safe='')}/memberOfGroups/{quote(group_id, safe='')}")
