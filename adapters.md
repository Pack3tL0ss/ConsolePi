# Lame!! USB to Serial Adapters

*Technically all adapters should work, however some USB to Serial adapter vendors get cheap and either don't burn in a serial numbers or burn the same serial number over and over. This can create challenges for the OS to match configuration to the same physical adapter between reboots. Navigating which devices behave nicely can be a challenge.*

***I recommend FTDI based adapters*** as I've found those typically already have a serial #, but in the few cases (all were development borads) where there was not a serial # the FTPROG utility (see below) allowed me to easily write a serial # to the chip/eeprom.

# Fixing a Lame Adapter

In **some** cases it is possible to use a utility from the chipset vendor to write a serial number to the eeprom on the adapter.

[FTDI FTPROG Utility](https://ftdichip.com/utilities/#ft_prog)
[Prolific EEWriter Utility](http://www.prolific.com.tw/UserFiles/files/PL2303TA-HXD-EA_EEWriter_v2200.zip)

> A note on Prolific: I've come across multiple prolific based adapters that do not have a serial number, and I have not been able to update them with the utility listed below (only applicable to certain chips).  Additionally the process of updating prolific chips requires 6.5v (usb port is 5v) to the adapter, and the utility doesn't have scroll-bars or allow re-sizing, so that's fun on a laptop.


# Lame adapters (No Serial #)

 - Tripp Lite [U009-006-RJ45-X](https://www.amazon.com/Tripp-Lite-Rollover-Compatible-U009-006-RJ45-X/dp/B07ZZG15HP)
   - This adapter shows as a PL2303 but does not have a serial number.
   - I would expect the same for any models that start with U009-.
   - Unable to update using EEWriter utility.
 - Prolific Technology PL2303 Serial Port (Generic) Not overly useful, but it was a generic USB to DB9 short black adapter.

# Recommended / Known Working Adapters

- [Tripp Lite USB to RJ45 (U209-006-RJ45-X)](https://www.amazon.com/gp/product/B016A4CAF2/ref=ppx_yo_dt_b_asin_title_o00_s01?ie=UTF8&psc=1)

> This is just one of many FTDI adapters that work just fine.  Most FTDI based adapters I've purchased do have a serial #.  For the few that don't FTPROG.exe has worked to write a serial number to the eeprom.

# Options when using a lame adapter

The `rn` (rename) menu from within `consolepi-menu` and the `consolepi-rename` command will detect lame adapters and provide a couple of options for mapping them.
1. The adapter can be mapped based on vendor/model (vid/pid) alone.  Anytime an adapter of this type is plugged into any port it will adopt the chosen alias.  This is a viable opiton if you only have 1 lame adapter per vid/pid combination.
2. The adapter can be mapped to the physical USB port it's plugged in to.  With this option anytime an adapter of the same vendor/model (vid/pid) is plugged into the port it will adopt the chosen alias.
    > This is the exact port, even if a hub is in use, it would be mapped to the port it's in on the hub.

[<< README](README.md)