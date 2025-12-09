Changelog
=========

3.2.1
-----

* Changed: [:mod:`upload_stats.changes`] Fix accidentally restoring the backup before the restore -> nothing restored

3.2.0
-----

* Changed: [:mod:`upload_stats.changes`] Save backups as compressed gzip to save on space.
* Changed: [:mod:`upload_stats.changes`] Fix issues building page due to missing playlist.
* Changed: [:mod:`upload_stats.changes`] Update :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.5.0`

3.1.5
-----

* Changed: [:mod:`upload_stats.changes`] Updated :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.4.1` Fixing proper unloading of the plugin and thus the ``/up-reload`` command.

3.1.4
-----

* Changed: [:mod:`upload_stats.changes`] Add clarification for various settings.
* Changed: [:mod:`upload_stats.changes`] Updated :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.4.0`

3.1.3
-----

* Changed: [:mod:`upload_stats.changes`] Updated :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.3.6` Fixing issues with windowed messages not being displayed on Nicotine+ versions lower than 3.3.0.

3.1.2
-----

* Changed: [:meth:`upload_stats.Plugin.build_html`] Added version of Plugin, Nicotine+ and Python to the page.
* Changed: [:meth:`upload_stats.Plugin.icons`] Fixed path to images. Making icons work again.
* Added: [:meth:`upload_stats.Plugin.settings_changed`] Rebuild page on theme change.

3.1.1
-----

* Changed: [:func:`upload_stats.html.tag`] Prefix arguments with _ to avoid conflicts with html attributes. Fixing the <meta http-equiv="refresh" content="..." /> tag issue.
* Changed: [:mod:`upload_stats.changes`] Updated :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.3.5` Adding support and fixing issues with Nicotine+ version lower than 3.3.0.
* Added: [:mod:`upload_stats.changes`] Added ``/up-help`` command through :external+npc:ref:`0.3.5` which adds a help command like ``/help`` but for N+ versions lower than 3.3.0.

3.1.0
-----

* Added: [:meth:`upload_stats.Plugin.upload_finished_notification`] Fixed no file uploads being tracked by adding missing event listener.
* Changed: [:mod:`upload_stats.changes`] Updated :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.3.4` Fixing log level changes via settings not being applied during runtime.

3.0.0
-----

* Changed: [:mod:`upload_stats.changes`] Implement new `Nicotine+ Plugin Core <https://naa.gg/npc>`_ developed by yours truly. This is a major change that will allow for more flexibility and customization in the future. It may not be 100% stable yet, but it's a good start.
