"""Opt-in Windows browser and live Ollama smoke test, using temporary fictional data."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from playwright.sync_api import expect, sync_playwright
from trace_mem.workspace import server


def main():
    with TemporaryDirectory() as tmp, server(Path(tmp)/"memory.json",0) as app:
        Thread(target=app.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as runner:
                browser = runner.chromium.launch(channel="msedge")
                page = browser.new_page()
                page.set_default_timeout(120000)
                page.goto(f"http://127.0.0.1:{app.server_port}")
                expect(page.locator("#mode")).to_have_value("ollama")
                page.get_by_text("Generation settings",exact=True).click()
                page.locator("#output").fill("48")
                page.locator("#question").fill("I live in fictional Cedar Town.")
                page.locator("#send").click()
                proposal = page.get_by_role("button",name="Review assert")
                proposal.wait_for()
                print(page.locator("#models").input_value(),page.locator("#usage").inner_text(),flush=True)
                page.on("dialog",lambda dialog: dialog.accept(dialog.default_value))
                proposal.click()
                expect(page.locator("#count")).to_have_text("1")
                page.locator("#new").click()
                page.locator("#question").fill("Where is my home?")
                page.locator("#send").click()
                expect(page.locator("#evidence")).to_contain_text("Cedar Town",timeout=120000)
                print(page.locator("#evidence").inner_text(),page.locator("#usage").inner_text(),flush=True)
                page.reload()
                expect(page.locator("#chats option")).to_have_count(2)
                page.get_by_role("button",name="Forget",exact=True).click()
                expect(page.locator("#count")).to_have_text("0")
                assert app.store.rows == []
                for mode in ("standard","rag","trace"):
                    page.locator("#strategy").select_option(mode)
                    expect(page.locator("#strategy")).to_have_value(mode)
                page.locator("#pilot summary").click()
                expect(page.locator("#pilotReport table tr")).to_have_count(4)
                browser.close()
        finally:
            app.shutdown()


if __name__ == "__main__":
    main()
