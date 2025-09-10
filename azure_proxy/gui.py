# gui.py
from __future__ import annotations
import os, asyncio, json
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth
from nicegui import ui, app as ngapp

TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID = os.getenv("AZURE_APP_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_APP_CLIENT_SECRET", "")  # pro public flow lze vynechat
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8787")
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-me-please")
REDIRECT_PATH = os.getenv("GUI_REDIRECT_PATH", "/auth/callback")  # musí být registrováno v Entra

def init_gui(fastapi_app: FastAPI) -> None:
    """Připojí NiceGUI k existujícímu FastAPI a zaregistruje stránky + OIDC."""
    # 1) Session pro OAuth (Authlib)
    fastapi_app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

    # 2) Napoj NiceGUI na FastAPI
    ui.run_with(fastapi_app)

    # 3) OAuth client (Entra ID OpenID provider)
    oauth = OAuth()
    oauth.register(
        name="entra",
        server_metadata_url=f"https://login.microsoftonline.com/{TENANT_ID}/v2.0/.well-known/openid-configuration",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET or None,
        client_kwargs={"scope": "openid profile email offline_access"},
        redirect_uri=PUBLIC_BASE_URL + REDIRECT_PATH,
    )

    # 4) Interní ASGI klient – volání management API bez externího HTTP
    transport = httpx.ASGITransport(app=fastapi_app)
    api = httpx.AsyncClient(transport=transport, base_url="http://internal", timeout=20.0)

    def _auth_header() -> dict:
        tok = ngapp.storage.user.get("id_token") or ngapp.storage.user.get("access_token")
        return {"Authorization": f"Bearer {tok}"} if tok else {}

    async def _api_get(path: str):
        r = await api.get(path, headers=_auth_header())
        r.raise_for_status()
        return r.json()

    async def _api_post(path: str, json_body: dict | None = None):
        r = await api.post(path, headers=_auth_header(), json=json_body or {})
        r.raise_for_status()
        return r.json() if r.content else {"ok": True}

    # --------- OIDC routy ---------
    @fastapi_app.get("/auth/login")
    async def login(request: Request):
        return await oauth.entra.authorize_redirect(request, PUBLIC_BASE_URL + REDIRECT_PATH)

    @fastapi_app.get(REDIRECT_PATH)
    async def auth_callback(request: Request):
        token = await oauth.entra.authorize_access_token(request)
        # ulož do NiceGUI user storage
        claims = token.get("userinfo") or token.get("id_token_claims") or {}
        ngapp.storage.user["id_token"] = token.get("id_token")
        ngapp.storage.user["access_token"] = token.get("access_token")
        ngapp.storage.user["name"] = claims.get("name") or claims.get("preferred_username")
        # zpět do UI
        from starlette.responses import RedirectResponse
        return RedirectResponse("/mgmt")

    @fastapi_app.get("/auth/logout")
    async def logout(request: Request):
        ngapp.storage.user.clear()
        from starlette.responses import RedirectResponse
        return RedirectResponse("/mgmt")

    # --------- NiceGUI stránka: /mgmt ---------
    @ui.page("/mgmt")
    def mgmt_page():
        ui.page_title("Proxy Management")
        with ui.header().classes("items-center justify-between"):
            ui.label("Azure OpenAI Proxy – Management")
            with ui.row().classes("items-center"):
                if ngapp.storage.user.get("id_token") or ngapp.storage.user.get("access_token"):
                    ui.label(f"Signed in as {ngapp.storage.user.get('name', 'user')}")
                    ui.button("Sign out", on_click=lambda: ui.navigate.to("/auth/logout"))
                else:
                    ui.button("Sign in with Entra ID", color="primary", on_click=lambda: ui.navigate.to("/auth/login"))

        if not (ngapp.storage.user.get("id_token") or ngapp.storage.user.get("access_token")):
            ui.label("Please sign in to manage API keys.").classes("text-grey-7 mt-8")
            return

        # --- sekce klíčů ---
        with ui.card().classes("w-full"):
            ui.label("API Keys").classes("text-lg mb-2")

            columns = [
                {"name": "prefix", "label": "Prefix", "field": "prefix"},
                {"name": "name", "label": "Name", "field": "name"},
                {"name": "is_active", "label": "Active", "field": "is_active"},
                {"name": "created_at", "label": "Created", "field": "created_at"},
                {"name": "expires_at", "label": "Expires", "field": "expires_at"},
                {"name": "last_used_at", "label": "Last used", "field": "last_used_at"},
                {"name": "rate_limit_per_minute", "label": "RPM", "field": "rate_limit_per_minute"},
            ]
            table = ui.table(columns=columns, rows=[], row_key="id", pagination=10).classes("w-full")

            async def refresh_keys():
                try:
                    rows = await _api_get("/management/apikeys")
                    table.rows = rows
                    table.update()
                    ui.notify("Keys refreshed", type="positive")
                except Exception as e:
                    ui.notify(f"Failed to load keys: {e}", type="negative")

            async def open_create_key_dialog():
                with ui.dialog() as d, ui.card():
                    name = ui.input("Name")
                    days = ui.number("Expires in days", value=90, min=1, max=3650)
                    rpm = ui.number("Rate limit (per minute)", value=None, min=1)
                    async def create():
                        payload = {
                            "name": name.value or None,
                            "expires_in_days": int(days.value) if days.value else None,
                            "rate_limit_per_minute": int(rpm.value) if rpm.value else None,
                        }
                        resp = await _api_post("/management/apikeys", json_body=payload)
                        plaintext = resp["token"]
                        ui.notify("API key created. Token will be shown once below.", type="positive", close_button="OK")
                        ui.markdown(f"**Save this token now:** `{plaintext}`").classes("mt-2")
                        await refresh_keys()
                    with ui.row().classes("justify-end mt-2"):
                        ui.button("Create", on_click=create, color="primary")
                        ui.button("Cancel", on_click=d.close)
                d.open()

            async def enable_disable(selected: dict, enable: bool):
                if not selected:
                    ui.notify("Select a key in the table first", type="warning")
                    return
                path = f"/management/apikeys/{selected['id']}/" + ("enable" if enable else "disable")
                await _api_post(path)
                await refresh_keys()

            with ui.row().classes("gap-2 mb-2"):
                ui.button("Refresh", on_click=refresh_keys)
                ui.button("Create key", color="primary", on_click=open_create_key_dialog)
                ui.button("Enable", on_click=lambda: enable_disable(table.selected, True))
                ui.button("Disable", on_click=lambda: enable_disable(table.selected, False))

        # --- sekce spotřeby ---
        with ui.card().classes("w-full mt-4"):
            ui.label("Usage (last 30 days)").classes("text-lg mb-2")
            chart = ui.echart(
                {
                    "tooltip": {"trigger": "axis"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value"},
                    "legend": {"data": ["requests", "total_tokens"]},
                    "series": [
                        {"name": "requests", "type": "bar", "data": []},
                        {"name": "total_tokens", "type": "line", "data": []},
                    ],
                }
            ).classes("w-full h-80")

            async def load_usage():
                sel = table.selected
                if not sel:
                    ui.notify("Select a key to load usage", type="warning")
                    return
                payload = {"key_id": sel["id"], "bucket": "day"}
                rows = await _api_post("/management/usage", json_body=payload)
                xs = [r["bucket"] for r in rows]
                reqs = [r["requests"] for r in rows]
                toks = [r.get("total_tokens") or 0 for r in rows]
                chart.options["xAxis"]["data"] = xs
                chart.options["series"][0]["data"] = reqs
                chart.options["series"][1]["data"] = toks
                chart.update()

            with ui.row().classes("gap-2"):
                ui.button("Load usage for selected key", on_click=load_usage)

        # úvodní načtení
        asyncio.create_task(refresh_keys())
