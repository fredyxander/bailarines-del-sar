"""Prueba de humo del visor en un navegador real (python tests/smoke_test.py).

Sirve web/ en un puerto local y, con Playwright:
  - página normal: aparece la introducción y no hay errores de JavaScript
  - modo demo: franja de aviso, capas cargadas, la barra se arrastra,
    cambio de vista y de polarización
  - ningún archivo propio del sitio devuelve 404
Variable opcional BROWSER_CHANNEL=msedge para usar Edge instalado.
"""

from __future__ import annotations

import functools
import http.server
import os
import re
import sys
import threading
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

WEB = Path(__file__).resolve().parents[1] / "web"


def serve() -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=str(WEB))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def main() -> None:
    srv, base = serve()
    js_errors: list[str] = []
    missing: list[str] = []
    with sync_playwright() as p:
        channel = os.environ.get("BROWSER_CHANNEL")
        browser = p.chromium.launch(**({"channel": channel} if channel else {}))
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        # layers/index.json puede no existir todavía (sin datos reales): es esperado.
        page.on("response", lambda r: missing.append(r.url)
                if r.url.startswith(base) and r.status >= 400 and not r.url.endswith("/layers/index.json") else None)

        # 1. Página normal (sin capas reales todavía, o con ellas)
        page.goto(base + "/", wait_until="load")
        page.wait_for_timeout(1000)
        has_real = page.locator("#site option").count() > 0
        if not has_real:
            expect(page.locator("#empty")).to_be_visible()
        expect(page.locator("#demo-banner")).to_be_hidden()
        assert page.locator(".tl-seg").count() == 4, "la línea de tiempo debe tener 4 segmentos"
        print(f"ok  página normal ({'con capas reales' if has_real else 'introducción visible'})")
        if has_real:
            why_file = WEB / "layers" / page.locator("#site").input_value() / "why.json"
            if why_file.exists():
                expect(page.locator("#why")).to_be_visible()
                expect(page.locator("#why-lead")).not_to_be_empty()
                print("ok  'Why it changed' visible con datos reales")
            if (WEB / "layers" / page.locator("#site").input_value() / "summary.json").exists():
                page.click("#read-btn")
                expect(page.locator("#read")).to_be_visible()
                expect(page.locator("#read-text")).not_to_be_empty()
                expect(page.locator("#read-foot")).to_contain_text("AI")
                page.click("#read-close")
                expect(page.locator("#read")).to_be_hidden()
                print("ok  'Read the dance' se abre, muestra el texto y la etiqueta de IA")
            if (WEB / "layers" / page.locator("#site").input_value() / "types.json").exists():
                page.click("#mode-types")
                expect(page.locator("#mode-types")).to_have_attribute("aria-pressed", "true")
                expect(page.locator("#types-legend")).to_be_visible()
                assert page.locator("#types-items li").count() >= 1, "leyenda de tipos vacía"
                expect(page.locator("#types-note")).to_contain_text("not ground truth")
                expect(page.locator("#swipe-handle")).to_be_hidden()
                expect(page).to_have_url(re.compile(r"mode=types"))
                page.click("#mode-swipe")
                expect(page.locator("#types-legend")).to_be_hidden()
                print("ok  'Change types · AI': capa, leyenda con % y aviso de interpretación")
            if (WEB / "layers" / page.locator("#site").input_value() / "ask.json").exists():
                page.click("#ask-btn")
                expect(page.locator("#ask")).to_be_visible()
                assert page.locator("#ask .ask-q").count() >= 3, "faltan preguntas guiadas"
                page.locator("#ask .ask-q").nth(1).click()
                expect(page.locator("#ask .ask-q").nth(1)).to_have_attribute("aria-pressed", "true")
                expect(page.locator("#ask-answer")).not_to_be_empty()
                expect(page.locator("#ask-foot")).to_contain_text("AI")
                page.click("#ask .ask-langs button[data-lang=es]")
                expect(page.locator("#ask-foot")).to_contain_text("IA")
                page.click("#read-btn")
                expect(page.locator("#ask")).to_be_hidden()
                page.click("#read-close")
                print("ok  'Ask the radar': preguntas, respuesta, EN/ES, etiqueta de IA, una tarjeta a la vez")

        # 2. Modo demo
        page.goto(base + "/?demo=1&pol=HHHH", wait_until="load")
        expect(page.locator("#demo-banner")).to_be_visible()
        expect(page.locator(".date-tag.left")).to_have_text("20 Jun 2026", timeout=10000)
        expect(page.locator("#empty")).to_be_hidden()
        print("ok  demo: aviso visible y capas cargadas")

        # HUD estilo transmisión: T+ días entre escenas y medidores
        expect(page.locator("#hud-days")).to_have_text("084")
        expect(page.locator("#g-dec")).to_have_text("16.0")
        assert page.get_attribute("#g-dec-arc", "stroke-dasharray").startswith("15.9"), "el arco no refleja el valor"
        print("ok  HUD: T+ 084 días y medidores con su arco")
        expect(page.locator("#water")).to_be_visible()
        expect(page.locator("#water-val")).to_contain_text("km²")
        print("ok  panel: área de agua HH con km²")
        expect(page.locator("#why")).to_be_hidden()
        print("ok  'Why it changed' oculto en el demo (no tiene why.json)")
        expect(page.locator("#read-btn")).to_be_hidden()
        print("ok  'Read the dance' oculto en el demo (no tiene resumen)")
        expect(page.locator("#mode-types")).to_be_hidden()
        expect(page.locator("#ask-btn")).to_be_hidden()
        print("ok  'Change types' oculto en el demo (no tiene types.json)")

        # Vista inicial: "Two dates", con la línea visible y un vaivén de pista
        expect(page.locator("#mode-swipe")).to_have_attribute("aria-pressed", "true")
        expect(page.locator("#swipe-handle")).to_be_visible()
        assert page.locator(".leaflet-image-layer").count() >= 2, "faltan capas antes/después"
        print("ok  la vista inicial es 'Two dates' con la línea visible")

        # Play: la línea se mueve sola; Pause la detiene
        handle = page.locator("#swipe-handle")
        page.click("#play")
        expect(handle).to_be_visible()
        pos = lambda: float(handle.evaluate("e => e.style.left").rstrip("%"))
        page.wait_for_timeout(400); a1 = pos()
        page.wait_for_timeout(700); a2 = pos()
        assert abs(a2 - a1) > 3, f"Play no mueve la línea ({a1} -> {a2})"
        page.click("#play")
        expect(page.locator("#play")).to_have_attribute("aria-pressed", "false")
        p1 = pos(); page.wait_for_timeout(500)
        assert pos() == p1, "Pause no detiene la línea"
        print("ok  Play mueve la línea sola y Pause la detiene")
        assert page.locator(".leaflet-image-layer").count() >= 2, "faltan capas antes/después en Two dates"

        box = page.locator(".knob").bounding_box()
        wrap = page.locator(".map-wrap").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(wrap["x"] + wrap["width"] * 0.8, box["y"] + box["height"] / 2, steps=10)
        page.mouse.up()
        left = float(handle.evaluate("e => e.style.left").rstrip("%"))
        assert 75 < left < 85, f"la barra no se movió con el mouse ({left}%)"
        cur = float(page.evaluate("document.getElementById('hud-cursor').style.left").rstrip("%"))
        assert 22 < cur < 32, f"el cursor del HUD no sigue a la línea ({cur}%)"
        clip = page.evaluate("[...document.querySelectorAll('.leaflet-pane')].find(e => e.className.includes('after')).style.clip")
        assert clip.startswith("rect("), clip
        handle.focus()
        page.keyboard.press("ArrowLeft")
        assert float(handle.evaluate("e => e.style.left").rstrip("%")) < left, "las flechas no mueven la barra"
        print("ok  la barra se arrastra con mouse y teclado y recorta la capa 'después'")

        page.click("#mode-change")
        expect(page.locator("#legend")).to_be_visible()
        expect(page.locator("#swipe-handle")).to_be_hidden()
        page.click("#pol button:has-text('HV')")
        expect(page.locator("#pol-note")).to_contain_text("Cross-polarized")
        expect(page).to_have_url(re.compile(r"pol=HVHV.*demo=1|demo=1.*pol=HVHV"))
        print("ok  vista de cambio, leyenda y cambio de polarización")

        browser.close()
    srv.shutdown()

    assert not js_errors, f"errores de JavaScript: {js_errors}"
    assert not missing, f"archivos del sitio con error: {missing}"
    print("\nTodas las pruebas del visor pasaron.")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
