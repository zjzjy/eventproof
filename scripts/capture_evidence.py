"""Capture reproducible UI evidence from the real core demo page."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

from make_demo_video import WEB_DIR, static_server


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "screenshots"
VIEWPORT = {"width": 1440, "height": 1000}
STATE_KEY = "eventproof.demo.v2"


def state_script(step: int, *, hangyun: bool = False) -> str:
    state = {
        "followed": True,
        "step": step,
        "hangyun": hangyun,
        "eventFollowed": True,
    }
    return f"localStorage.setItem({json.dumps(STATE_KEY)}, {json.dumps(json.dumps(state))});"


def settle(page) -> None:
    page.locator("body").wait_for()
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(350)


def shot(page, filename: str, *, selector: str | None = None, full_page: bool = False) -> Path:
    if selector:
        locator = page.locator(selector).first
        locator.wait_for(state="visible")
        locator.evaluate(
            "(el) => el.scrollIntoView({behavior: 'instant', block: 'center'})"
        )
        page.wait_for_timeout(250)
    path = OUTPUT / filename
    page.screenshot(path=str(path), full_page=full_page)
    return path


def capture_normal(browser, base_url: str) -> list[Path]:
    captured: list[Path] = []

    context = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
    page = context.new_page()
    page.goto(f"{base_url}/core-simple.html?evidence=onboarding", wait_until="networkidle")
    settle(page)
    captured.append(shot(page, "01-onboarding.png"))

    page.locator("#onboardInput").fill("002792")
    page.locator("#onboardFollow").click()
    page.locator("#processing").wait_for(state="visible")
    page.wait_for_timeout(120)
    captured.append(shot(page, "02-follow-processing.png"))
    context.close()

    cases = [
        (0, "03-v1-fact-opinion.png", "#stage-fact"),
        (1, "04-v2-rumor.png", "#stage-rumor"),
        (2, "05-v3-denial-p0.png", "#denial-notification"),
        (3, "06-v4-market-time.png", "#time-row"),
        (4, "07-v5-new-stage.png", "#stage-signing"),
    ]
    for step, filename, selector in cases:
        context = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
        context.add_init_script(state_script(step))
        page = context.new_page()
        page.goto(f"{base_url}/core-simple.html?evidence=step-{step}", wait_until="networkidle")
        settle(page)
        captured.append(shot(page, filename, selector=selector))
        context.close()

    context = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
    context.add_init_script(state_script(4))
    page = context.new_page()
    page.goto(f"{base_url}/core-simple.html?evidence=trace", wait_until="networkidle")
    settle(page)
    captured.append(shot(page, "08-source-traceability.png", selector="#stage-fact .quote"))
    context.close()

    context = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
    context.add_init_script(state_script(4, hangyun=True))
    page = context.new_page()
    page.goto(f"{base_url}/core-simple.html?evidence=second-event", wait_until="networkidle")
    settle(page)
    page.locator("#openHangyun").click()
    page.locator("#hangyunOverlay").wait_for(state="visible")
    settle(page)
    captured.append(shot(page, "09-second-event.png"))
    context.close()
    return captured


def capture_scenarios(browser, base_url: str) -> list[Path]:
    captured: list[Path] = []
    for scenario, filename in (
        ("correction", "10-correction-p0.png"),
        ("expiry", "11-expiry-not-false.png"),
        ("conflict", "12-official-conflict.png"),
    ):
        context = browser.new_context(viewport=VIEWPORT, locale="zh-CN")
        page = context.new_page()
        page.goto(
            f"{base_url}/core-simple.html?scenario={scenario}&static=1",
            wait_until="networkidle",
        )
        scenario_script = page.locator("#legacy-scenario").text_content()
        if not scenario_script:
            raise RuntimeError("Missing embedded scenario renderer")
        page.add_script_tag(content=scenario_script)
        page.locator(".scenario-banner").wait_for(state="visible")
        page.evaluate("document.getElementById('onboarding').classList.add('hidden')")
        page.evaluate("window.scrollTo(0, 0)")
        settle(page)
        captured.append(shot(page, filename, full_page=True))
        context.close()
    return captured


def make_contact_sheet(paths: list[Path]) -> Path:
    thumb_width, thumb_height = 480, 333
    columns = 3
    rows = (len(paths) + columns - 1) // columns
    canvas = Image.new("RGB", (thumb_width * columns, thumb_height * rows), "white")
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail((thumb_width, thumb_height))
        tile = Image.new("RGB", (thumb_width, thumb_height), "white")
        tile.paste(
            image,
            ((thumb_width - image.width) // 2, (thumb_height - image.height) // 2),
        )
        x = (index % columns) * thumb_width
        y = (index // columns) * thumb_height
        canvas.paste(tile, (x, y))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((x + 6, y + 6, x + 48, y + 34), fill="white")
        draw.text((x + 10, y + 8), path.stem[:2], fill="black", font=font)

    path = OUTPUT / "contact-sheet.png"
    canvas.save(path)
    return path


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT.glob("*.png"):
        old.unlink()

    with static_server(WEB_DIR) as base_url:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                channel="chrome",
                headless=True,
                args=["--force-device-scale-factor=1", "--hide-scrollbars"],
            )
            captured = capture_normal(browser, base_url)
            captured.extend(capture_scenarios(browser, base_url))
            browser.close()

    captured.append(make_contact_sheet(captured))
    for path in captured:
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size} bytes")
    print(f"captured {len(captured)} screenshots")


if __name__ == "__main__":
    main()
