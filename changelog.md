# CHANGELOG

- ConsolePi remote discovery via mdns, or sync to Google Drive
- Power Outlet Control, via relay attached to GPIO or network connected tasmota flashed wifi smart-outlet.  Power on automatically when attempting to connect to console session (via `consolepi-menu`), or toggle via power sub-menu (`consolepi-menu`)
- consolepi-menu adapter connection parameters (baud, flow, parity, data-bits) are now extracted from the associated definition in ser2net.conf if one exists, if it doesn't defaults are used (which can be changed via menu option c)
- Added new option 's' to menu which allows you to connect to the shell on any reachable remote ConsolePis
- Added new quick commands and an option to delete a remote ConsolePi from the local cloud cache via ```consolepi-remotes```
    <br>**8/19/2019**
- remote connections are now established through proxy script, which will prompt/kill a previous hung session.
    - Bonus, the proxy script also adds support for auto-power-on for devices linked to outlets on the remote system (having them appear in a power sub-menu will come later once I build out the API further)
-  Added override function for most system files involved... So Custom system files won't be backed up and replaced during `consolepi-upgrade`
-  Added option to install and configure a tftp server.
    <br>**9/10/2019 ~ MAJOR UPDATE**
-  Menu will now allow user to purge host key from known hosts and retry connection when connecting to a remote ConsolePi who's SSH key has changed.
-  Menu Auto-sizing with multiple cols based on terminal size.  Currently will place multiple remotes in different Cols if warranted (still 1 col if enough space vertically).
- Added Support for Digital Loggers Web Power Switches (both the newer ones with API and older models).  Separate menu for DLI outlets, the existing power menu remains for linked outlets (The existing power menu will evolve, still considering best options for how to display defined but not linked, different types, etc.)
- Incorporated spinners from [Halo](https://github.com/manrajgrover/halo) during load and update operations.
- Any information or error messages now display in an information pane that populates the bottom of the menu if any errors are encountered
- Changed URI for a couple of API methods (so all match the key field in the dict they reference)
- lots of other little tweaks
<br>**11/07/2019**
- New rename function directly from menu.  Rename adapters already defined by `consolepi-addconsole` (or manually) or adapters that have never been defined.

### DEC 2019 *Major Update*
- refactored the menu formatter.  When multiple ConsolePis are clustered it will populate the colums in a more intuitive way
    > This is still evolving, but an improvement.  
- Completely Replaced consolepi-addconsole function with more capable option which is also available in the menu
    - Accomodates a couple of problematic adapters.  Multi-Port pig-tail with a single serial # and adapters that lack a serial #
        however the latter is not tested yet, and it's a compromise, that essentially maps the USB port (any serail adapter plugged into the port would 
        use the assigned alias)
- FIX TTY SIZING!! Prior to this update, if the device you connect to resized the terminal smaller than your native tty size you were stuck with that after disconnecting until you resized manually using stty or a similar mechanism.  That is no longer necessary, on exit of any serial session the display is automatically resized based on the terminals available rows/cols.
- Optional Utilities Selector presented during consolepi-install / consolepi-upgrade
    - This installs/uninstalls optional packages useful for many ConsolePi users.
    The packages currently included:
        - tftpd: (with ability to read/write), this actually was there prior, but moved to this new menu
        - lldpd: this is useful as another mechansim to get the IP of the ConsolePi by querying the switch you've plugged it into.
        - ansible: Useful if you want to tinker with Ansible.  Not configured yet, the script just installs it.