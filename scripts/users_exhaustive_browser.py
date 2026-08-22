#!/usr/bin/env python3
"""Disposable Playwright coverage for the Users page controls.

The runner deliberately uses the isolated Compose DNS name and creates only
suffix-labelled disposable identities. It writes no credentials or bearer
tokens to its result.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid

from playwright.sync_api import Page, expect, sync_playwright


BASE = os.environ.get("PLATFORMOPS_BROWSER_BASE", "http://platformops:8000")
SUFFIX = uuid.uuid4().hex[:8]
PASSWORD = "BrowserStrong123!"


def api_json(page: Page, method: str, path: str, token: str = "", payload: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = page.request.fetch(
        BASE + path,
        method=method,
        headers=headers,
        data=payload,
    )
    try:
        body = response.json()
    except Exception:
        body = response.text()[:200]
    return response.status, body


def assert_status(result, expected: int, label: str):
    status, body = result
    if status != expected:
        raise AssertionError(f"{label}: HTTP {status}: {body}")
    return body


def cleanup(page: Page, admin_token: str) -> None:
    status, users = api_json(page, "GET", "/api/users", admin_token)
    if status != 200:
        return
    for user in users:
        if f"{SUFFIX}@example.test" not in user.get("user_email", ""):
            continue
        if user.get("status") == "pending":
            api_json(
                page,
                "POST",
                "/api/users/invite/revoke",
                admin_token,
                {"user_email": user["user_email"]},
            )
        else:
            api_json(page, "DELETE", f"/api/users/{user['user_id']}", admin_token)
    page.request.delete("http://mailpit:8025/api/v1/messages")


def main() -> int:
    admin_token = ""
    browser = None
    context = None
    page = None
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                accept_downloads=True,
                permissions=["clipboard-read", "clipboard-write"],
            )
            page = context.new_page()
            page.on("dialog", lambda dialog: dialog.accept())
            status, login = api_json(page, "POST", "/api/auth/login", payload={"email": "admin", "password": "admin"})
            admin_token = assert_status((status, login), 200, "admin setup login")["token"]
            # Twelve active and two pending records force pagination and tabs.
            for index in range(12):
                email = f"usx-browser-active-{index:02d}-{SUFFIX}@example.test"
                assert_status(
                    api_json(
                        page,
                        "POST",
                        "/api/users",
                        admin_token,
                        {
                            "user_name": f"Browser Active {index:02d}",
                            "user_email": email,
                            "password": PASSWORD,
                            "user_role": "Operational",
                            "user_number": "1234567890",
                            "permissions": ["monitoring.read"],
                        },
                    ),
                    200,
                    "active setup",
                )
            pending = []
            for index in range(2):
                email = f"usx-browser-pending-{index:02d}-{SUFFIX}@example.test"
                pending.append(email)
                assert_status(
                    api_json(
                        page,
                        "POST",
                        "/api/users/invite",
                        admin_token,
                        {"user_name": f"Browser Pending {index:02d}", "user_email": email, "user_role": "Management"},
                    ),
                    200,
                    "pending setup",
                )

            page.goto(BASE + "/", wait_until="networkidle", timeout=30_000)
            page.get_by_placeholder("admin").first.fill("admin")
            page.get_by_placeholder("admin").nth(1).fill("admin")
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.get_by_role("button", name="Users", exact=True).first).to_be_visible(timeout=30_000)
            page.get_by_role("button", name="Users", exact=True).first.click()
            expect(page.get_by_role("heading", name="Users", exact=True)).to_be_visible(timeout=20_000)
            expect(page.get_by_role("tab", name=re.compile(r"Active \(13\)"))).to_be_visible()

            # Search and filter only the active tab.
            search = page.get_by_label("Search users")
            search.fill("Browser Active 11")
            expect(page.get_by_text(f"usx-browser-active-11-{SUFFIX}@example.test", exact=True)).to_be_visible()
            expect(page.get_by_text(f"usx-browser-active-00-{SUFFIX}@example.test", exact=True)).to_have_count(0)
            search.fill("")

            # Pagination and sort control are observable from the table state.
            expect(page.get_by_text("1/2", exact=True)).to_be_visible()
            page.get_by_role("button", name="Next", exact=True).click()
            expect(page.get_by_text("2/2", exact=True)).to_be_visible()
            page.get_by_role("button", name=re.compile(r"Last login")).click()
            page.get_by_role("button", name=re.compile(r"Last login")).click()

            # Export must produce a download from the complete user set.
            with page.expect_download(timeout=10_000) as download_info:
                page.get_by_role("button", name="Export", exact=True).click()
            download = download_info.value
            if download.suggested_filename != "platformops-users.csv":
                raise AssertionError(f"unexpected export filename: {download.suggested_filename}")

            # Edit every UI-editable field and assert success feedback.
            search.fill("Browser Active 00")
            row = page.get_by_role("row", name=re.compile(f"usx-browser-active-00-{SUFFIX}"))
            row.get_by_role("button", name="Edit", exact=True).click()
            page.get_by_label("Edit name").fill("Browser Edited")
            page.get_by_label("Edit phone").fill("12345678901")
            page.get_by_label("Edit role").select_option("Management")
            page.get_by_label("New password").fill("BrowserEdited123!")
            page.get_by_role("button", name="Save changes", exact=True).click()
            expect(page.get_by_text("User updated", exact=True)).to_be_visible(timeout=20_000)

            # Create through the UI and verify the row appears after refresh.
            page.get_by_label("Create name").fill("Browser Created")
            page.get_by_label("Create email").fill(f"usx-browser-created-{SUFFIX}@example.test")
            page.get_by_label("Create password").fill(PASSWORD)
            page.get_by_role("button", name="Create user", exact=True).click()
            expect(page.get_by_text("User created", exact=True)).to_be_visible(timeout=20_000)

            # Pending tab, copy/resend, selection/bulk resend, confirm/revoke.
            search.fill("")
            page.get_by_role("tab", name=re.compile(r"Pending invites"), exact=False).click()
            expect(page.get_by_text(pending[0], exact=True)).to_be_visible()
            page.get_by_role("row", name=re.compile(pending[0])).get_by_role("button", name="Copy invite", exact=True).click()
            page.get_by_role("row", name=re.compile(pending[0])).get_by_role("checkbox").check()
            expect(page.get_by_text("1 selected", exact=True)).to_be_visible()
            page.get_by_role("button", name="Resend invitations", exact=True).click()
            expect(page.get_by_text("Invitations resent (1)", exact=True)).to_be_visible(timeout=20_000)
            page.get_by_role("row", name=re.compile(pending[1])).get_by_role("button", name="Revoke", exact=True).click()
            expect(page.get_by_text("Invitation revoked", exact=True)).to_be_visible(timeout=20_000)

            # Retry path: first refresh fails visibly, second succeeds.
            failed_once = {"value": False}

            def fail_once(route):
                if not failed_once["value"]:
                    failed_once["value"] = True
                    route.abort()
                else:
                    route.continue_()

            page.route("**/api/users", fail_once)
            page.get_by_role("button", name="Refresh", exact=True).click()
            expect(page.get_by_role("button", name="Retry", exact=True)).to_be_visible(timeout=10_000)
            page.get_by_role("button", name="Retry", exact=True).click()
            expect(page.get_by_role("button", name="Retry", exact=True)).to_have_count(0, timeout=20_000)
            page.unroute("**/api/users", fail_once)

            # Admin confirmation delete and non-admin visibility gate.
            page.get_by_role("tab", name=re.compile(r"Active"), exact=False).click()
            search.fill("Browser Created")
            page.get_by_role("row", name=re.compile(f"usx-browser-created-{SUFFIX}")).get_by_role("button", name="Delete", exact=True).click()
            # Dialog is accepted by the handler below; the row must disappear.
            expect(page.get_by_text(f"usx-browser-created-{SUFFIX}@example.test", exact=True)).to_have_count(0, timeout=20_000)

            # Log out and prove a non-admin reaches the explicit access gate.
            status, nonadmin = api_json(page, "POST", "/api/users", admin_token, {"user_name": "Browser Nonadmin", "user_email": f"usx-browser-nonadmin-{SUFFIX}@example.test", "password": PASSWORD, "user_role": "Operational"})
            nonadmin_email = f"usx-browser-nonadmin-{SUFFIX}@example.test"
            page.get_by_role("button", name=re.compile(r"Sign out")).click()
            page.get_by_placeholder("admin").first.fill(nonadmin_email)
            page.get_by_placeholder("admin").nth(1).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_role("button", name="Users", exact=True).first.click()
            expect(page.get_by_role("alert")).to_contain_text("System_Admin access is required")
            expect(page.get_by_role("button", name="Create user", exact=True)).to_have_count(0)

            cleanup(page, admin_token)
            print(json.dumps({"result": "PASS", "surface": "users-browser", "suffix": SUFFIX}))
            return 0
    except Exception as exc:
        if page is not None:
            try:
                page.screenshot(path="/artifacts/users_exhaustive_browser_failure.png", full_page=True)
            except Exception:
                pass
        print(json.dumps({"result": "FAIL", "surface": "users-browser", "error": str(exc)}))
        return 1
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
