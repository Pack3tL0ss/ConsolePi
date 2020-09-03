# ConsolePi ZTP Orchestration

**This feature has currently only been tested with ArubaOS-CX switches by Aruba Networks, mileage may very beyond that**

## ZTP Configuration
- Place templates (jinja2) and variable files in `/etc/ConsolePi/ztp`
    - Templates should have `.j2` extension
    - Variable Files should have `.yaml` extension
    > consolepi-ztp currently supports yaml format for variables, it's planned to expand this with future releases to allow for other formats.
- Add `ZTP:` section to `ConsolePi.yaml` configuration file which has the following format:

### Defining Devices by System MAC
```yaml
ZTP:
  <system-mac-of-device>:
    oobm: Optional bool(true|false) Default: false.  Use if using oobm (will generate rules using system-mac +1) Allows you to use MAC from barcode without adjusting for oobm.
    template: Optional string(filename of template i.e. `6300.j2`), Default: Will look for file named mac.j2 formatted with no delims.  Otherwise if you define "aa:bb:cc:dd:ee:ff" the script will look for aabbccddeeff.j2
    # NOTE: if using colon delimted mac format in a yaml you need to use quotes (") to keep the yaml valid
    variables: Optional string(name of variable file i.e. `aabbccddeeff.yaml`) Default: Follows same rules as template file with .yaml instead of .j2 + if no <mac-addr>.yaml exists will check for common variable file `variables.yaml` with a key matching the mac-addr (no delims).
    image: Optional string(image file name (Tested for ArubaOS-CX switches)) Default: None
    cli_user: Optional string(SSH User used for post configuration command execution if defined) Default: None
    cli_pass: Optional string(SSH Password used for post configuration command execution if defined) Default: None
    cli_post: Optional list of strings(Post configuration commands to be executed via SSH/CLI) Default: None
```

