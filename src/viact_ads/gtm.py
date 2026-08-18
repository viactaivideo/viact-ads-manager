"""Google Tag Manager — read containers, workspaces, tags, triggers, variables.

Read-only by design for now. Publishing a container change takes effect on the
live website immediately, so that is deliberately not exposed here.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .google_api import GoogleApiClient, required_env

BASE = "https://tagmanager.googleapis.com/tagmanager/v2"

# GTM-XXXXXXX is the public ID printed in the website snippet. The API needs
# the numeric container ID from the Tag Manager URL, so a public ID has to be
# resolved before it can be used.
_PUBLIC_ID = re.compile(r"^GTM-[A-Z0-9]+$", re.I)


def account_id(explicit: str | None = None) -> str:
    raw = explicit or required_env(
        "GTM_ACCOUNT_ID",
        "Take it from the Tag Manager URL, after /accounts/.")
    digits = re.sub(r"[^0-9]", "", str(raw))
    if not digits:
        raise ValueError(f"GTM account ID must be numeric, got {raw!r}.")
    return digits


class GTMClient:
    def __init__(self, api: GoogleApiClient) -> None:
        self._api = api

    async def accounts(self) -> dict[str, Any]:
        payload = await self._api.get(f"{BASE}/accounts")
        return {"accounts": [{"account_id": a.get("accountId"),
                              "name": a.get("name")}
                             for a in payload.get("account", [])]}

    async def containers(self, account: str | None = None) -> dict[str, Any]:
        aid = account_id(account)
        payload = await self._api.get(f"{BASE}/accounts/{aid}/containers")
        return {"account_id": aid,
                "containers": [{"container_id": c.get("containerId"),
                                "public_id": c.get("publicId"),
                                "name": c.get("name"),
                                "usage_context": c.get("usageContext"),
                                "path": c.get("path")}
                               for c in payload.get("container", [])]}

    async def resolve_container(
        self, container: str | None = None, account: str | None = None
    ) -> tuple[str, str]:
        """Return (account_id, numeric container_id), accepting either form.

        A GTM-XXXX public ID is looked up against the account's containers, so
        the value from the website snippet works as well as the numeric one.
        """
        aid = account_id(account)
        raw = container or os.environ.get("GTM_CONTAINER_ID", "").strip()
        if not raw:
            raise ValueError(
                "GTM_CONTAINER_ID is not set. Either the numeric ID from the "
                "Tag Manager URL or the GTM-XXXX public ID will do.")
        if not _PUBLIC_ID.match(raw):
            digits = re.sub(r"[^0-9]", "", raw)
            if digits:
                return aid, digits
            raise ValueError(f"Unrecognised container id {raw!r}.")

        listing = await self.containers(aid)
        for c in listing["containers"]:
            if str(c["public_id"]).upper() == raw.upper():
                return aid, str(c["container_id"])
        known = ", ".join(str(c["public_id"]) for c in listing["containers"])
        raise ValueError(
            f"No container with public ID {raw} under account {aid}. "
            f"Found: {known or '(none)'}")

    async def workspaces(self, container: str | None = None,
                         account: str | None = None) -> dict[str, Any]:
        aid, cid = await self.resolve_container(container, account)
        payload = await self._api.get(
            f"{BASE}/accounts/{aid}/containers/{cid}/workspaces")
        return {"account_id": aid, "container_id": cid,
                "workspaces": [{"workspace_id": w.get("workspaceId"),
                                "name": w.get("name"),
                                "description": w.get("description")}
                               for w in payload.get("workspace", [])]}

    async def _default_workspace(self, aid: str, cid: str) -> str:
        payload = await self._api.get(
            f"{BASE}/accounts/{aid}/containers/{cid}/workspaces")
        spaces = payload.get("workspace", [])
        if not spaces:
            raise ValueError(f"Container {cid} has no workspaces.")
        for w in spaces:
            if str(w.get("name", "")).lower() == "default workspace":
                return str(w.get("workspaceId"))
        return str(spaces[0].get("workspaceId"))

    async def _listing(self, kind: str, key: str, container, account, workspace):
        aid, cid = await self.resolve_container(container, account)
        wid = workspace or await self._default_workspace(aid, cid)
        payload = await self._api.get(
            f"{BASE}/accounts/{aid}/containers/{cid}/workspaces/{wid}/{kind}")
        return aid, cid, wid, payload.get(key, [])

    async def tags(self, container=None, account=None, workspace=None) -> dict[str, Any]:
        aid, cid, wid, items = await self._listing(
            "tags", "tag", container, account, workspace)
        tags = [{"tag_id": t.get("tagId"), "name": t.get("name"),
                 "type": t.get("type"), "paused": t.get("paused", False),
                 "firing_trigger_ids": t.get("firingTriggerId", []),
                 "parameters": {p.get("key"): p.get("value")
                                for p in t.get("parameter", [])
                                if p.get("key")}}
                for t in items]
        return {"account_id": aid, "container_id": cid, "workspace_id": wid,
                "count": len(tags), "tags": tags}

    async def triggers(self, container=None, account=None, workspace=None) -> dict[str, Any]:
        aid, cid, wid, items = await self._listing(
            "triggers", "trigger", container, account, workspace)
        triggers = [{"trigger_id": t.get("triggerId"), "name": t.get("name"),
                     "type": t.get("type")} for t in items]
        return {"account_id": aid, "container_id": cid, "workspace_id": wid,
                "count": len(triggers), "triggers": triggers}

    async def variables(self, container=None, account=None, workspace=None) -> dict[str, Any]:
        aid, cid, wid, items = await self._listing(
            "variables", "variable", container, account, workspace)
        variables = [{"variable_id": v.get("variableId"), "name": v.get("name"),
                      "type": v.get("type")} for v in items]
        return {"account_id": aid, "container_id": cid, "workspace_id": wid,
                "count": len(variables), "variables": variables}

    async def versions(self, container=None, account=None) -> dict[str, Any]:
        aid, cid = await self.resolve_container(container, account)
        payload = await self._api.get(
            f"{BASE}/accounts/{aid}/containers/{cid}/version_headers")
        return {"account_id": aid, "container_id": cid,
                "versions": [{"version_id": v.get("containerVersionId"),
                              "name": v.get("name"),
                              "deleted": v.get("deleted", False)}
                             for v in payload.get("containerVersionHeader", [])][:20]}
