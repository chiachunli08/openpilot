# SPAS offline control-function test

Visuals now includes a 3–8 second duration setting (default 7), separate left
and right offline test buttons, and Stop. Status explicitly says no CAN output.
The production `create_spas_messages` function is called with an in-memory
recording packer. The UI shows its SPAS2 value and the remaining test duration.
Timeout, Stop and leaving Visuals reset the request to neutral. Only duration
is persisted; requests are not saved or sent when the UI restarts.

This is an offline unit-test interface, **not physical turn-signal control**.
It does not enable CANFD_ENABLE_BLINKERS, disable any ECU, publish carControl
or sendcan, bypass Panda checks, or encode a CAN frame. No lamp animation is
used as evidence of a successful physical operation. SPAS values are 3 for
left, 4 for right, and 0 for neutral. Both flags select left in the production
function; the UI permits only one direction at a time.

The current Hyundai CAN FD safety transmit lists do not include SPAS1 0x165
or SPAS2 0x16A. Enabling the existing blinker flag also invokes ECU communication
control at 0x7B1 during initialization. A verified vehicle-specific protocol,
restoration behavior and constrained safety integration are still needed
before physical operation can be enabled. A detected lamp status alone does
not establish those capabilities.

Run `python -m unittest discover -s openpilot/selfdrive/ui/tests -p test_spas_bench.py`
with the repository's opendbc submodule present. Tests extract and execute the
actual production function from that submodule, compare its builder calls
with the pinned DBC, and exercise the countdown using a fake clock.
They do not validate native CAN packing, checksums, hardware transmission or
lamp response. Device UI rendering has not been tested.