When the device is defined by MAC address `consolepi-ztp` will generate config files using `<mac-address>.cfg` for each device.  Using Template/variables based on what is specified or [Template/Variable File Selection Rules](#templatevariable-file-rules) if not specified.

### Ordered ZTP

ZTP can also create rules based on a fuzzy match of the Vendor Class ID provided by the device in the ZTP request, creating and sending configurations in the order those devices are configured.

**For example:**

```yaml
ZTP:
  ordered:
    6200:
      - template: 6200F.j2
        variables: 6200F_1.yaml
        cli_post: ["copy tftp://10.30.112.1/6200-vsf.cfg running vrf mgmt", "conf t", "led locator flash", SLEEP 10, "led locator off", "end"]
        cli_user: cxadmin
        cli_pass: aruba123
      - template: 6200F.j2
        variables: 6200F_2.yaml
        cli_post: ["conf t", "led locator flash", "vsf renumber-to 2", "y"]
        cli_user: cxadmin
        cli_pass: aruba123
```

Given the example above:
- `consolepi-ztp` will create:
  - `6200_1.cfg` based on Template `6200F.j2` using variables from `6200F_1.yaml`
  - `6200_2.cfg` based on Template `6200F.j2` using variables from `6200F_2.yaml`
- DHCP will be configured such that `6200_1.cfg` will be returned in the DHCP response as DHCP option 67 (boot file name) to any device with `6200` in the vendor class ID.
- Once `6200_1.cfg` has been requested/downloaded by a device via TFTP, DHCP will adjust on the fly so that:
  - `6200_2.cfg` will be returned in the DHCP response as DHCP option 67 (boot file name) to any device with `6200` in the vendor class ID.
  - `6200_1.cfg` Will be mapped to the MAC address of the device that requested it via DHCP (for the sake of retries)

*The ordered ZTP function allows you to configure ZTP by fuzzy match of Vendor Class ID without knowing the system MAC address.  When Multiple devices of the same model/vendor-class are defined the configurations are assigned in order, so you would plug in the switch you want to get the 1st config, then plug in the next switch, and so on.*

### Config Creation Only (No ZTP/DHCP orchestration)

ConsolePi also supports a special use case where you define the template/variable files, but set `no_dhcp: true`.  This instructs `consolepi-ztp` to create the cfg file, but not to create any related ZTP/DHCP rules.

**For Example:**
```yaml
ZTP:
  6200-vsf:
    template: 6200F.j2
    variables: 6200F-VSF.yaml
    no_dhcp: true
```
> NOTE: if `no_dhcp:` is not set to `true` (which is the default if it's not provided at all).  The only valid keys under `ZTP:` are either valid MAC addresses or `ordered:`.
>
> The `cli_post:` key (see [Post Configuration CLI Execution](#post-configuration-cli-execution)) is still valid for `no_dhcp:` configurations, if configured ConsolePi will attempt to SSH to the IP that requested the cfg and execute those commands.  However no DHCP/ZTP rules are created to automatically have a device download the cfg, so that would be done either manually or via a `cli_post:` command (see `883a30aabb60` in the [Comprehensive Example](#comprehensive-example))

With the Configuration above `consolepi-ztp` will result in `6200-vsf.cfg` being created using `6200F.j2` as the template with variables from `6200F-VSF.yaml`.  However nothing will be orchestrated regarding DHCP/ZTP rules.

### Template/Variable File Rules

The `consolepi-ztp` command which configures ZTP based on the configuration does not require the template/variable file be specified.  When `template:` and/or `variables:` are not specified the following highlights the rules used to look for the template/variable files.

Given the following (device defined by MAC address):
```yaml
ZTP:
  aabbccddeeff:
```
- **TEMPLATE:** The script will look for `aabbccddeeff.j2`
- **VARIABLES:** The script will (in the order listed):
    - look for `aabbccddeeff.yaml`
    - look for a shared variables file `variables.yaml` under `aabbccddeeff:` key

  > It is valid to specify `variables: variables.yaml` (shared variables file), the script will go straight to looking for the appropriate device key inside `variables.yaml`.

Given the following:
```yaml
ZTP:
  aabbccddeeff:
    template: 6200F.j2
```
- **TEMPLATE:** The script will look for `6200F.j2` as it was defined in the config.
- **VARIABLES:** The script will (in the order listed):
    - look for `aabbccddeeff.yaml`
    - look for `6200F.yaml`
    - look for a shared variables file `variables.yaml`:
        - under `aabbccddeeff:` key
        - under `6200F` key

## Comprehensive Example

```yaml

ZTP:
  6200-vsf:
    template: 6200F.j2
    variables: 6200F-VSF.yaml
    no_dhcp: true
  6300-vsf:
    template: 6300M.j2
    variables: 6300M-VSF.yaml
    cli_user: cxadmin
    cli_pass: p@ssW0rd
    cli_post: ["conf t", "led locator fast_blink", SLEEP 10, "led locator off"]
    no_dhcp: true
  64e881aabb50:
    oobm: true
    template: 6300M.j2
    variables: variables.yaml
    image: ArubaOS-CX_6400-6300_10_05_0001.swi
    cli_user: cxadmin
    cli_pass: p@ssW0rd
    cli_post: ["conf t", "led locator flash", SLEEP 10, "led locator off"]
  883a30aabb60:
    oobm: true
    template: 6300-vsf-base.j2
    variables: 6300-vsf-base1.yaml
    image: ArubaOS-CX_6400-6300_10_04_3011.swi
    cli_user: cxadmin
    cli_pass: p@ssW0rd
    cli_post: ["conf t", "led locator flash", "do copy tftp://10.30.112.1/6300-vsf.cfg running vrf mgmt", "SLEEP 5", "led locator off"]
  883a30aabb70:
    oobm: true
    template: 6300-vsf-base.j2
    variables: 6300-vsf-base2.yaml
    image: ArubaOS-CX_6400-6300_10_04_3011.swi
    cli_user: cxadmin
    cli_pass: p@ssW0rd
    cli_post: ["conf t", "led locator flash", "vsf renumber-to 2", "y"]
  ordered:
    6200:
      - template: 6200F.j2
        variables: 6200F_1.yaml
        cli_post: ["conf t", "led locator flash", SLEEP 1, "led locator off", "end", "copy tftp://10.30.112.1/6200-vsf.cfg running vrf mgmt"]
        cli_user: cxadmin
        cli_pass: p@ssW0rd
      - template: 6200F.j2
        variables: 6200F_2.yaml
        cli_post: ["conf t", "led locator flash", "vsf renumber-to 2", "y"]
        cli_user: cxadmin
        cli_pass: p@ssW0rd
    2530:
      - template: 2530a.j2
```

## Post Configuration CLI Execution

*Currently only validated with ArubaOS-CX switches*

`consolepi-ztp` supports Post Configuration command execution via SSH.  The optional `cli_post:` key supports a list of strings representing the commands/text to be executed via CLI after the configuration has been sent.

> When `cli_post:` is defined, `cli_user` and `cli_pass` are required.

If `cli_post:` is defined, ConsolePi will login to the device via SSH and send the strings/commands in the order provided.
> A special command exists for `SLEEP` (all caps) this in not sent to the switch, it's used to place a delay prior to the execution of the next command.  It uses the same format for args as the bash builtin `sleep` (it's actually converted to lowercase and sent to bash with the provided arguments).

## Configuration/Image File Location

Generated Configuration Files are placed in the tftp root directory `/srv/tftp`

Any `image:` defined in the config, should be placed in that directory.

> Image File Download has currently only been tested, and uses the format required by ArubaOS-CX switches (DHCP option 43, encapsulated/sub-option 145)

## Let's do Some ZTP

Once the desired configuration for ZTP has been configured in `ConsolePi.yaml` and the appropriate jinja2 Templates and yaml variable files are placed in `/etc/ConsolePi/ztp`.  ZTP can be configured by issueing the `consolepi-ztp` command.

With No arguments provided `consolepi-ztp` will:
- Prompt user for necessary configuration details related to ConsolePi-ZTP
- Store the current state of your ConsolePi (as it relates to this function), as the ZTP function will enable `wired-dhcp` if not already enabled, and will stop/disable the `tftpd-hpa.service` if installed/enabled.  Storing the pre-ZTP state allows `consolepi-ztp -end` to restore the pre-ZTP state when you are done with ZTP.
- Will generate cfg files based on jinja2 templates / variable files defined in the config (or derived based on rule).
- Will generate DHCP configuration rules for ZTP
- Will then prompt the user / give the option to start ZTP, Prior to this point (and if the user choses N/No) to the prompt.  Services are still in the pre-ZTP state.  Otherwise DHCP/TFTP etc. are in whatever state they where when you ran `consolepi-ztp`.
- If "y/yes" to the above prompt:
  - `tftpd-hpa.service` (in.tftpd) is disabled/stopped if it has been installed
  - `wired-dhcp` is enabled/started or reloaded whichever applies based on current state.
  > tftpd-hpa is one of the optional utilities available via `consolepi-extras`, for ZTP we use dnsmasq's built-in tftp server to aid in the orchistration.The dnsmasq tftp is less ideal outside of ZTP given it only allows for file download, not upload.

> To reset ZTP orchestration (fresh run) simply run `consolepi-ztp` again.  It will re-create the configs & DHCP/ZTP rules and re-start the process.

### consolepi-ztp Arguments

```text
USAGE: consolepi-ztp [OPTIONS]
  No arguments: Generate Configuration templates based on config, and prep DHCP for ZTP
  -start|-S:  Start DHCP for ZTP (only necessary if you chose not to start DHCP on initial run of consolepi-ztp)
  -end|-e:    Reset ConsolePi to pre-ztp state (DHCP back to orig state, revert back to tftpd-hpa if installed...)
  -show|-s:   Show current DHCP configuration
  -j2|-c:     Generate configuration templates only, do not prep DHCP for ZTP
  -watch|-w:  Launch byobu(tmux) session with logs and pcap to monitor ZTP progress
              CTRL-C then exit each pane to leave the tmux session or use byobu or tmux sequences
  --help:     Display this help output.
```
> The `-watch|-w` options require packages byobu and tcpdump.  It launches a split-screen that displays ConsolePi-Logs (which will show any ZTP activity), and tcpdump packet capture (filtered on DHCP/TFTP) so you can view activity in real-time.
>
> At the time of this writing you are not prompted to install those packages... so `apt update && apt install byobu tcpdump` would be necessary for this command to work (if not already installed).  Alternatively you can simply watch the logs for activity (`consolepi-logs -f`)

## Custom Parsers

The jinja2 templating language is very powerful, but there are cases where it may be easier to parse variable content via Python allowing more flexibility in how you define the variables without placing more complex loops/conditionals/sets in the template.

`consolepi-ztp` supports this by attempting to import Parsers class from an optional parsers.py which needs to be placed in `/etc/ConsolePi/ztp/custom_parsers`.  Then sending the dictionary representing the variables for each template to that parser, if succesful the dictionary is set to whatever is placed in the `out` attribute of the class.


- This is optional the lack of a parser doesn't impact ZTP
- There are 3 class attributes that should be defined in the parser class:
    - `ok`: set to True if everything went OK, False if there was some kind of error, which will lead to the variable dict remaining unchanged.
    - `out`: This is the variable dict resulting from the custom parser, and what is then used to generate the cfg based on the template (given ok mentioned above is set to True)
    - `error`: The error you want displayed/logged in the event you set ok to False

Example (refer to `/etc/ConsolePi/ztp/custom_parsers/parsers.py.example`):
- The example Parser provided allows interfaces in the variables file to be set in mass based on range or set or combination, and will build each interface with the resulting combined set of lines.
- Given this in the yaml file used for Template variables for a devive:
```yaml
...
  interfaces:
    ...
    - port: 1/1/3 - 1/1/48, 2/1/3 - 2/1/48
      lines:
        - vlan access 40
    - port: 1/1/13-1/1/24, 2/1/13-2/1/24
      lines:
        - aaa authentication port-access allow-lldp-bpdu
        - aaa authentication port-access client-limit 5
        - aaa authentication port-access dot1x authenticator enable
        - aaa authentication port-access mac-auth enable
```
The resulting config stanza for inteface 1/1/13 ends up being:
```
interface 1/1/13
    vlan access 40
    aaa authentication port-access allow-lldp-bpdu
    aaa authentication port-access client-limit 5
    aaa authentication port-access dot1x authenticator enable
    aaa authentication port-access mac-auth enable
```
The template can then simply loop through those config lines:
```
{% if interfaces %}
    {% for i in interfaces %}
interface {{ i }}
        {% for line in interfaces[i] %}
    {{ line }}
        {% endfor %}
    {% endfor %}
{% endif %}
```

The same result can be accomplished with either a more complex Template file or by repeating the same values multiple times in the variable file (for different interfaces), but with this custom parser we can simplify both.

> If you create a custom_parser you believe would be useful, consider inegrating it into the current parsers.py.example and submitting a pull request.
