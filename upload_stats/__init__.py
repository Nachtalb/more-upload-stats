"""This module contains the main Plugin class for the "More Upload Stats" plugin.

The plugin tracks file uploads and user activity to generate statistics.
The statistics are mainly displayed in a dynamically built HTML page.
Additionally, the plugin can generate a playlist file with the top 25 uploads.

The plugin can be configured to automatically backup the statistics and rebuild
the statistics page periodically.

.. seealso:: :class:`npc.BasePlugin` for more information about the plugin class.
"""

import json
import webbrowser
from base64 import urlsafe_b64encode
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from tempfile import NamedTemporaryFile
from textwrap import dedent
from typing import Any, List, Optional, Tuple, TypedDict, Union

from .defaults import BUILD_PATH, HTML_PATH, REL_HTML_PATH
from .html import a, id_string, li, readable_size_html, small, span, tag
from .npc import BasePlugin, Bool, File, Int, PeriodicJob, __version__, command, startfile
from .utils import create_m3u


class Stats(TypedDict):
    """Statistics data structure."""

    file: dict[str, dict[str, Any]]
    user: dict[str, dict[str, Any]]
    day: list[int]


class Plugin(BasePlugin):
    """Upload statistics plugin.

    .. seealso:: :class:`npc.BasePlugin` for more information about the
        plugin class.

    Attributes:
        config (:obj:`Config`): Plugin configuration
        stats (:obj:`upload_stats.Stats`): Statistics data
        empty_stats (:obj:`upload_stats.Stats`): Empty statistics data
        auto_builder (:obj:`upload_stats.npc.PeriodicJob`): Auto builder job
    """

    class Config(BasePlugin.Config):
        """Plugin configuration.

        Note:

            This class inherits form the :class:`npc.BasePlugin.Config` class.

        Attributes:
            stats_file (:obj:`pathlib.Path`): Path to statistics file
            stats_html_file (:obj:`pathlib.Path`): Path to statistics HTML file
            playlist_file (:obj:`pathlib.Path`): Path to playlist file
            backup_folder (:obj:`pathlib.Path`): Path to backup folder
            backup_interval (:obj:`int`): Auto backup interval
            build_interval (:obj:`int`): Rebuild interval
            dark_theme (:obj:`bool`): Dark theme
            auto_refresh (:obj:`bool`): Auto refresh
            automatic_threshold (:obj:`bool`): Automatic threshold
            file_threshold (:obj:`int`): File threshold
            user_threshold (:obj:`int`): User threshold
        """

        stats_file = File("Path to statistics file", default=BUILD_PATH / "stats.json")
        stats_html_file = File("Path to statistics HTML file", default=BUILD_PATH / "index.html")
        playlist_file = File("Path to playlist file", default=BUILD_PATH / "playlist.m3u")

        backup_folder = File("Path to backup folder", default=BUILD_PATH / "backups")
        backup_interval = Int("Auto backup every x hours", default=24)
        build_interval = Int("Rebuild statistics page every x minutes", default=30)

        dark_theme = Bool("Dark Theme", default=True)
        auto_refresh = Bool("Auto refresh statistics page", default=False)

        automatic_threshold = Bool("Automatic threshold", default=True)
        file_threshold = Int("User threshold", default=2)
        user_threshold = Int("File threshold", default=5)

    stats = Stats({"file": {}, "user": {}, "day": [0, 0, 0, 0, 0, 0, 0]})
    empty_stats = stats.copy()
    reset_flag = False

    config: Config

    def init(self) -> None:
        """Initialize the plugin

        .. seealso:: :meth:`npc.BasePlugin.init` for more information.

        * Load the statistics from a file
        * Start the auto builder job
        * Start the auto backup job
        """
        super().init()
        self.load_stats()

        self.auto_builder = PeriodicJob(
            name="AutoBuilder",
            delay=lambda: self.config.build_interval * 60,
            update=self.rebuild_stats_output,
        )
        self.auto_builder.start()
        self.auto_backup = PeriodicJob(
            name="AutoBuilder",
            delay=lambda: self.config.backup_interval * 3600,
            update=self.automatic_backup,
        )
        self.auto_backup.start()

    def load_stats(self) -> None:
        """Load the statistics from a file"""
        self.log.info(f'Loading statistics from "{self.config.stats_file}"')
        try:
            stats = json.loads(self.config.stats_file.read_text())
            self.stats.update(stats)
        except FileNotFoundError:
            self.log.warning(f'Statistics file does not exist yet. Creating "{self.config.stats_file}"')
            self.save_stats()
            return
        except json.JSONDecodeError:
            self.log.error(f'Could not parse statistics file "{self.config.stats_file}".')
            self.window(
                f'Could not parse statistics file "{self.config.stats_file}". Use /up-restore to restor the latest backup or /up-reset to reset the statistics.',
                title="Error loading statistics",
            )
            self.pause_jobs()
            return

    def pause_jobs(self) -> None:
        """Pause all jobs"""
        self.log.debug("Pausing all jobs")
        self.auto_builder.pause()
        self.auto_backup.pause()

    def save_stats(self, path: Optional[Path] = None) -> None:
        """Save the statistics to a file

        Args:
            path (:obj:`pathlib.Path`, optional): Path to the file. Default is None.
        """
        path = path or self.config.stats_file
        self.log.debug(f'Saving statistics to "{path}"')
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            self.log.debug(f'Created missing file "{path}"')
        path.write_text(json.dumps(self.stats))
        self.log.debug(f'Saved statistics to "{path}"')

    @command
    def reset(self) -> None:
        """Start the reset process"""
        self.log.warning("User requested a reset, asking for confirmation.")
        self.window(
            dedent(
                """
                Are you sure you want to reset the statistics?

                Before the reset is performed, a backup will be created.
                Using /restore will restore the latest backup.

                Confirm the reset by using /up-reset-confirm
                Abort the reset by using /up-reset-abort
                """
            ),
            title="Reset Statistics",
        )
        self.reset_flag = True

    @command
    def reset_abort(self) -> None:
        """Cancel the reset process"""
        self.log.warning("User aborted the reset.")
        self.reset_flag = False
        self.window("Reset aborted", title="Reset Aborted")

    @command
    def reset_confirm(self) -> None:
        """Create a backup and reset the statistics"""
        if not self.reset_flag:
            self.log.error("User did not start the reset process. Aborting.")
            self.window("No reset process started (/reset). Aborting.", title="Error")
            return
        self.log.warning("User confirmed the reset. Creating a backup and resetting the statistics.")
        self.backup("reset")
        self.hard_reset()

    def backup(self, reason: str) -> Path:
        """Create a backup of the statistics

        Args:
            reason (:obj:`str`): Reason for the backup

        Returns:
            :obj:`pathlib.Path`: Path to the backup file
        """
        self.log.info(f'Creating a backup for "{reason}"')
        file = self.config.backup_folder / (f"stats-{reason}-{datetime.now().strftime('%Y_%M_%d-%H_%M_%S')}.json")
        self.save_stats(file)
        self.log.info(f'Created a backup at "{file}"')
        return file

    def hard_reset(self) -> None:
        """Reset the statistics to the default values"""
        self.log.info("Resetting statistics")
        self.stats = self.empty_stats.copy()
        self.save_stats()
        self.rebuild_page()
        self.rebuild_playlist()
        self.log.info("Statistics have been reset")

    def automatic_backup(self) -> None:
        """Trigger an automatic backup"""
        self.log.info("Automatic backup triggered")
        self.backup("auto")

    @command(aliases=["stats"])
    def open(self) -> None:
        """Open the statistics page"""
        self.open_stats_page()

    def open_stats_page(self) -> None:
        """Open the statistics page"""
        if not self.config.stats_html_file.exists():
            self.log.error(f'File "{self.config.stats_html_file}" does not exist. Rebuilding statistics page.')
            self.rebuild_stats_output()

        webbrowser.open(str(self.config.stats_html_file))

    @command(aliases=["play"])
    def open_playlist(self) -> None:
        """Open the top 25 uploads playlist file"""
        self.open_playlist_file()

    def open_playlist_file(self) -> None:
        """Open the playlist file"""
        if not self.config.playlist_file.exists():
            self.log.error(f'File "{self.config.playlist_file}" does not exist. Rebuilding playlist.')
            self.rebuild_playlist()

        startfile(str(self.config.playlist_file))

    @command("backup")
    def backup_cmd(self) -> None:
        """Create a backup of the statistics"""
        self.backup("manual")

    @command
    def list_backups(self) -> None:
        """List all backups"""
        self.log.info("Listing all backups")
        backups: List[Path] = list(self.config.backup_folder.glob("stats-*.json"))
        backups = sorted(backups, reverse=True, key=lambda i: i.stat().st_mtime)
        if not backups:
            self.log.error("No backups found")
            self.window("No backups found", title="Error")
            return

        backup_list = "- " + "\n- ".join(map(str, backups))
        self.window(f"Found the following backups:\n{backup_list}", title="Backups")

    @command(parameters=["[backup file]"])
    def restore(self, file: Optional[Union[str, Path]] = None) -> None:
        """Restore the latest backup

        Args:
            file (:obj:`str`, optional): Backup file to restore. Default is None.
        """
        # Backup current stats
        new_backup = self.backup("restore")

        # Choose backup file
        if file:
            file = Path(file)
            if not file.exists():
                file = self.config.backup_folder / file
                if not file.exists():
                    self.log.error(f'Backup file "{file}" not found')
                    self.window(f'Backup file "{file}" not found', title="Error")
                    return
            self.log.info(f'Restoring backup "{file}"')
        else:
            backups: List[Path] = list(self.config.backup_folder.glob("stats-*.json"))
            backups = sorted(backups, reverse=True, key=lambda i: i.stat().st_mtime)
            backups = [file for file in backups if file != new_backup]

            if not backups:
                self.log.error("No backups found")
                self.window("No backups found", title="Error")
                return

            file = backups[0]
            self.log.info(f'Restoring backup "{file}"')

        # Restore backup
        try:
            self.stats = json.loads(file.read_text())
        except json.JSONDecodeError:
            self.log.error(f'Could not parse backup file "{file}"')
            self.window(f'Could not parse backup file "{file}"', title="Error")
            return

        self.save_stats()
        self.rebuild_page()
        self.rebuild_playlist()
        self.log.info("Backup restored")
        self.open_stats_page()
        self.window(f'Backup "{file}" restored', title="Backup restored")

    # === Build ===

    def rebuild_stats_output(self) -> None:
        """Rebuild the statistics page and playlist file"""
        self.rebuild_page()
        self.rebuild_playlist()

    @command("rebuild", parameters=["[user threshold]", "[file threshold]"])
    def rebuild_stats_output_cmd(
        self, user_threshold: Optional[int] = None, file_threshold: Optional[int] = None
    ) -> None:
        """Rebuild the statistics page and playlist file

        Args:
            user_threshold (:obj:`int`, optional): User threshold
            file_threshold (:obj:`int`, optional): File threshold
        """
        self.rebuild_page(user_threshold, file_threshold)
        self.rebuild_playlist()

    @command("rebuild-page", parameters=["[user threshold]", "[file threshold]"])
    def rebuild_page_cmd(self, user_threshold: Optional[int] = None, file_threshold: Optional[int] = None) -> None:
        """Rebuild the statistics page

        Args:
            user_threshold (:obj:`int`, optional): User threshold
            file_threshold (:obj:`int`, optional): File threshold
        """
        self.rebuild_page(user_threshold, file_threshold)

    @command("rebuild-playlist")
    def rebuild_playlist_cmd(self) -> None:
        """Rebuild the playlist file"""
        self.rebuild_playlist()

    def rebuild_page(self, user_threshold: Optional[int] = None, file_threshold: Optional[int] = None) -> None:
        """Rebuild the statistics page

        Args:
            user_threshold (:obj:`int`, optional): User threshold
            file_threshold (:obj:`int`, optional): File threshold
        """
        self.log.info("Rebuilding statistics page")

        if user_threshold or file_threshold:
            self.log.info(f"Creating temporary HTML file with thresholds: user={user_threshold}, file={file_threshold}")
            with NamedTemporaryFile("w", suffix=".html", delete=False) as file:
                file.write(self.build_html(user_threshold, file_threshold))
                self.log.info(f'Temporary statistics page created at "{file.name}"')
                return

        if not self.config.stats_html_file.exists():
            self.log.info(f'File "{self.config.stats_html_file}" does not exist. Creating a new one.')
            self.config.stats_html_file.parent.mkdir(parents=True, exist_ok=True)
            self.config.stats_html_file.touch()

        self.config.stats_html_file.write_text(self.build_html())
        self.log.info(f'Statistics page generated and saved to "{self.config.stats_html_file}"')

    def rebuild_playlist(self, total: int = 25) -> None:
        """Rebuild the playlist

        Args:
            total (:obj:`int`, optional): Top number of files to include in the playlist.
                Default is 25.
        """
        self.log.info(f"Rebuilding playlist with top {total} uploads")
        songs = sorted(self.stats["file"], reverse=True, key=lambda i: self.stats["file"][i]["total"])
        file = self.config.playlist_file
        create_m3u(title=f"TOP #{total}", files=songs, out_file=file, max_files=total)
        self.log.info(f'Playlist generated and saved to "{file}"')

    def build_html(self, user_threshold: Optional[int] = None, file_threshold: Optional[int] = None) -> str:
        """Build the statistics page

        Args:
            user_threshold (:obj:`int`, optional): User threshold
            file_threshold (:obj:`int`, optional): File threshold

        Returns:
            :obj:`str`: HTML page
        """
        self.log.debug("Building statistics page")
        template = (HTML_PATH / "template.html").read_text()

        info: dict[str, Any] = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "BASE": str(REL_HTML_PATH).replace("\\", "/") + "/",
            "DARK_THEME": "checked" if self.config.dark_theme else "",
            "head": "",
            "update": "",
            "summary": self.calculate_summary(),
            "stats_link": self.file_link(self.config.stats_file),
            "playlist_file": self.file_link(self.config.playlist_file, as_base64=True),
            "userranking": self.user_ranking(),
            "fileranking": self.file_ranking(),
            "icons": self.icons(),
        }

        if self.config.auto_refresh and user_threshold is file_threshold is None:
            info["head"] = tag("meta", http_equiv="refresh", content="60")

        if new_version := self._check_update():
            update_url = "https://github.com/Nachtalb/more-upload-stats/releases/latest"

            info["update"] = tag(
                "h4 a",
                "A new update is available. Current: {current} New: {new}".format(
                    current=tag("kbd", __version__), new=tag("kbd", str(new_version))
                ),
                href=update_url,
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

    def calculate_summary(self) -> str:
        """Calculate the statistics summary

        Returns:
            :obj:`str`: HTML summary
        """
        self.log.debug("Calculating summary")
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
        """Calculate the user threshold

        If automatic_threshold is enabled, the 25th percentile is used as the threshold,
        unless the user stats are empty, then 0 is returned.

        Returns:
            int: The user threshold
        """
        if self.config.automatic_threshold:
            if not self.stats["user"]:
                return 0

            # Get the 25th percentile
            uniq_totals = set(map(lambda i: i["total"], self.stats["user"].values()))
            return sorted(uniq_totals)[int(len(uniq_totals) * 0.25)]  # type: ignore[no-any-return]  # Get the 25th percentile
        return self.config.user_threshold

    def user_stats(self, threshold: int = 0) -> str:
        """Create the user statistics table

        Args:
            threshold (:obj:`int`, optional): Threshold to filter the users. Default is 0.

        Returns:
            :obj:`str`: HTML table
        """
        self.log.debug(f"Building user stats with threshold {threshold}")
        html = ""

        # Sort by total uploads
        for username, user_data in sorted(self.stats["user"].items(), key=lambda i: i[1]["total"], reverse=True):
            if user_data["total"] <= threshold:
                continue

            filename = a(
                Path(user_data["last_file"]).name,
                href="#file-" + id_string(user_data["last_real_file"]),
                data_tooltip=f'RP: {user_data["last_real_file"]}\nVP: {user_data["last_file"]}',
                data_tooltip_align="left",
            )

            total_bytes_raw = total_bytes = "-"
            if total_bytes_raw := user_data.get("total_bytes"):  # type: ignore[assignment]
                total_bytes = readable_size_html(total_bytes_raw)

            html += f"""
            <tr id="user-{id_string(username)}">
                <td>{username}</td>
                <td>{user_data["total"]}</td>
                <td sorttable_customkey="{total_bytes_raw}">{total_bytes}</td>
                <td>{filename}</td>
            </tr>"""
        return html

    def file_threshold(self) -> int:
        """Calculate the file threshold

        If automatic_threshold is enabled, the 25th percentile is used as the threshold,
        unless the file stats are empty, then 0 is returned.

        Returns:
            int: The file threshold
        """
        if self.config.automatic_threshold:
            if not self.stats["file"]:
                return 0

            # Get the 25th percentile
            uniq_totals = set(map(lambda i: i["total"], self.stats["file"].values()))
            return sorted(uniq_totals)[int(len(uniq_totals) * 0.25)]  # type: ignore[no-any-return]  # Get the 25th percentile
        return self.config.file_threshold

    def file_stats(self, threshold: int = 0) -> str:
        """Create the file statistics table

        Args:
            threshold (:obj:`int`, optional): Threshold to filter the files. Default is 0.

        Returns:
            :obj:`str`: HTML table
        """
        self.log.debug(f"Building file stats with threshold {threshold}")
        html = ""

        # Sort by total uploads
        for file_path, file_data in sorted(self.stats["file"].items(), key=lambda i: i[1]["total"], reverse=True):
            if file_data["total"] <= threshold:
                continue

            name = a(
                Path(file_path).name,
                data_tooltip=f'RP: {file_path}\nVP: {file_data["virtual_path"]}',
                href="file:///" + file_path,
                target="_blank",
                data_tooltip_align="left",
            )

            total_bytes_raw = total_bytes = "-"
            if total_bytes_raw := file_data.get("total_bytes"):  # type: ignore[assignment]
                total_bytes = readable_size_html(total_bytes_raw)

            file_size_raw = file_size = "-"
            if file_size_raw := file_data.get("file_size"):  # type: ignore[assignment]
                file_size = readable_size_html(file_size_raw)

            last_user = a(file_data["last_user"], href="#user-" + id_string(file_data["last_user"]))

            html += f"""
            <tr id="file-{id_string(file_path)}">
                <td>{name}</td>
                <td>{file_data["total"]}</td>
                <td sorttable_customkey="{total_bytes_raw}">{total_bytes}</td>
                <td sorttable_customkey="{file_size_raw}">{file_size}</td>
                <td>{last_user}</td>
            </tr>"""
        return html

    def file_link(self, file: Union[str, Path], as_base64: bool = False) -> str:
        """Create a file link

        Args:
            file (:obj:`str` | :obj:`pathlib.Path`): File path
            as_base64 (:obj:`bool`, optional): Instead of a file link, use a base64 data
                link. Default is False.

        Returns:
            :obj:`str`: HTML link
        """
        file = Path(file)
        href = f"file:///{file}"

        if as_base64:
            b64 = urlsafe_b64encode(file.read_bytes()).decode("utf-8")
            href = f"data:application/octet-stream;base64,{b64}"

        return a(file.name, href=href, data_tooltip=file, target="_blank", download=file.name)

    def ranking(self, data: List[Tuple[str, int, str]], size: int = 5) -> str:
        """Create a ranking list

        Args:
            data (:obj:`List` of :obj:`Tuple`): Ranking data
            size (:obj:`int`, optional): Number of items to show. Default is 5.

        Returns:
            :obj:`str`: HTML list
        """
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
        """Create a user ranking list

        Returns:
            :obj:`str`: HTML list
        """
        data: List[Tuple[str, int, str]] = [
            (name, user["total"], "#user-" + id_string(name)) for name, user in self.stats["user"].items()
        ]
        return self.ranking(data)

    def file_ranking(self) -> str:
        """Create a file ranking list

        Returns:
            :obj:`str`: HTML list
        """
        data: List[Tuple[str, int, str]] = [
            (Path(path).name, file["total"], "#file-" + id_string(path)) for path, file in self.stats["file"].items()
        ]
        return self.ranking(data)

    def icons(self) -> str:
        """Create CSS for all icons in the images folder

        Returns:
            :obj:`str`: CSS for all icons
        """
        icons = ""
        for icon in (HTML_PATH / "images").glob("*.svg"):
            icons += f'.icon-{icon.stem} {{ background-image: url("file:///{REL_HTML_PATH}/images/{icon.name}"); }}'
        return tag("style", icons.replace("\\", "/"))

    ### === Events ===

    def pre_stop(self) -> None:
        """Stop all jobs before stopping the plugin"""
        self.log.debug("Stopping all jobs")
        self.auto_update.stop()
        self.auto_builder.stop(False)

    def track_file_upload(self, user: str, virtual_path: str, real_path: str) -> None:
        """Track a file upload in the statistics

        Args:
            user (:obj:`str`): User who uploaded the file
            virtual_path (:obj:`str`): Virtual path of the file
            real_path (:obj:`str`): Real path of the file
        """
        self.log.info(f"Tracking file upload: {virtual_path} to {user} at {real_path}")
        file_info = self.stats["file"].get(real_path, {})
        user_info = self.stats["user"].get(user, {})

        try:
            stat = Path(real_path).stat()
        except FileNotFoundError:
            self.log.warning(f'File "{real_path}" not found')
            stat = None
        except Exception as e:
            self.log.warning(f'Could not get file info for "{real_path}": {e}')
            stat = None

        weekday = datetime.now().weekday()

        # Increment uploads per day counter
        self.stats["day"][weekday] = self.stats["day"][weekday] + 1

        # Update file statistics
        self.stats["file"][real_path] = {
            "total": file_info.get("total", 0) + 1,
            "virtual_path": virtual_path,
            "last_user": user,
            "last_modified": stat.st_mtime if stat else 0,
            "file_size": stat.st_size if stat else 0,
            "total_bytes": file_info.get("total_bytes", 0) + stat.st_size if stat else 0,
        }

        # Update user statistics
        self.stats["user"][user] = {
            "total": user_info.get("total", 0) + 1,
            "last_file": virtual_path,
            "last_real_file": real_path,
            "total_bytes": user_info.get("total_bytes", 0) + stat.st_size if stat else 0,
        }
        self.save_stats()
