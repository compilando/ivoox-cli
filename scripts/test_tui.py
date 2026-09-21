# /// script
# requires-python = ">=3.11"
# dependencies = ["requests>=2.32,<3", "beautifulsoup4>=4.12,<5", "textual>=6,<9"]
# ///
"""Navegación real de Textual y reproducción IPC con mpv sin salida de sonido."""

import argparse
import asyncio
import json
import os
import runpy
import sys
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from textual.widgets import Button, DataTable, Input, Static

MODULE = runpy.run_path(str(Path(__file__).resolve().parent.parent / "ivx"))


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ivx-tui-test-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.args = argparse.Namespace(directory=root / "library", config=root / "config", local_only=True)
        self.args.config.mkdir()
        self.url = "https://www.ivoox.com/podcast-ciencia_sq_f11234_1.html"
        (self.args.config / "sources.txt").write_text(self.url + "\n")
        folder = self.args.directory / "program-1234"
        folder.mkdir(parents=True)
        for number, title, published in [
            ("1", "Ciencia [sin formato]", "2024-02-03"),
            ("2", "Historia del mar", "2023-01-02"),
        ]:
            audio = folder / f"{number}.mp3"
            # Contenido WAV PCM determinista; mpv detecta por bytes, no extensión.
            with wave.open(str(audio), "wb") as output:
                output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
                output.writeframes(b"\0\0" * 8000 * 40)
            audio.with_suffix(".json").write_text(json.dumps(
                {"title": title, "published": published}))
            os.utime(audio, (int(number), int(number)))
        self.player = MODULE["MpvPlayer"](audio_output="null")
        self.app = MODULE["create_tui"](self.args, player=self.player)
        self.addAsyncCleanup(self.player.close)

    async def wait_until(self, condition, message):
        for _ in range(60):
            if await condition():
                return
            await asyncio.sleep(0.05)
        self.fail(f"{message}; estado={self.app.query_one('#notice', Static).render()}; "
                  f"cola={self.app.queue_index}/{len(self.app.queue)}")

    async def test_navigation_and_real_playback(self):
        # Duración suficiente para comprobar también saltos de un minuto.
        audio = self.args.directory / "program-1234" / "1.mp3"
        with wave.open(str(audio), "wb") as output:
            output.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            output.writeframes(b"\0\0" * 8000 * 130)
        async with self.app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            self.assertEqual(self.app.query_one("#collections", DataTable).row_count, 2)
            self.assertEqual(self.app.query_one("#episodes", DataTable).row_count, 2)
            self.assertEqual([item["id"] for item in self.app.visible_episodes], ["1", "2"])
            await pilot.press("o")
            self.assertEqual([item["id"] for item in self.app.visible_episodes], ["2", "1"])
            await pilot.press("o")
            self.assertEqual([item["id"] for item in self.app.visible_episodes], ["1", "2"])
            await pilot.press("j", "enter")
            self.assertEqual(self.app.focused.id, "episodes")
            await pilot.press("slash", *list("ciencia"))
            self.assertEqual(self.app.query_one("#episodes", DataTable).row_count, 1)
            await pilot.press("enter", "enter")
            async def playing():
                try:
                    return await self.player.command("get_property", "time-pos") is not None
                except (ValueError, OSError):
                    return False
            await self.wait_until(playing, "mpv no empezó a reproducir")
            self.assertEqual(self.app.now_title, "Ciencia [sin formato]")
            await pilot.press("space")
            self.assertTrue(await self.player.command("get_property", "pause"))
            await pilot.press("right")
            async def advanced():
                return await self.player.command("get_property", "time-pos") >= 9
            await self.wait_until(advanced, "La flecha derecha no hizo seek")
            async def duration_known():
                return self.app.player_duration > 0
            await self.wait_until(duration_known, "No se obtuvo la duración del episodio")
            await pilot.press("5")
            async def halfway():
                position = await self.player.command("get_property", "time-pos")
                return 64 <= position <= 67
            await self.wait_until(halfway, "El seek absoluto al 50% no funcionó")
            progress = self.app.query_one("#progress")
            rendered_bar = progress.query_one("#bar")
            self.assertEqual(rendered_bar.size.width, progress.content_size.width,
                             "La barra visible no ocupa todo el ancho disponible")
            await pilot.click(progress, offset=(progress.size.width // 4, 0))
            async def first_quarter():
                position = await self.player.command("get_property", "time-pos")
                return 31 <= position <= 34
            await self.wait_until(first_quarter, "El seek absoluto con clic no funcionó")
            await pilot.press("shift+right")
            async def minute_forward():
                position = await self.player.command("get_property", "time-pos")
                return 91 <= position <= 95
            await self.wait_until(minute_forward, "Mayús+derecha no avanzó un minuto")
            await pilot.press("shift+left")
            await self.wait_until(first_quarter, "Mayús+izquierda no retrocedió un minuto")
            await pilot.press("minus")
            self.assertEqual(await self.player.command("get_property", "volume"), 95)
            await pilot.press("space")
            self.assertFalse(await self.player.command("get_property", "pause"))
            await pilot.press("s")
            async def idle():
                return await self.player.command("get_property", "idle-active")
            await self.wait_until(idle, "mpv no se detuvo")
            self.assertTrue(self.app.stopped)
            await pilot.press("escape")
            self.assertEqual(self.app.query_one("#episodes", DataTable).row_count, 2)
            await pilot.press("g", "enter", "n")
            self.assertEqual(self.app.queue_index, 1)
            await pilot.press("p")
            self.assertEqual(self.app.queue_index, 0)
            await pilot.press("a")
            self.assertEqual(self.app.focused.id, "source-url")
            await pilot.press("escape")
            process = self.player.process
            player_directory = Path(self.player.temporary.name)
            await pilot.press("q")
        self.assertEqual(process.returncode, 0, "mpv no recibió un cierre ordenado")
        self.assertFalse(player_directory.exists(), "No se retiró el temporal de mpv")
        self.assertIsNone(self.player.socket)

    async def test_empty_library_small_terminal_and_add(self):
        self.args.directory = Path(self.tmp.name) / "empty"
        self.args.config = Path(self.tmp.name) / "empty-config"
        self.app = MODULE["create_tui"](self.args, player=self.player)
        async with self.app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            self.assertEqual(self.app.query_one("#episodes", DataTable).row_count, 0)
            await pilot.press("enter", "enter", "space", "s", "n", "p")
            self.assertIsNone(self.player.process)
            await pilot.press("a")
            self.app.screen.query_one(Input).value = self.url
            await pilot.press("enter")
            await self.app.workers.wait_for_complete()
            await pilot.pause()
            self.assertEqual((self.args.config / "sources.txt").read_text().strip(), self.url)
            self.assertEqual(self.app.query_one("#collections", DataTable).row_count, 2)
            self.assertFalse(self.args.directory.exists(), "Añadir una fuente creó la biblioteca")
            await pilot.press("q")

    async def test_collection_filter_and_episode_filter_reset(self):
        async with self.app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            episode_search = self.app.query_one("#search", Input)
            episode_search.value = "sin coincidencias"
            episode_search.add_class("visible")
            await pilot.pause()
            self.assertEqual(self.app.query_one("#episodes", DataTable).row_count, 0)

            collections = self.app.query_one("#collections", DataTable)
            collections.focus()
            collections.move_cursor(row=1)
            await pilot.pause()
            self.assertEqual(episode_search.value, "")
            self.assertFalse(episode_search.has_class("visible"))
            self.assertEqual(self.app.query_one("#episodes", DataTable).row_count, 2)

            await pilot.press("f", *list("ciencia"))
            await pilot.pause()
            podcast_search = self.app.query_one("#collection-search", Input)
            self.assertIs(self.app.focused, podcast_search)
            self.assertEqual(collections.row_count, 1)
            self.assertEqual(self.app.group_key, "program-1234")
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(podcast_search.value, "")
            self.assertEqual(collections.row_count, 2)

    async def test_missing_metadata_and_invalid_source(self):
        folder = self.args.directory / "program-1234"
        (folder / "1.json").write_text("{broken")
        (self.args.config / "sources.txt").write_text("invalid\n" + self.url + "\n")
        groups, warnings = MODULE["library_collections"](self.args.directory, self.args.config)
        self.assertEqual(len(groups[0]["episodes"]), 2)
        self.assertEqual(len(warnings), 2)
        async with self.app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            self.assertIn("no válida", str(self.app.query_one("#notice", Static).render()))

    async def test_exit_terminates_active_cli_job(self):
        spawn = asyncio.create_subprocess_exec
        async def slow_cli(*command, **kwargs):
            return await spawn(sys.executable, "-c", "import time; time.sleep(60)", **kwargs)
        async with self.app.run_test(size=(80, 24)) as pilot:
            with patch.object(asyncio, "create_subprocess_exec", slow_cli):
                self.app.cli_job("get", self.url, "-n", "10")
                async def started():
                    return self.app.job is not None
                await self.wait_until(started, "No arrancó la operación")
                process = self.app.job
                await pilot.press("q")
        self.assertIsNotNone(process.returncode, "Quedó una operación huérfana al salir")
        self.assertIsNone(self.app.job)
        self.assertFalse(self.app.busy)

    async def test_account_collection_parsing_and_merge(self):
        class Response:
            def __init__(self, url, text):
                self.url = url
                self.text = text

            def raise_for_status(self):
                return None

        pages = {
            "mis-listas_hk.html": '''<div id="myListAudios">
              <div class="modulo-type-lista"><p class="title-wrapper">Mi lista</p>
              <a href="/mi-lista_bk_list_77_1.html">abrir</a></div>
              <div class="modulo-type-lista"><a href="/mis-audios_hn.html">Escuchar más tarde</a></div>
            </div>''',
            "gestionar-suscripciones_je.html": '''<div id="main">
              <a class="title" href="/suscripciones_jb_88_1.html">Mi podcast</a></div>''',
        }

        class Client:
            def get(self, url, timeout):
                name = url.rsplit("/", 1)[-1]
                return Response(url, pages[name])

        groups = MODULE["account_collections"](Client(), self.args.config, True)
        self.assertEqual({g["key"] for g in groups}, {"list-77", "account-later", "account-sub-88"})
        html = BeautifulSoup('''<tbody id="suscriptions">
          <tr><td><a class="title" href="/uno-audios-mp3_rf_9_1.html">Uno</a></td><td>28/04/2015</td></tr>
          <tr><td><a class="title" href="/dos-audios-mp3_rf_8_1.html">Dos</a></td></tr>
        </tbody>''', "html.parser")
        with patch.dict(MODULE["require_account_page"].__globals__,
                        {"require_account_page": lambda c, u, ajax=False: html}):
            episodes = MODULE["account_episodes"](Client(), groups[-1]["url"], 1)
        self.assertEqual(episodes, [{"id": "9", "url": "https://www.ivoox.com/uno-audios-mp3_rf_9_1.html",
                                     "title": "Uno", "published": "2015-04-28"}])
        groups[-1]["episodes"] = episodes
        groups[-1]["loaded"] = True
        merged = MODULE["merge_collections"](MODULE["library_collections"](
            self.args.directory, self.args.config)[0], groups)
        self.assertEqual(len(merged), 5)
        self.assertTrue(merged[1]["account"])

        initial = BeautifulSoup('''<tbody id="suscriptions" data-trigger="ajax_pagination"
          data-href="mi-podcast_jb_88" data-page="2">
          <tr><td><a class="title" href="/uno-audios-mp3_rf_9_1.html">Uno</a></td></tr>
          <tr><td><a class="title" href="/dos-audios-mp3_rf_8_1.html">Dos</a></td></tr>
        </tbody>''', "html.parser")
        second = BeautifulSoup('''
          <tr><td><a class="title" href="/tres-audios-mp3_rf_7_1.html">Tres</a></td></tr>
        ''', "html.parser")
        requested = []

        def paged(client, page_url, ajax=False):
            requested.append((page_url, ajax))
            return second if ajax else initial

        clock = type("Clock", (), {"sleep": staticmethod(lambda seconds: None)})
        with patch.dict(MODULE["account_episode_page"].__globals__,
                        {"require_account_page": paged, "time": clock}):
            paged_episodes = MODULE["account_episodes"](Client(), groups[-1]["url"], None, 0)
        self.assertEqual([episode["id"] for episode in paged_episodes], ["9", "8", "7"])
        self.assertEqual(requested[1],
                         ("https://www.ivoox.com/mi-podcast_jb_88_2.html", True))

    async def test_account_urls_are_restricted(self):
        valid = MODULE["account_source"]("https://www.ivoox.com/suscripciones_jb_123_1.html")
        self.assertEqual(valid[0], "account-sub-123")
        for url in ("https://example.com/suscripciones_jb_1_1.html",
                    "https://www.ivoox.com/cerrar-sesion_zs.html"):
            with self.assertRaises(ValueError):
                MODULE["account_source"](url)

    async def test_bounded_download_queue_and_state(self):
        folder = Path(self.tmp.name) / "queue"
        folder.mkdir()
        state = folder / "archive-state.json"
        active = maximum = 0
        lock = threading.Lock()

        def fake_download(episode, target, config, rate):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return episode["id"] != "2"

        episodes = [{"id": str(i), "title": str(i)} for i in range(8)]
        with patch.dict(MODULE["download_queue"].__globals__, {"download": fake_download}):
            result = await asyncio.to_thread(
                MODULE["download_queue"], episodes, folder, self.args.config, 2, 0, state)
        self.assertLessEqual(maximum, 2)
        self.assertEqual(result, {"downloaded": 7, "skipped": 1, "failed": 0})
        saved = json.loads(state.read_text())
        self.assertEqual(saved["status"], "complete")
        self.assertEqual(len(saved["completed"]), 8)

    async def test_archive_from_tui_requires_confirmation(self):
        async with self.app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            self.app.group_key = "program-1234"
            self.app.show_episodes()
            with patch.object(self.app, "cli_job") as job:
                await pilot.press("U")
                await pilot.pause()
                await pilot.click("#archive-confirm")
                await pilot.pause()
                job.assert_called_once_with("archive", self.url)

    async def test_load_all_pages_button(self):
        account_url = "https://www.ivoox.com/mi-podcast_jb_88_1.html"
        self.app.account_groups = [{
            "key": "account-sub-88", "title": "Mi podcast", "url": account_url,
            "account": True, "loaded": True, "loading": False,
            "next_url": "https://www.ivoox.com/mi-podcast_jb_88_2.html",
            "episodes": [{"id": "1", "title": "Uno", "published": "2026-01-01"}],
        }]
        pages = {
            "https://www.ivoox.com/mi-podcast_jb_88_2.html": (
                [{"id": "2", "title": "Dos", "published": "2025-01-01"}],
                "https://www.ivoox.com/mi-podcast_jb_88_3.html"),
            "https://www.ivoox.com/mi-podcast_jb_88_3.html": (
                [{"id": "3", "title": "Tres", "published": "2024-01-01"}], None),
        }

        def fetch(config, url, next_url):
            return pages[next_url]

        async with self.app.run_test(size=(100, 30)) as pilot:
            self.app.group_key = "account-sub-88"
            self.app.action_refresh_library()
            self.assertTrue(self.app.query_one("#pagination").has_class("visible"))
            self.assertEqual(str(self.app.query_one("#load-all", Button).label),
                             "Cargar toda la lista")
            with patch.dict(MODULE["fetch_account_episode_page"].__globals__,
                            {"fetch_account_episode_page": fetch}):
                await pilot.click("#load-all")
                await self.app.workers.wait_for_complete()
                await pilot.pause()
            group = next(g for g in self.app.account_groups if g["key"] == "account-sub-88")
            self.assertEqual([episode["id"] for episode in group["episodes"]], ["1", "2", "3"])
            self.assertIsNone(group["next_url"])
            self.assertFalse(self.app.query_one("#pagination").has_class("visible"))

    async def test_publication_date_formats(self):
        parse = MODULE["publication_date"]
        self.assertEqual(parse("Sun, 20 Sep 2026 21:30:00 +0200"), "2026-09-20")
        self.assertEqual(parse("Publicado 7/4/2020"), "2020-04-07")
        self.assertEqual(parse("2025-12-31T10:00:00Z"), "2025-12-31")
        self.assertIsNone(parse("ayer"))

        folder = Path(self.tmp.name) / "enrich"
        folder.mkdir()
        (folder / "7.mp3").write_bytes(b"already downloaded")
        (folder / "7.json").write_text(json.dumps({"id": "7", "title": "Anterior"}))
        changed = MODULE["download"](
            {"id": "7", "title": "Actual", "published": "2026-09-20"},
            folder, self.args.config)
        self.assertFalse(changed)
        self.assertEqual(json.loads((folder / "7.json").read_text())["published"], "2026-09-20")


if __name__ == "__main__":
    unittest.main(verbosity=2)
