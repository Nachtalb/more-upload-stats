More Upload Statistics
======================

A small plugin for `Nicotine+`_ 3.1+ to create more detailed upload
statistics.

⚠ No data previous to enabling this plugin will be available.

⚠ Some data in the statistics may be hidden to not create an unnecessarily
huge page. You can disable this by disabling auto thresholding in the
preferences and setting the manual thresholds to 0.

.. figure:: https://raw.githubusercontent.com/Nachtalb/more-upload-stats/master/html/images/screenshot.jpg
   :alt: screenshot

Installation
------------

Click the burger menu next to the gear icon at the top right of your
window.

Click "About Nicotine+"

If the version number is above 3.1.0, continue to the next step.
If not, update here: https://github.com/nicotine-plus/nicotine-plus/releases/latest/

If you are on Linux you need Python 3.8+.

Open Nicotine+ settings, go to *General > Plugins* and click *+ Add
Plugins*. After that download the latest `release`_ and extract it into
the plugins folder.

Remove the version from the folder name. The folder name must stay the
same across version upgrades otherwise you will loose any changed
settings.

Now you can enable the *Upload Statistics* plugin in the previously
opened plugin settings.


Usage
-----

- Type ``/up`` into a chat message and hit enter.

- If you want to temporarely disable or change the thresholds you can
  do so like this: ``/up 0 2``. The values are user and file
  threshold respectively.

- Use ``/up-reset`` to reset the statistics (a backup will be created beforhand).


Settings
--------

+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Name                | Function                                                                                | Default                       |
+=====================+=========================================================================================+===============================+
| Check for Updates   | Check for updates on start and periodically                                             | Enabled                       |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Quieter             | Quiet down a bit and stop filling the console with messages.                            | Disabled                      |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Raw statistics file | JSON file where containing the raw data                                                 | ``build/stats.json``          |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Statistic page file | HTML file presenting the data in a human readable way                                   | ``build/index.html``          |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| M3U Playlist file   | M3U playlist file of the top 25# uploaded files                                         | ``build/playlist.m3u``        |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Dark Theme          | Enable / Disable dark theme                                                             | Enabled                       |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Auto refresh        | Automatically refresh the statistics page every minute                                  | Disabled                      |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Auto regenerate     | Automatically regenerate statistics page every X minutes                                | 30min                         |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| Auto threshold      | Automatically set a threshold respective to the gathered data.                          | Enabled                       |
|                     | Data under the threshold will be hidden from the statistics page.                       |                               |
|                     | Overrides both user and file threshold when enabled.                                    |                               |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| User threshold      | Fix threshold for users.                                                                | 2                             |
|                     | Only users who downloaded more files than this will be shown on the statistics page.    |                               |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+
| File threshold      | Fix threshold for files.                                                                | 5                             |
|                     | Only files that have been uploaded more than this will be shown on the statistics page. |                               |
+---------------------+-----------------------------------------------------------------------------------------+-------------------------------+


Contributing
------------

Pull requests are welcome.


Contributors
^^^^^^^^^^^^

`juup1ter`_


Credits
-------

Created with: `Skeleton`_ | `sorttable`_
Icons made by `Smartline`_ from `www.flaticon.com`_

License
-------

`MIT`_

.. _Nicotine+: https://nicotine-plus.github.io/nicotine-plus/
.. _release: https://github.com/Nachtalb/more-upload-stats/releases/latest
.. _juup1ter: https://github.com/juup1ter
.. _Skeleton: http://getskeleton.com/
.. _sorttable: https://www.kryogenix.org/code/browser/sorttable/
.. _smartline: https://www.flaticon.com/authors/smartline
.. _www.flaticon.com: https://www.flaticon.com/
.. _MIT: https://github.com/Nachtalb/more-upload-stats/blob/master/LICENSE
