"""Generate the EventProof demo video end to end.

The pipeline is:

1. Generate one Chinese female-voice clip per narration scene.
2. Record the real core-simple page with Chrome and a visible pointer dot.
3. Concatenate narration with scene-aligned gaps.
4. Mux WebM + WAV into a browser-friendly H.264/AAC MP4.

Examples:

    python scripts/make_demo_video.py
    python scripts/make_demo_video.py --skip-tts
    python scripts/make_demo_video.py --voice zh-CN-XiaoxiaoNeural
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from mutagen import File as MutagenFile


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "video"
WEB_DIR = ROOT / "apps" / "web" / "dist"
NARRATION_PATH = VIDEO_DIR / "narration.json"
RAW_DIR = VIDEO_DIR / "raw"
TTS_DIR = VIDEO_DIR / "narration"
AUDIO_DIR = VIDEO_DIR / "audio"
OUTPUT_DIR = VIDEO_DIR / "output"
OUTPUT_PATH = OUTPUT_DIR / "eventproof-demo.mp4"
MANIFEST_PATH = VIDEO_DIR / "manifest.json"

LEAD_IN_SECONDS = 0.55
SCENE_GAP_SECONDS = 0.45
FINAL_HOLD_SECONDS = 1.2
VIEWPORT = {"width": 1440, "height": 900}

POINTER_SCRIPT = r"""
(() => {
  const install = () => {
    if (!document.body || document.getElementById("__eventproof_pointer")) return;
    const style = document.createElement("style");
    style.textContent = `
      html { scrollbar-width: none !important; }
      html::-webkit-scrollbar, body::-webkit-scrollbar { display: none !important; }
      #__eventproof_pointer {
        position: fixed; left: -40px; top: -40px; width: 13px; height: 13px;
        border: 3px solid rgba(255,255,255,.96); border-radius: 50%;
        background: #111; box-shadow: 0 1px 5px rgba(0,0,0,.35);
        pointer-events: none; z-index: 2147483647;
        transform: translate(-50%, -50%) scale(1);
        transition: transform 90ms ease, opacity 120ms ease;
      }
      #__eventproof_click {
        position: fixed; left: -50px; top: -50px; width: 30px; height: 30px;
        border: 2px solid rgba(20,20,20,.55); border-radius: 50%;
        pointer-events: none; z-index: 2147483646; opacity: 0;
        transform: translate(-50%, -50%) scale(.35);
      }
      #__eventproof_click.pulse { animation: __ep_pulse 380ms ease-out; }
      @keyframes __ep_pulse {
        0% { opacity: .8; transform: translate(-50%, -50%) scale(.35); }
        100% { opacity: 0; transform: translate(-50%, -50%) scale(1.25); }
      }
    `;
    document.documentElement.appendChild(style);
    const dot = document.createElement("div");
    dot.id = "__eventproof_pointer";
    const ring = document.createElement("div");
    ring.id = "__eventproof_click";
    document.body.append(dot, ring);
    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    const move = (nextX, nextY) => {
      x = nextX; y = nextY;
      dot.style.left = `${x}px`;
      dot.style.top = `${y}px`;
    };
    move(x, y);
    window.addEventListener("mousemove", event => move(event.clientX, event.clientY), true);
    window.addEventListener("mousedown", event => {
      move(event.clientX, event.clientY);
      dot.style.transform = "translate(-50%, -50%) scale(.78)";
      ring.style.left = `${event.clientX}px`;
      ring.style.top = `${event.clientY}px`;
      ring.classList.remove("pulse");
      void ring.offsetWidth;
      ring.classList.add("pulse");
    }, true);
    window.addEventListener("mouseup", event => {
      move(event.clientX, event.clientY);
      dot.style.transform = "translate(-50%, -50%) scale(1)";
    }, true);
    window.__eventproofMovePointer = move;
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install, { once: true });
  } else {
    install();
  }
})();
"""


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        pass


@contextmanager
def static_server(directory: Path):
    handler = lambda *args, **kwargs: QuietHandler(  # noqa: E731
        *args, directory=str(directory), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def ffmpeg_exe() -> str:
    from imageio_ffmpeg import get_ffmpeg_exe

    return get_ffmpeg_exe()


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def media_duration(path: Path) -> float:
    audio = MutagenFile(path)
    if audio is not None and audio.info is not None:
        return float(audio.info.length)
    text = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    ).stderr
    match = re.search(r"Duration:\s+(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise RuntimeError(f"Cannot read media duration: {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def file_hash(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sapi_fallback(text: str, output: Path) -> None:
    """Use a local female Chinese SAPI voice when online Edge TTS is unavailable."""
    text_path = output.with_suffix(".txt")
    text_path.write_text(text, encoding="utf-8")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SelectVoice('Microsoft Huihui Desktop'); "
        f"$s.SetOutputToWaveFile('{output.as_posix()}'); "
        f"$s.Speak((Get-Content -LiteralPath '{text_path.as_posix()}' -Raw -Encoding UTF8)); "
        "$s.Dispose()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
        capture_output=True,
    )
    text_path.unlink(missing_ok=True)


def generate_one_tts(
    text: str,
    output_stem: Path,
    voice: str,
    rate: str,
    volume: str,
    *,
    force: bool,
    cache_key: str,
    cache: dict[str, dict[str, object]],
) -> Path:
    key = str(output_stem.relative_to(VIDEO_DIR))
    cached = cache.get(key, {})
    extension = str(cached.get("extension", ".mp3"))
    cached_path = output_stem.with_suffix(extension)
    if (
        not force
        and cached.get("cache_key") == cache_key
        and cached_path.exists()
        and cached_path.stat().st_size > 1024
    ):
        print(f"TTS cache: {cached_path.name}")
        return cached_path

    cached_path.unlink(missing_ok=True)
    output_stem.with_suffix(".wav").unlink(missing_ok=True)
    output_stem.with_suffix(".mp3").unlink(missing_ok=True)
    try:
        import edge_tts

        async def save() -> None:
            await edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=rate,
                volume=volume,
            ).save(str(output_stem.with_suffix(".mp3")))

        asyncio.run(save())
        output = output_stem.with_suffix(".mp3")
        engine = "edge-tts"
    except Exception as exc:
        print(f"Edge TTS failed ({exc}); falling back to Microsoft Huihui.")
        output = output_stem.with_suffix(".wav")
        sapi_fallback(text, output)
        engine = "Windows SAPI"

    if media_duration(output) < 0.5:
        raise RuntimeError(f"Generated narration is too short: {output}")
    cache[key] = {
        "cache_key": cache_key,
        "extension": output.suffix,
        "engine": engine,
        "voice": voice if engine == "edge-tts" else "Microsoft Huihui Desktop",
        "duration": round(media_duration(output), 3),
    }
    return output


def generate_narration(
    config: dict[str, object],
    voice: str,
    rate: str,
    volume: str,
    *,
    force: bool,
) -> list[dict[str, object]]:
    scenes = config["scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("narration.json must contain a non-empty scenes list")
    TTS_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = TTS_DIR / "manifest.json"
    cache: dict[str, dict[str, object]] = {}
    if manifest_path.exists():
        cache = json.loads(manifest_path.read_text(encoding="utf-8"))

    result: list[dict[str, object]] = []
    for index, scene in enumerate(scenes, start=1):
        scene = dict(scene)
        display_text = str(scene["text"]).strip()
        speech_text = str(scene.get("speech_text") or display_text).strip()
        stem = TTS_DIR / f"{index:02d}-{scene['id']}"
        cache_key = file_hash(speech_text, voice, rate, volume)
        audio_path = generate_one_tts(
            speech_text,
            stem,
            voice,
            rate,
            volume,
            force=force,
            cache_key=cache_key,
            cache=cache,
        )
        scene.update(
            {
                "audio_path": str(audio_path.relative_to(VIDEO_DIR)),
                "tts_seconds": media_duration(audio_path),
                "engine": cache[str(stem.relative_to(VIDEO_DIR))]["engine"],
            }
        )
        result.append(scene)

    manifest_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def build_audio_track(scenes: list[dict[str, object]]) -> tuple[Path, list[dict[str, float]]]:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_exe()
    silence = AUDIO_DIR / "silence.wav"
    run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            f"{LEAD_IN_SECONDS:.3f}",
            "-c:a",
            "pcm_s16le",
            str(silence),
        ]
    )

    concat_entries: list[Path] = [silence]
    timings: list[dict[str, float]] = []
    cursor = LEAD_IN_SECONDS
    for index, scene in enumerate(scenes, start=1):
        source = VIDEO_DIR / str(scene["audio_path"])
        normalized = AUDIO_DIR / f"{index:02d}.wav"
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-ar",
                "48000",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(normalized),
            ]
        )
        duration = media_duration(normalized)
        gap = AUDIO_DIR / "gap.wav"
        if not gap.exists():
            run(
                [
                    ffmpeg,
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=r=48000:cl=stereo",
                    "-t",
                    f"{SCENE_GAP_SECONDS:.3f}",
                    "-c:a",
                    "pcm_s16le",
                    str(gap),
                ]
            )
        scene["audio_start"] = round(cursor, 3)
        scene["audio_end"] = round(cursor + duration, 3)
        scene["scene_seconds"] = round(duration + SCENE_GAP_SECONDS, 3)
        timings.append(
            {
                "start": scene["audio_start"],
                "end": scene["audio_end"],
                "scene_start": scene["audio_start"] - (LEAD_IN_SECONDS if index == 1 else 0),
                "scene_end": scene["audio_end"]
                + SCENE_GAP_SECONDS
                - (LEAD_IN_SECONDS if index == 1 else 0),
            }
        )
        cursor += duration + SCENE_GAP_SECONDS
        concat_entries.extend([normalized, gap])

    concat_file = AUDIO_DIR / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.as_posix()}'\n" for path in concat_entries),
        encoding="utf-8",
    )
    narration = AUDIO_DIR / "narration.wav"
    run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(narration),
        ]
    )
    return narration, timings


def first_scene_duration(scene: dict[str, object]) -> float:
    return LEAD_IN_SECONDS + float(scene["tts_seconds"]) + SCENE_GAP_SECONDS


def other_scene_duration(scene: dict[str, object]) -> float:
    return float(scene["tts_seconds"]) + SCENE_GAP_SECONDS


class Recording:
    def __init__(self, page, width: int = 1440, height: int = 900):
        self.page = page
        self.width = width
        self.height = height
        self.scene_started = 0.0

    def wait(self, seconds: float) -> None:
        if seconds > 0:
            self.page.wait_for_timeout(round(seconds * 1000))

    def begin_scene(self) -> None:
        self.scene_started = time.monotonic()

    def elapsed(self) -> float:
        return time.monotonic() - self.scene_started

    def finish_scene(self, duration: float) -> None:
        remain = duration - self.elapsed()
        if remain < -0.15:
            print(f"Warning: scene overran narration by {-remain:.2f}s")
        self.wait(max(0.0, remain))

    def pointer_locator(
        self,
        locator,
        *,
        offset: tuple[float, float] = (0, 0),
    ) -> None:
        locator.wait_for(state="visible")
        box = locator.bounding_box()
        if not box:
            return
        x = box["x"] + box["width"] / 2 + offset[0]
        y = box["y"] + box["height"] / 2 + offset[1]
        x = min(max(4, x), self.width - 4)
        y = min(max(4, y), self.height - 4)
        self.page.mouse.move(x, y, steps=14)

    def pointer(self, selector: str, *, offset: tuple[float, float] = (0, 0)) -> None:
        self.pointer_locator(self.page.locator(selector).first, offset=offset)

    def click(self, selector: str) -> None:
        self.pointer(selector)
        self.wait(0.12)
        self.page.mouse.down()
        self.wait(0.1)
        self.page.mouse.up()

    def scroll_to(self, selector: str, *, block: str = "center", settle: float = 0.75) -> None:
        self.page.locator(selector).first.evaluate(
            "(el, block) => el.scrollIntoView({behavior: 'smooth', block})",
            block,
        )
        self.wait(settle)

    def type_into(self, selector: str, text: str) -> None:
        self.click(selector)
        self.wait(0.15)
        self.page.keyboard.type(text, delay=80)


def record_video(
    scenes: list[dict[str, object]],
    base_url: str,
) -> tuple[Path, list[dict[str, float]]]:
    from playwright.sync_api import sync_playwright

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for old in RAW_DIR.glob("*.webm"):
        old.unlink()

    scene_actions: list[Callable[[Recording, float], None]] = [
        action_intro,
        action_follow,
        action_fact,
        action_rumor,
        action_denial,
        action_market,
        action_new_stage,
        action_multi_event,
        action_traceability,
    ]
    if len(scene_actions) != len(scenes):
        raise RuntimeError("Scene actions do not match narration scenes")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--force-device-scale-factor=1", "--hide-scrollbars"],
        )
        context = browser.new_context(
            viewport=VIEWPORT,
            record_video_dir=str(RAW_DIR),
            record_video_size=VIEWPORT,
            device_scale_factor=1,
        )
        context.add_init_script(POINTER_SCRIPT)
        page = context.new_page()
        page.set_default_timeout(5_000)
        page.goto(
            f"{base_url}/core-simple.html?video=20261020",
            wait_until="networkidle",
        )
        page.mouse.move(VIEWPORT["width"] / 2, VIEWPORT["height"] / 2, steps=8)
        recorder = Recording(page, VIEWPORT["width"], VIEWPORT["height"])
        actual: list[dict[str, float]] = []
        recording_start = time.monotonic()
        for index, scene in enumerate(scenes):
            duration = first_scene_duration(scene) if index == 0 else other_scene_duration(scene)
            scene_actual_start = time.monotonic() - recording_start
            recorder.begin_scene()
            scene_actions[index](recorder, duration)
            recorder.finish_scene(duration)
            actual.append(
                {
                    "start": scene_actual_start,
                    "end": time.monotonic() - recording_start,
                }
            )

        recorder.wait(FINAL_HOLD_SECONDS)
        video = page.video
        if video is None:
            raise RuntimeError("Playwright did not produce a video")
        video_path = Path(video.path())
        context.close()
        browser.close()

    if not video_path.exists():
        raise RuntimeError(f"Video output not found: {video_path}")
    return video_path, actual


def action_intro(rec: Recording, duration: float) -> None:
    rec.pointer(".onboarding-box h1")
    rec.wait(1.4)
    rec.pointer("#onboardInput")
    rec.wait(0.8)
    rec.finish_scene(duration)


def action_follow(rec: Recording, duration: float) -> None:
    rec.type_into("#onboardInput", "002792")
    rec.wait(0.4)
    rec.click("#onboardFollow")
    rec.page.locator("#processing").wait_for(state="visible")
    rec.pointer("#processing")
    rec.wait(1.35)
    rec.pointer("#conclusion-line")
    rec.finish_scene(duration)


def action_fact(rec: Recording, duration: float) -> None:
    rec.pointer("#conclusion-line")
    rec.wait(1.2)
    rec.scroll_to("#stage-fact")
    rec.pointer("#stage-fact .quote")
    rec.wait(1.4)
    rec.pointer_locator(rec.page.locator("#stage-fact .claim-extra").nth(0))
    rec.wait(1.2)
    rec.pointer_locator(rec.page.locator("#stage-fact .claim-extra").nth(1))
    rec.finish_scene(duration)


def action_rumor(rec: Recording, duration: float) -> None:
    rec.scroll_to("#syncButton", block="center")
    rec.pointer("#syncButton")
    rec.wait(0.4)
    rec.click("#syncButton")
    rec.wait(0.95)
    rec.scroll_to("#stage-rumor")
    rec.pointer("#stage-rumor .quote")
    rec.wait(1.2)
    rec.pointer("#stage-rumor .note")
    rec.finish_scene(duration)


def action_denial(rec: Recording, duration: float) -> None:
    rec.scroll_to("#syncButton", block="center")
    rec.click("#syncButton")
    rec.wait(0.95)
    rec.scroll_to("#notificationButton", block="start", settle=0.5)
    rec.pointer("#notificationButton")
    rec.wait(0.4)
    rec.click("#notificationButton")
    rec.wait(1.0)
    rec.pointer("#stage-denial .quote")
    rec.wait(1.2)
    rec.pointer("#denial-notification")
    rec.finish_scene(duration)


def action_market(rec: Recording, duration: float) -> None:
    rec.scroll_to("#syncButton", block="center")
    rec.click("#syncButton")
    rec.wait(0.95)
    rec.scroll_to("#time-row")
    for selector in ("#time-row > div:nth-child(1)", "#time-row > div:nth-child(2)",
                     "#time-row > div:nth-child(3)", "#time-row > div:nth-child(4)"):
        rec.pointer(selector)
        rec.wait(0.45)
    rec.scroll_to("#stage-market")
    rec.pointer("#stage-market .quote")
    rec.pointer("#market-notification")
    rec.finish_scene(duration)


def action_new_stage(rec: Recording, duration: float) -> None:
    rec.scroll_to("#syncButton", block="center")
    rec.click("#syncButton")
    rec.wait(0.95)
    rec.scroll_to("#notificationButton", block="start", settle=0.5)
    rec.click("#notificationButton")
    rec.wait(0.95)
    rec.pointer("#stage-signing .quote")
    rec.wait(1.2)
    rec.pointer("#stage-signing .why")
    rec.finish_scene(duration)


def action_multi_event(rec: Recording, duration: float) -> None:
    rec.scroll_to(".watch-drawer", block="center")
    rec.click("#toggleAddWatch")
    rec.wait(0.25)
    rec.type_into("#watchInput", "300209")
    rec.click("#watchForm button[type='submit']")
    rec.wait(0.55)
    rec.pointer("#watchMessage")
    rec.wait(0.45)
    rec.click("#openHangyun")
    rec.page.locator("#hangyunOverlay").wait_for(state="visible")
    rec.pointer("#hangyunOverlay .modal-conclusion")
    rec.wait(0.8)
    rec.pointer_locator(rec.page.locator("#hangyunOverlay .mini-stage").nth(1))
    rec.finish_scene(duration)


def action_traceability(rec: Recording, duration: float) -> None:
    rec.click("#closeHangyun")
    rec.wait(0.35)
    rec.scroll_to("#stage-fact .quote")
    rec.pointer("#stage-fact .quote a")
    rec.wait(0.9)
    rec.scroll_to(".open-questions")
    rec.pointer(".open-questions .question-grid")
    rec.wait(0.8)
    rec.scroll_to(".method")
    rec.pointer(".method summary")
    rec.wait(0.55)
    rec.click(".method summary")
    rec.wait(0.65)
    rec.pointer(".state-rule:last-of-type")
    rec.finish_scene(duration)


def subtitle_chunks(text: str, max_chars: int = 34) -> list[str]:
    """Split narration into readable subtitle cues without changing words."""
    clauses = [
        clause.strip()
        for clause in re.findall(r".+?(?:[，、；：。！？]|$)", text)
        if clause.strip()
    ]
    merged: list[str] = []
    for clause in clauses:
        while len(clause) > max_chars:
            window = clause[: max_chars + 1]
            cut = max(
                window.rfind("，"),
                window.rfind("、"),
                window.rfind("；"),
                window.rfind("："),
                window.rfind(" "),
            )
            cut = cut + 1 if cut >= 12 else max_chars
            merged.append(clause[:cut].strip())
            clause = clause[cut:].strip().lstrip("，、；：")
        if not clause:
            continue
        if merged and len(merged[-1]) + len(clause) <= max_chars:
            merged[-1] += clause
        else:
            merged.append(clause)
    return merged


def subtitle_cues(
    scenes: list[dict[str, object]],
    timings: list[dict[str, float]],
) -> list[dict[str, object]]:
    cues: list[dict[str, object]] = []
    for scene, timing in zip(scenes, timings):
        chunks = subtitle_chunks(str(scene["text"]))
        weights = [max(1, len(chunk)) for chunk in chunks]
        total_weight = sum(weights)
        cursor = float(timing["start"])
        available = float(timing["end"]) - cursor
        for chunk, weight in zip(chunks, weights):
            duration = available * weight / total_weight
            cues.append(
                {
                    "start": cursor,
                    "end": cursor + duration,
                    "text": chunk,
                }
            )
            cursor += duration
    return cues


def write_subtitles(
    scenes: list[dict[str, object]],
    timings: list[dict[str, float]],
) -> tuple[Path, Path]:
    def srt_stamp(seconds: float) -> str:
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3_600_000)
        minutes, milliseconds = divmod(milliseconds, 60_000)
        secs, milliseconds = divmod(milliseconds, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def ass_stamp(seconds: float) -> str:
        centiseconds = round(seconds * 100)
        hours, centiseconds = divmod(centiseconds, 360_000)
        minutes, centiseconds = divmod(centiseconds, 6_000)
        secs, centiseconds = divmod(centiseconds, 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    cues = subtitle_cues(scenes, timings)
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{srt_stamp(float(cue['start']))} --> "
            f"{srt_stamp(float(cue['end']))}\n{cue['text']}\n"
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    srt_path = OUTPUT_DIR / "eventproof-demo.srt"
    srt_path.write_text("\n".join(blocks), encoding="utf-8")

    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1440",
        "PlayResY: 900",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Microsoft YaHei,28,&H00FFFFFF,&H000000FF,"
        "&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,90,90,28,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text",
    ]
    for cue in cues:
        text = str(cue["text"]).replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        ass_lines.append(
            f"Dialogue: 0,{ass_stamp(float(cue['start']))},"
            f"{ass_stamp(float(cue['end']))},Default,,0,0,0,,{text}"
        )
    ass_path = OUTPUT_DIR / "eventproof-demo.ass"
    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    return srt_path, ass_path


def assemble(video_path: Path, audio_path: Path, subtitle_path: Path, output: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    subtitle_filter_path = subtitle_path.relative_to(ROOT).as_posix()
    run(
        [
            ffmpeg_exe(),
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "21",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-vf",
            f"ass={subtitle_filter_path}",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-ar",
            "48000",
            "-af",
            "volume=2.5dB",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output),
        ]
    )


def validate_duration(duration: float) -> None:
    if not 60 <= duration <= 180:
        raise RuntimeError(
            f"Video duration {duration:.1f}s is outside the required 60-180s range"
        )


def expected_scene_timings(scenes: list[dict[str, object]]) -> list[dict[str, float]]:
    timings: list[dict[str, float]] = []
    cursor = 0.0
    for index, scene in enumerate(scenes):
        duration = first_scene_duration(scene) if index == 0 else other_scene_duration(scene)
        timings.append({"start": cursor, "end": cursor + duration})
        cursor += duration
    return timings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", help="Override the Edge TTS voice")
    parser.add_argument("--rate", help="Override speech rate, e.g. +4%%")
    parser.add_argument("--volume", help="Override speech volume, e.g. +0%%")
    parser.add_argument("--skip-tts", action="store_true", help="Reuse cached narration")
    parser.add_argument("--force-tts", action="store_true", help="Regenerate all narration")
    parser.add_argument("--keep-raw", action="store_true", help="Keep intermediate WebM")
    parser.add_argument(
        "--reuse-raw",
        action="store_true",
        help="Reuse the newest WebM and only rebuild subtitles/manifest/MP4",
    )
    args = parser.parse_args()

    config = json.loads(NARRATION_PATH.read_text(encoding="utf-8"))
    voice = args.voice or str(config.get("voice", "zh-CN-XiaoxiaoNeural"))
    rate = args.rate or str(config.get("rate", "+4%"))
    volume = args.volume or str(config.get("volume", "+0%"))

    if not WEB_DIR.joinpath("core-simple.html").exists():
        raise FileNotFoundError(f"Missing core page: {WEB_DIR / 'core-simple.html'}")

    scenes = generate_narration(
        config,
        voice,
        rate,
        volume,
        force=args.force_tts and not args.skip_tts,
    )
    estimated_total = (
        LEAD_IN_SECONDS
        + sum(float(scene["tts_seconds"]) for scene in scenes)
        + SCENE_GAP_SECONDS * len(scenes)
        + FINAL_HOLD_SECONDS
    )
    print(f"Narration estimate: {estimated_total:.1f}s across {len(scenes)} scenes")

    audio_path, audio_timings = build_audio_track(scenes)
    if args.reuse_raw:
        raw_files = sorted(
            RAW_DIR.glob("*.webm"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not raw_files:
            raise FileNotFoundError("--reuse-raw requested, but video/raw has no WebM")
        video_path = raw_files[0]
        actual_timings = expected_scene_timings(scenes)
        print(f"Reusing raw recording: {video_path.name}")
    else:
        with static_server(WEB_DIR) as base_url:
            video_path, actual_timings = record_video(scenes, base_url)

    for scene, expected, actual in zip(scenes, audio_timings, actual_timings):
        print(
            f"{scene['id']:<12} narration={expected['end'] - expected['start']:.2f}s "
            f"scene={actual['end'] - actual['start']:.2f}s"
        )

    srt_path, ass_path = write_subtitles(scenes, audio_timings)
    assemble(video_path, audio_path, ass_path, OUTPUT_PATH)
    duration = media_duration(OUTPUT_PATH)
    validate_duration(duration)

    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "output": str(OUTPUT_PATH.relative_to(ROOT)),
        "file_size_bytes": OUTPUT_PATH.stat().st_size,
        "sha256": sha256_file(OUTPUT_PATH),
        "duration_seconds": round(duration, 3),
        "resolution": VIEWPORT,
        "voice": voice,
        "rate": rate,
        "pointer": "visible injected pointer dot",
        "subtitles": {
            "burned_in": True,
            "srt": str(srt_path.relative_to(ROOT)),
            "ass": str(ass_path.relative_to(ROOT)),
        },
        "scenes": [
            {
                **scene,
                "scene_start": round(timing["start"], 3),
                "scene_end": round(timing["end"], 3),
            }
            for scene, timing in zip(scenes, actual_timings)
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not args.keep_raw:
        for path in RAW_DIR.glob("*.webm"):
            path.unlink(missing_ok=True)

    print(f"Video: {OUTPUT_PATH}")
    print(f"Duration: {duration:.1f}s")
    print(f"Subtitles: {srt_path} + burned-in {ass_path}")
    print(f"Manifest: {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
