#!/usr/bin/env python3
"""Disposable Playwright browser flow for the strict acceptance harness."""
from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright


def main() -> int:
    link = os.environ["PLATFORMOPS_ACCEPTANCE_INVITE_URL"]
    full_name = os.environ["PLATFORMOPS_ACCEPTANCE_FULL_NAME"]
    password = os.environ["PLATFORMOPS_ACCEPTANCE_PASSWORD"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(link, wait_until="networkidle", timeout=30_000)
        if page.get_by_role("heading", name="Accept invitation").count() != 1:
            raise RuntimeError("browser did not render invite route")
        page.get_by_placeholder("Full name").fill(full_name)
        page.get_by_placeholder("Password", exact=True).fill(password)
        page.get_by_placeholder("Confirm password", exact=True).fill(password)
        page.get_by_role("checkbox").check()
        page.get_by_role("button", name="Accept invitation & sign in").click()
        page.wait_for_timeout(1000)
        if "/invite/" in page.url:
            raise RuntimeError(f"browser did not clear one-time invite URL: {page.url}")
        if not page.evaluate("Object.keys(localStorage).some((key) => key.toLowerCase().includes('token'))"):
            raise RuntimeError("browser did not establish a session")
        result = {"final_path": page.url.split("#", 1)[-1], "session_established": True}
        browser.close()
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
