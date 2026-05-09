# window_manager.py - Funktionen zur Verwaltung von Fenstern auf Windows, einschließlich Auflisten, Finden, Positionieren und Minimieren von Fenstern basierend auf Titel- und Prozess-Hinweisen. Wird hauptsächlich für die Morgenroutine verwendet, um die Arbeitsumgebung zu organisieren.
import ctypes
import time
from dataclasses import dataclass
from typing import Callable

import psutil
import win32con
import win32gui
import win32process


LogFn = Callable[[str, str], None]


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    process_name: str
    pid: int
    rect: tuple[int, int, int, int]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def get_work_area() -> tuple[int, int, int, int]:
    """
    Gibt den nutzbaren Bereich des primären Monitors zurück.
    Taskleiste wird berücksichtigt.
    """
    rect = RECT()
    SPI_GETWORKAREA = 48

    success = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETWORKAREA,
        0,
        ctypes.byref(rect),
        0
    )

    if not success:
        return (0, 0, 1920, 1080)

    width = rect.right - rect.left
    height = rect.bottom - rect.top

    return (rect.left, rect.top, width, height)


def get_process_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name()
    except Exception:
        return ""


def list_windows() -> list[WindowInfo]:
    windows: list[WindowInfo] = []

    def callback(hwnd: int, _extra: object) -> None:
        if not win32gui.IsWindow(hwnd):
            return

        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()

        if not title:
            return

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = get_process_name(pid)
            rect = win32gui.GetWindowRect(hwnd)

            windows.append(
                WindowInfo(
                    hwnd=hwnd,
                    title=title,
                    process_name=process_name,
                    pid=pid,
                    rect=rect,
                )
            )
        except Exception:
            return

    win32gui.EnumWindows(callback, None)
    return windows


def score_window(
    window: WindowInfo,
    title_hints: list[str],
    process_hints: list[str],
) -> int:
    score = 0

    title = window.title.lower()
    process = window.process_name.lower()

    for hint in title_hints:
        if hint.lower() in title:
            score += 10

    for hint in process_hints:
        if hint.lower() in process:
            score += 20

    return score


def find_window(
    title_hints: list[str],
    process_hints: list[str],
) -> WindowInfo | None:
    candidates = []

    for window in list_windows():
        score = score_window(window, title_hints, process_hints)

        if score > 0:
            candidates.append((score, window))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def wait_for_window(
    log: LogFn,
    name: str,
    title_hints: list[str],
    process_hints: list[str],
    timeout_seconds: int = 25,
) -> WindowInfo | None:
    end_time = time.time() + timeout_seconds

    while time.time() < end_time:
        window = find_window(title_hints, process_hints)

        if window:
            log("OK", f"Fenster gefunden: {name} | {window.title} | {window.process_name}")
            return window

        time.sleep(1)

    log("WARN", f"Fenster nicht gefunden: {name}")
    return None


def restore_window(window: WindowInfo) -> None:
    try:
        win32gui.ShowWindow(window.hwnd, win32con.SW_RESTORE)
    except Exception:
        pass


def minimize_window(window: WindowInfo, log: LogFn, name: str) -> None:
    try:
        win32gui.ShowWindow(window.hwnd, win32con.SW_MINIMIZE)
        log("OK", f"Fenster minimiert: {name}")
    except Exception as exc:
        log("ERROR", f"Fenster konnte nicht minimiert werden: {name} | {exc}")


def move_window(
    window: WindowInfo,
    x: int,
    y: int,
    width: int,
    height: int,
    log: LogFn,
    name: str,
) -> None:
    try:
        restore_window(window)
        time.sleep(0.2)
        win32gui.MoveWindow(window.hwnd, x, y, width, height, True)
        log("OK", f"Fenster positioniert: {name} -> x={x}, y={y}, w={width}, h={height}")
    except Exception as exc:
        log("ERROR", f"Fenster konnte nicht positioniert werden: {name} | {exc}")


def arrange_morning_windows(log: LogFn) -> None:
    log("INFO", "Fensteranordnung startet.")

    work_x, work_y, work_w, work_h = get_work_area()

    left_x = work_x
    left_y = work_y
    left_w = work_w // 2
    left_h = work_h

    right_x = work_x + left_w
    right_y = work_y
    right_w = work_w - left_w
    right_h = work_h

    todo_x = right_x
    todo_y = right_y
    todo_w = right_w
    todo_h = max(260, work_h // 3)

    vscode = wait_for_window(
        log,
        "VS Code",
        title_hints=["visual studio code", "code"],
        process_hints=["code.exe"],
        timeout_seconds=25,
    )

    discord = wait_for_window(
        log,
        "Discord",
        title_hints=["discord"],
        process_hints=["discord.exe"],
        timeout_seconds=25,
    )

    todo = wait_for_window(
        log,
        "TODO",
        title_hints=["todo.md", "todo", "editor", "notepad"],
        process_hints=["notepad.exe"],
        timeout_seconds=10,
    )

    obs = find_window(
        title_hints=["obs"],
        process_hints=["obs64.exe", "obs32.exe"],
    )

    spotify = find_window(
        title_hints=["spotify"],
        process_hints=["spotify.exe"],
    )

    whatsapp = find_window(
        title_hints=["whatsapp"],
        process_hints=["whatsapp.exe", "applicationframehost.exe"],
    )

    if vscode:
        move_window(vscode, left_x, left_y, left_w, left_h, log, "VS Code")

    if discord:
        move_window(discord, right_x, right_y, right_w, right_h, log, "Discord")

    if todo:
        move_window(todo, todo_x, todo_y, todo_w, todo_h, log, "TODO")

    if obs:
        minimize_window(obs, log, "OBS")
    else:
        log("WARN", "OBS-Fenster nicht gefunden. Minimieren übersprungen.")

    if spotify:
        minimize_window(spotify, log, "Spotify")
    else:
        log("WARN", "Spotify-Fenster nicht gefunden. Minimieren übersprungen.")

    if whatsapp:
        minimize_window(whatsapp, log, "WhatsApp")
    else:
        log("WARN", "WhatsApp-Fenster nicht gefunden. Minimieren übersprungen.")

    log("INFO", "Fensteranordnung abgeschlossen.")