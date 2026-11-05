import time

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:7860/"
logs = []


def wait_log(page, timeout=300, must_change_from=None):
    log = page.get_by_label("บันทึกการทำงาน")
    deadline = time.time() + timeout
    text = ""
    while time.time() < deadline:
        try:
            text = log.input_value()
        except Exception:
            text = log.inner_text()
        if "ใช้เวลา" in text and text != must_change_from:
            return text
        page.wait_for_timeout(1000)
    return text


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1100})
    page.on(
        "console",
        lambda m: logs.append(f"console[{m.type}] {m.location.get('url','')}:{m.location.get('lineNumber','')} {m.text}"),
    )
    page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))

    page.goto(URL, wait_until="networkidle", timeout=180000)
    page.wait_for_selector("text=ฟื้นฟูภาพ", timeout=180000)
    page.wait_for_timeout(1500)

    # --- 1) กดรันโดยยังไม่เลือกภาพ
    page.get_by_role("button", name="ฟื้นฟูภาพ").click()
    page.wait_for_timeout(1500)
    print("error toast shown:", "กรุณาเลือกภาพก่อนกดฟื้นฟู" in page.inner_text("body"))

    # --- 2) อัปโหลด TIFF 16-bit: ตัวอย่างภาพต้องแสดงได้ (ไม่ใช่แถบขาด)
    page.set_input_files("input[type=file]", "_testing/negative16.tif")
    page.wait_for_timeout(4000)
    preview_state = page.evaluate(
        """() => [...document.querySelectorAll('img')]
            .map(i => ({w: i.naturalWidth, h: i.naturalHeight, src: i.src.slice(0, 30)}))
            .filter(i => i.w > 200)"""
    )
    print("preview images:", preview_state[:3])

    # --- 3) เนกาทีฟสี, ปิดฟื้นฟูใบหน้า, x4
    page.get_by_text("เนกาทีฟสี (C-41)", exact=True).first.click()
    page.wait_for_timeout(1200)
    page.get_by_label("ฟื้นฟูใบหน้า").uncheck()
    page.get_by_text("x4", exact=True).first.click()
    page.get_by_role("button", name="ฟื้นฟูภาพ").click()
    text1 = wait_log(page)
    print("RUN1 has face step (should be False):", "ฟื้นฟูใบหน้า" in text1)
    print("RUN1 LOG>>>\n" + text1)
    page.screenshot(path="_testing/ui_negative.png", full_page=True)

    # --- 4) เปลี่ยนโหมดแล้วติ๊กฟื้นฟูใบหน้ากลับ (ค่าเริ่มต้นของโหมดต้องตามมา)
    page.get_by_text("เนกาทีฟขาวดำ", exact=True).first.click()
    page.wait_for_timeout(1200)
    print("face re-enabled by preset:", page.get_by_label("ฟื้นฟูใบหน้า").is_checked())

    # --- 5) รันซ้ำ
    page.get_by_text("เนกาทีฟสี (C-41)", exact=True).first.click()
    page.wait_for_timeout(800)
    page.get_by_role("button", name="ฟื้นฟูภาพ").click()
    text2 = wait_log(page, must_change_from=text1)
    print("RUN2 changed:", text2 != text1)
    print("RUN2 has face step (should be True):", "ฟื้นฟูใบหน้า" in text2)

    # --- 6) หน้าจอมือถือ
    page.set_viewport_size({"width": 420, "height": 900})
    page.wait_for_timeout(1500)
    page.screenshot(path="_testing/ui_mobile.png", full_page=False)
    print(
        "mobile overflow:",
        page.evaluate("() => ({scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth})"),
    )

    print("CONSOLE (%d):" % len(logs))
    for line in logs[:30]:
        print(" ", line)
    browser.close()
