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

If you are on Linux you need Python 3.9+ installed.

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

After enabling the plugin, you can access the statistics by using these commands
in any chat window.

- ``/up-open``: Open the statistics webpage
- ``/up-open-playlist`` Open a playlist of the top 25 uploaded music pieces.

There are many more commands available, you can find them by typing ``/help``.
Or ``/up-help`` on N+ versions below 3.3.0.


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

`LGPL-3.0`_

.. _npc: https://naa.gg/npc
.. _Nicotine+: https://nicotine-plus.github.io/nicotine-plus/
.. _release: https://github.com/Nachtalb/more-upload-stats/releases/latest
.. _juup1ter: https://github.com/juup1ter
.. _Skeleton: http://getskeleton.com/
.. _sorttable: https://www.kryogenix.org/code/browser/sorttable/
.. _smartline: https://www.flaticon.com/authors/smartline
.. _www.flaticon.com: https://www.flaticon.com/
.. _LGPL-3.0: https://github.com/Nachtalb/more-upload-stats/blob/master/LICENSE
