"""Changes are usually documented with directives in the source code. These are
picked up by the changelog generator to create the changelog file.

Example:
    .. code-block:: python

        def my_function():
            '''
            ​.. versionadded:: 0.1.0 Added my_function
            ​.. versionchanged:: 0.2.0 Changed parameter order
            ​.. versionremoved:: 0.3.0 Removed unused parameter X
            '''
            pass

However, sometimes changes are not documented in the source code, but are still important
enough to be included in the changelog. For example, changes to the build system, or
changes to the documentation build process. These changes are documented in this file.

.. versionchanged:: 3.1.1 Updated :external+npc:doc:`npc <index>` to version :external+npc:ref:`0.3.5`
    Adding support and fixing issues with Nicotine+ version lower than 3.3.0.

.. versionadded:: 3.1.1 Added ``/up-help`` command through :external+npc:ref:`0.3.5`
    which adds a help command like ``/help`` but for N+ versions lower than 3.3.0.

.. versionchanged:: 3.1.0 Updated :external+npc:doc:`npc <index>` to version
    :external+npc:ref:`0.3.4` Fixing log level changes via settings not being
    applied during runtime.

.. versionchanged:: 3.0.0 Implement new `Nicotine+ Plugin Core <https://naa.gg/npc>`_
    developed by yours truly. This is a major change that will allow for more
    flexibility and customization in the future. It may not be 100% stable yet, but
    it's a good start.

"""
