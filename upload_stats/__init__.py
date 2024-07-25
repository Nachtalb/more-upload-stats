import json
import webbrowser
from base64 import urlsafe_b64encode
from datetime import datetime
from functools import partial
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
from typing import Any, List, Literal, Optional, Tuple, TypedDict, Union

from pynicotine.pluginsystem import returncode

from .core.base import BasePlugin, PeriodicJob, __version__  # type: ignore[attr-defined]
from .core.utils import command, startfile
from .tag import a, id_string, li, readable_size_html, small, span, tag
from .utils import BUILD_PATH, HTML_PATH, REL_HTML_PATH, create_m3u


class Stats(TypedDict):
    file: dict[str, dict[str, Any]]
    user: dict[str, dict[str, Any]]
    day: list[int]


class Settings(TypedDict):
    stats_file: str
    stats_html_file: str
    playlist_file: str
    dark_theme: bool
    quiet: bool
    auto_backup: int
    auto_regenerate: int
    auto_refresh: bool
    threshold_auto: bool
    threshold_file: int
    threshold_user: int


class Plugin(BasePlugin):
    backup_folder = BUILD_PATH / "backups"
    backup_folder.mkdir(exist_ok=True, parents=True)

    settings: Settings = {  # type: ignore[assignment]
        "stats_file": str(BUILD_PATH / "stats.json"),
        "stats_html_file": str(BUILD_PATH / "index.html"),
        "playlist_file": str(BUILD_PATH / "playlist.m3u"),
        "dark_theme": True,
        "quiet": False,
        "auto_backup": 24,
        "auto_regenerate": 30,
        "auto_refresh": False,
        "threshold_auto": True,
        "threshold_file": 2,
        "threshold_user": 5,
    }
    metasettings: dict[str, dict[str, str]] = {
        "stats_file": {
            "description": """Raw statistics file
JSON file where containing the raw data""",
            "type": "file",
            "chooser": "file",
        },
        "stats_html_file": {
            "description": """Statistic page file
HTML file presenting the data in a human readable way""",
            "type": "file",
            "chooser": "file",
        },
        "playlist_file": {
            "description": """Playlist file
.m3u playlist file of the top 25 most uploaded songs""",
            "type": "file",
            "chooser": "file",
        },
        "dark_theme": {
            "description": """Dark Theme
Enable / Disable dark theme""",
            "type": "bool",
        },
        "quiet": {
            "description": """Quieter
Don\'t print as much to the console""",
            "type": "bool",
        },
        "auto_backup": {
            "description": f"""Auto Backup every x hours
Backup folder: {backup_folder}""",
            "type": "bool",
        },
        "auto_refresh": {
            "description": """Auto refresh
Automatically refresh the statistics page every minute""",
            "type": "bool",
        },
        "auto_regenerate": {
            "description": """Auto regenerate
Automatically regenerate statistics page every X minutes""",
            "type": "int",
        },
        "threshold_auto": {
            "description": """Auto threshold
Automatically set a threshold respective to the gathered data.
Data under the threshold will be hidden from the statistics page.
Overrides both user and file threshold when enabled.""",
            "type": "bool",
        },
        "threshold_file": {
            "description": """User threshold
Fix threshold for users.
Only users who downloaded more files than this will be shown on the statistics page.""",
            "type": "int",
        },
        "threshold_user": {
            "description": """File threshold
Fix threshold for files.
Only files that have been uploaded more than this will be shown on the statistics page.""",
            "type": "int",
        },
    }

    default_stats: Stats = {"file": {}, "user": {}, "day": [0, 0, 0, 0, 0, 0, 0]}

    def init(self) -> None:
        super().init()  # type: ignore[no-untyped-call]
        self.stats: Stats = self.default_stats.copy()
        self.load_stats()

        self.auto_builder = PeriodicJob(  # type: ignore[no-untyped-call]
            name="AutoBuilder",
            delay=lambda: self.settings["auto_regenerate"] * 60,
            update=self.update_stats,
            before_start=lambda: self.auto_update.first_round.wait(),
        )
        self.auto_builder.start()
        self.auto_backup = PeriodicJob(  # type: ignore[no-untyped-call]
            name="AutoBuilder",
            delay=lambda: self.settings["auto_backup"] * 3600,
            update=partial(self.backup, "auto"),
            before_start=lambda: self.auto_update.first_round.wait(),
        )
        self.auto_backup.start()

    def pre_stop(self) -> None:
        self.auto_update.stop()  # type: ignore[no-untyped-call]
        self.auto_builder.stop(False)  # type: ignore[no-untyped-call]

    def load_stats(self) -> None:
        path = Path(self.settings["stats_file"])
        try:
            self.stats = self.default_stats.copy()
            self.stats.update(json.loads(path.read_text()))
        except FileNotFoundError:
            self.log(f'Statistics file does not exist yet. Creating "{path}"')
            self.save_stats()

    def log(
        self,
        *msg: Union[str, Exception],
        msg_args: List[Any] = [],
        level: Optional[str] = None,
        with_prefix: bool = True,
        force: bool = False,
    ) -> None:
        if self.settings["quiet"] and not force and not level:
            return
        super().log(*msg, msg_args=msg_args, level=level, with_prefix=with_prefix)  # type: ignore[no-untyped-call]

    def settings_changed(self, before: dict[str, Any], after: dict[str, Any], change: dict[str, Any]) -> None:
        if not self.settings["quiet"]:
            super().settings_changed(before, after, change)  # type: ignore[no-untyped-call]

    def save_stats(self, file: Optional[Path] = None) -> None:
        if not file:
            file = Path(self.settings["stats_file"])
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(self.stats))

    def upload_finished_notification(self, user: str, virtual_path: str, real_path: str) -> None:
        info = self.stats["file"].get(real_path, {})
        user_info = self.stats["user"].get(user, {})
        try:
            stat = Path(real_path).stat()
        except:  # noqa
            self.log(f'Could not get file info for "{real_path}"')
            stat = None

        weekday = datetime.now().weekday()
        self.stats["day"][weekday] = self.stats["day"][weekday] + 1

        self.stats["file"][real_path] = {
            "total": info.get("total", 0) + 1,
            "virtual_path": virtual_path,
            "last_user": user,
            "last_modified": stat.st_mtime if stat else 0,
            "file_size": stat.st_size if stat else 0,
            "total_bytes": info.get("total_bytes", 0) + stat.st_size if stat else 0,
        }

        self.stats["user"][user] = {
            "total": user_info.get("total", 0) + 1,
            "last_file": virtual_path,
            "last_real_file": real_path,
            "total_bytes": user_info.get("total_bytes", 0) + stat.st_size if stat else 0,
        }
        self.save_stats()

    def summary(self) -> str:
        users, files = self.stats["user"].values(), self.stats["file"].values()
        total_users = len(users)
        total_files = len(files)

        bytes_per_user: List[int] = [user["total_bytes"] for user in users if user.get("total_bytes")] or [0]
        files_per_user: List[int] = [user["total"] for user in users] or [0]

        average_bytes_user = readable_size_html(mean(bytes_per_user))
        median_bytes_user = readable_size_html(median(bytes_per_user))
        average_files_user = format(mean(files_per_user), ".2f")
        median_files_user = median(files_per_user)

        total_uploads_per_file: List[int] = [file["total"] for file in files if file.get("total")] or [0]
        total_bytes_per_file: List[int] = [file["total_bytes"] for file in files if file.get("total_bytes")] or [0]

        total_uploads = sum(total_uploads_per_file)
        total_bytes = readable_size_html(sum(total_bytes_per_file))

        file_size: List[int] = [file["file_size"] for file in files if file.get("file_size")] or [0]

        average_filesize = readable_size_html(mean(file_size))
        median_filesize = readable_size_html(median(file_size))
        average_bytes = readable_size_html(mean(total_bytes_per_file))
        median_bytes = readable_size_html(median(total_bytes_per_file))
        average_uploads_file = format(mean(total_uploads_per_file), ".2f")
        median_uploads_files = median(total_uploads_per_file)

        return f"""
        <dl>
          <dt>Total unique Users:</dt>
          <dd>{total_users}</dd>
          <dt>Total unique Files:</dt>
          <dd>{total_files}</dd>
          <dt>Total Uploads:</dt>
          <dd>{total_uploads}</dd>
          <dt>Total Bytes:</dt>
          <dd>{total_bytes}</dd>
          <dt>Average per User:</dt>
          <dd>Average Bytes: {average_bytes_user}</dd>
          <dd>Median Bytes: {median_bytes_user}</dd>
          <dd>Average Files: {average_files_user}</dd>
          <dd>Median Files: {median_files_user}</dd>
          <dt>Average per File:</dt>
          <dd>Average Filesize: {average_filesize}</dd>
          <dd>Median Filesize: {median_filesize}</dd>
          <dd>Average Bytes Total: {average_bytes}</dd>
          <dd>Median Bytes Total: {median_bytes}</dd>
          <dd>Average Uploads: {average_uploads_file}</dd>
          <dd>Median Uploads: {median_uploads_files}</dd>
        </dl>
        """

    def user_threshold(self) -> int:
        if self.settings["threshold_auto"]:
            if not self.stats["user"]:
                return 0
            uniq_totals = set(map(lambda i: i["total"], self.stats["user"].values()))
            return sorted(uniq_totals)[int(len(uniq_totals) * 0.25)]  # type: ignore[no-any-return]  # Get the 25th percentile
        else:
            return self.settings["threshold_user"]

    def user_stats(self, threshold: int = 0) -> str:
        html = ""
        for user, data in sorted(self.stats["user"].items(), key=lambda i: i[1]["total"], reverse=True):
            if data["total"] <= threshold:
                continue
            filename = a(
                Path(data["last_file"]).name,
                href="#file-" + id_string(data["last_real_file"]),
                data_tooltip=f'RP: {data["last_real_file"]}\nVP: {data["last_file"]}',
                data_tooltip_align="left",
            )

            total_bytes_raw = total_bytes = "-"
            if total_bytes_raw := data.get("total_bytes"):  # type: ignore[assignment]
                total_bytes = readable_size_html(total_bytes_raw)

            html += f"""
            <tr id="user-{id_string(user)}">
                <td>{user}</td>
                <td>{data["total"]}</td>
                <td sorttable_customkey="{total_bytes_raw}">{total_bytes}</td>
                <td>{filename}</td>
            </tr>"""
        return html

    def file_threshold(self) -> int:
        if self.settings["threshold_auto"]:
            if not self.stats["file"]:
                return 0
            uniq_totals = set(map(lambda i: i["total"], self.stats["file"].values()))
            return sorted(uniq_totals)[int(len(uniq_totals) * 0.25)]  # type: ignore[no-any-return]  # Get the 25th percentile
        else:
            return self.settings["threshold_file"]

    def file_stats(self, threshold: int = 0) -> str:
        html = ""

        for real_path, file in sorted(self.stats["file"].items(), key=lambda i: i[1]["total"], reverse=True):
            if file["total"] <= threshold:
                continue
            name = a(
                Path(real_path).name,
                data_tooltip=f'RP: {real_path}\nVP: {file["virtual_path"]}',
                href="file:///" + real_path,
                target="_blank",
                data_tooltip_align="left",
            )

            total_bytes_raw = total_bytes = "-"
            if total_bytes_raw := file.get("total_bytes"):  # type: ignore[assignment]
                total_bytes = readable_size_html(total_bytes_raw)

            file_size_raw = file_size = "-"
            if file_size_raw := file.get("file_size"):  # type: ignore[assignment]
                file_size = readable_size_html(file_size_raw)

            last_user = a(file["last_user"], href="#user-" + id_string(file["last_user"]))

            html += f"""
            <tr id="file-{id_string(real_path)}">
                <td>{name}</td>
                <td>{file["total"]}</td>
                <td sorttable_customkey="{total_bytes_raw}">{total_bytes}</td>
                <td sorttable_customkey="{file_size_raw}">{file_size}</td>
                <td>{last_user}</td>
            </tr>"""
        return html

    def file_link(self, file: Union[str, Path], base64: bool = False) -> str:
        file = Path(file)
        href = f"file:///{file}"
        if base64:
            b64 = urlsafe_b64encode(file.read_bytes()).decode("utf-8")
            href = f"data:application/octet-stream;base64,{b64}"

        return a(file.name, href=href, data_tooltip=file, target="_blank", download=file.name)  # type: ignore[no-any-return]

    def ranking(self, data: List[Tuple[str, int, str]], size: int = 5) -> str:
        html = ""
        data = sorted(data, key=lambda i: i[1], reverse=True)
        for index in range(size):
            score: Union[str, int]
            title = score = "-"
            link_id = None
            if len(data) >= index + 1:
                title, score, link_id = data[index]
            html += li(a(small(f"{score} ") + span(span(title)), href=link_id or "#"))
        return html

    def user_ranking(self) -> str:
        data: List[Tuple[str, int, str]] = [
            (name, user["total"], "#user-" + id_string(name)) for name, user in self.stats["user"].items()
        ]
        return self.ranking(data)

    def file_ranking(self) -> str:
        data: List[Tuple[str, int, str]] = [
            (Path(path).name, file["total"], "#file-" + id_string(path)) for path, file in self.stats["file"].items()
        ]
        return self.ranking(data)

    def icons(self) -> str:
        icons = ""
        for icon in (HTML_PATH / "images").glob("*.svg"):
            icons += f'.icon-{icon.stem} {{ background-image: url("file:///{REL_HTML_PATH}/images/{icon.name}"); }}'
        return tag("style", icons.replace("\\", "/"))

    def build_html(self, user_threshold: Optional[int] = None, file_threshold: Optional[int] = None) -> str:
        template = (HTML_PATH / "template.html").read_text()

        info: dict[str, Any] = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "BASE": str(REL_HTML_PATH).replace("\\", "/") + "/",
            "DARK_THEME": "checked" if self.settings["dark_theme"] else "",
            "head": "",
            "update": "",
            "summary": self.summary(),
            "stats_link": self.file_link(self.settings["stats_file"]),
            "playlist_file": self.file_link(self.settings["playlist_file"], base64=True),
            "userranking": self.user_ranking(),
            "fileranking": self.file_ranking(),
            "icons": self.icons(),
        }

        if self.settings["auto_refresh"] and user_threshold is file_threshold is None:
            info["head"] = tag("meta", http_equiv="refresh", content=60)

        if self.update_url and self.update_version:
            info["update"] = tag(
                "h4 a",
                "A new update is available. Current: {current} New: {new}".format(
                    current=tag("kbd", __version__), new=tag("kbd", self.update_version[1:])
                ),
                href=self.update_url,
                target="_blank",
            )

        max_day = max(self.stats["day"]) or 1
        for index, day in enumerate(self.stats["day"]):
            info[f"day_{index}"] = day
            info[f"day_{index}_p"] = 3 + (97 / max_day * day)

        user_threshold = self.user_threshold() if user_threshold is None else user_threshold
        file_threshold = self.file_threshold() if file_threshold is None else file_threshold
        info.update(
            {
                "user_threshold": user_threshold,
                "file_threshold": file_threshold,
                "userstats": self.user_stats(user_threshold),
                "filestats": self.file_stats(file_threshold),
            }
        )

        return template.format(**info)

    def update_index_html(self) -> Path:
        file = Path(self.settings["stats_html_file"])
        file.write_text(self.build_html(), encoding="utf-8")
        self.log(f'Statistics generated and saved to "{file}"')
        return file

    def create_m3u(self) -> None:
        songs = sorted(self.stats["file"], reverse=True, key=lambda i: self.stats["file"][i]["total"])
        file = self.settings["playlist_file"]
        create_m3u("TOP #25", songs, file, max_files=25)
        self.log(f'Playlist generated and saved to "{file}"')

    @command("build")  # type: ignore[no-untyped-call, misc]
    def update_stats(
        self,
        initiator: Optional[Any] = None,
        args: Optional[List[str]] = None,
        page: bool = True,
        playlist: bool = True,
    ) -> Union[str, Path, Literal[1]]:
        if playlist:
            self.create_m3u()

        filename: Union[str, Path]
        if page:
            args = args or []
            self.log(f"args: {args}")

            try:
                thresholds: List[int] = [int(args[0]), int(args[1])]
            except (ValueError, IndexError):
                thresholds = []

            if thresholds:
                with NamedTemporaryFile("w", encoding="utf-8", suffix=".html", delete=False) as file:
                    file.write(self.build_html(*thresholds))
                    filename = file.name
            else:
                filename = self.update_index_html()

            if not initiator:
                return filename
        return returncode["zap"]  # type: ignore[no-any-return]

    @command("open")  # type: ignore[no-untyped-call, misc]
    def open_stats(self, page: bool = True, playlist: bool = True) -> None:
        if page:
            filename = page if isinstance(page, str) else self.settings["stats_html_file"]
            webbrowser.open(filename)
        if playlist:
            startfile(self.settings["playlist_file"])  # type: ignore[no-untyped-call]

    @command("")  # type: ignore[no-untyped-call, misc]
    def update_and_open(
        self,
        args: Optional[List[str]] = None,
        create_page: bool = True,
        create_playlist: bool = True,
        open_page: bool = True,
        open_playlist: bool = False,
    ) -> Literal[1]:
        filename = self.update_stats(args=args, page=create_page, playlist=create_playlist)
        self.open_stats(page=filename if filename and open_page else open_page, playlist=open_playlist)
        return returncode["zap"]  # type: ignore[no-any-return]

    @command  # type: ignore[misc]
    def backup(self, name: str = "") -> None:
        try:
            name = (name + "-") if name else ""
            backup = self.backup_folder / ("stats-" + name + datetime.now().strftime("%Y_%M_%d-%H_%M_%S") + ".json")
            self.save_stats(backup)
            self.log(f'Created a backup at "{backup}"', force=True)
        except Exception as e:
            self.log(e, force=True)

    @command("reset")  # type: ignore[no-untyped-call, misc]
    def reset_stats(self) -> Literal[1]:
        self.backup("reset")

        self.stats = self.default_stats.copy()
        self.save_stats()

        self.log("Statistics have been reset", force=True)
        return returncode["zap"]  # type: ignore[no-any-return]

    __publiccommands__ = __privatecommands__ = [
        ("playlist", partial(update_and_open, create_page=False, open_page=False, open_playlist=True)),
        ("page", partial(update_and_open, create_playlist=False)),
        ("open-page", partial(open_stats, playlist=False)),
        ("open-playlist", partial(open_stats, page=False)),
        ("build-page", partial(update_stats, playlist=False)),
        ("build-playlist", partial(update_stats, page=False)),
    ]
