import json
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7860/"
logs = []


def dump(name, data):
    with open(f"_testing/{name}.json", "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1100})
    page.on("console", lambda m: logs.append(f"console[{m.type}]: {m.text}"))
    page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))

    page.goto(URL, wait_until="networkidle", timeout=180000)
    page.wait_for_selector("text=ฟื้นฟูภาพ", timeout=180000)
    page.wait_for_timeout(1500)
    page.screenshot(path="_testing/ui_initial.png", full_page=True)
    print("STEP initial ok")

    # 1) เปลี่ยนโหมด -> ค่า slider ต้องเปลี่ยนตาม preset
    page.get_by_text("ภาพพิมพ์ขาวดำ", exact=True).first.click()
    page.wait_for_timeout(1200)
    sliders = page.eval_on_selector_all(
        "input[type=range]",
        "els => els.map(e => e.value)",
    )
    print("sliders after bw_print:", sliders)

    # 2) อัปโหลดภาพจริง
    page.set_input_files("input[type=file]", "_testing/faded_print.jpg")
    page.wait_for_timeout(3000)
    page.get_by_text("ภาพพิมพ์สีที่ซีด", exact=True).first.click()
    page.wait_for_timeout(1200)
    page.screenshot(path="_testing/ui_ready.png", full_page=True)
    print("STEP upload ok")

    # 3) กดรัน
    page.get_by_role("button", name="ฟื้นฟูภาพ").click()
    log = page.get_by_label("บันทึกการทำงาน")
    text = ""
    deadline = time.time() + 240
    while time.time() < deadline:
        try:
            text = log.input_value()
        except Exception:
            text = log.inner_text()
        if "ใช้เวลา" in text or "ผิดพลาด" in text:
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2500)
    page.screenshot(path="_testing/ui_result.png", full_page=True)
    print("LOG>>>\n" + text)

    # 4) ตรวจว่าภาพผลขึ้นในสไลเดอร์/gallery จริง
    info = page.evaluate(
        """() => ({
            imgs: document.querySelectorAll('img').length,
            sliders: document.querySelectorAll('.image-slider, [data-testid="image-slider"]').length,
            gallery: document.querySelectorAll('.grid-wrap, .gallery').length,
            errorToasts: [...document.querySelectorAll('.toast-body, .error')].map(e => e.innerText).slice(0,5),
        })"""
    )
    print("DOM:", info)
    print("CONSOLE (%d):" % len(logs))
    for line in logs[:40]:
        print(" ", line)
    browser.close()
