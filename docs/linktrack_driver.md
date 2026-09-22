# LinkTrack Node Frame3 ROS driver

The real-hardware driver reads Nooploop `NLink_LinkTrack_Node_Frame3` packets
from a serial device and publishes the decoded peer ranges as
`uwb_coop_localization/UwbRangeArray`.

## Safety and scope

The driver opens the configured serial port for incoming data only. It does not
send configuration commands, change a LinkTrack parameter, update firmware, or
reset a device. Configure and back up the hardware with the official tool before
using this node.

In addition to the backward-compatible `UwbRangeArray` output, the driver
publishes decoded Frame3 diagnostics on `/uwb/frame3`. The diagnostic message
retains local/system device time, voltage, peer role/ID, distance, FP RSSI, and
RX RSSI. The existing `/uwb/ranges` message and its `NaN` quality convention
remain unchanged.

For two vehicles on one ROS graph, use the namespaced launch file:

```bash
roslaunch uwb_coop_localization vehicle_uwb_driver.launch \
  vehicle_namespace:=car1 \
  port:=/dev/serial/by-id/usb-1a86_USB_Single_Serial_5B2E110223-if00
```

This produces `/car1/uwb/ranges` and `/car1/uwb/frame3`. Run the same launch on
Car2 with `vehicle_namespace:=car2` and Car2's verified stable serial path.
Merely namespacing the ROS node does not rewrite the vehicle vendor's odom/IMU
or TF frames; those must be inspected separately before dynamic recording.

The initial implementation targets the field-verified configuration:

- `DR_MODE0`, `NODE`, `Node_Frame3`;
- 921600 baud;
- one local node and zero or more peer nodes;
- checksum equal to the low eight bits of all preceding frame bytes.

It does not decode the unrelated `ff 02` stream observed while a device was in
`LP_MODE6 / Anchor_Frame0`.

## Serial port selection

The port is deliberately required at launch time. Neither `/dev/ttyACM0` nor
`/dev/ttyCH343USB0` is a stable identity and the driver must not guess which
connected device to use.

The field VM's generic `cdc_acm` driver created a stable
`/dev/serial/by-id/...` link but NAssistant V4.3.0.7 did not list that port. The
temporarily loaded WCH `ch343` driver created `/dev/ttyCH343USB0`, but did not
create a `/dev/serial/by-id` link. Before a vehicle test, provide a reviewed udev
symlink or explicitly pass the currently verified device path.

Example using an explicitly verified port:

```bash
roslaunch uwb_coop_localization uwb_linktrack_driver.launch \
  port:=/dev/ttyCH343USB0
```

## Stationary live validation

For a self-contained bench test, use a local ROS master in every test terminal.
This avoids inheriting a vehicle configuration such as
`ROS_MASTER_URI=http://192.168.0.100:11311` when the vehicle master is offline.
These exports affect only the current terminal and do not modify `.bashrc`:

```bash
export ROS_MASTER_URI=http://127.0.0.1:11311
export ROS_HOSTNAME=127.0.0.1
unset ROS_IP
```

Start the driver with the computer-connected node powered and the peer node
off. First verify that `/uwb/ranges` publishes an empty `ranges` array. Then
power the peer node without restarting the driver and verify that the array
contains the expected peer ID and a finite, non-negative distance:

```bash
rostopic echo -n 1 /uwb/ranges
rostopic hz /uwb/ranges
```

For the field-verified N1/N0 pair, the expected transition is from
`tag_id: node_1` with an empty array to a measurement whose `anchor_id` is
`node_0`. Keep both nodes stationary for this check. Do not mount the hardware
on the vehicle or enable its motors until the stationary topic contents and
rate have been recorded.

Once that transition and an approximately 50 Hz rate have been observed, the
two-node bench gate is complete. Do not repeat it unless hardware configuration,
firmware, driver binding, or serial cabling changes. Proceed to the vehicle in
stages: powered-off mounting inspection, stationary powered acquisition,
hand-pushed acquisition, and only then a low-speed motor test.

## Vehicle connection gate

Mounting the UWB hardware does not authorize motion. Before sending any drive
command, keep the vehicle stationary with motor output disabled and establish
which computer physically owns the P-B USB device. A serial device attached to
the VMware host is not automatically visible on the vehicle computer, and a
device attached to the vehicle computer is not automatically visible inside
the VM.

First verify network reachability and the intended ROS master without launching
the UWB node. Then verify the P-B USB serial identity on the computer that will
run the driver. Only after a stationary ROS acquisition succeeds should the
workflow progress to a hand-pushed test. Motor commands remain a separate,
later gate.

If `ip route get` selects the expected vehicle-facing interface but `ping`
returns `Destination Host Unreachable` from the VM's own address, routing is
already present but layer-2 neighbor discovery received no reply. Do not change
ROS variables to troubleshoot that condition: first inspect the interface link,
address, NetworkManager connection, and neighbor table. Common causes include
an unpowered vehicle computer, a disconnected vehicle Wi-Fi/Ethernet link, a
stale vehicle IP, or a VMware adapter attached to the wrong virtual network.

The rate output should also have approximately 20 ms inter-message intervals.
Repeated `min: 0.000s` and `max: 0.100s` values indicate serial timeout batching,
even when the long-term average is 50 Hz. The driver waits for one byte and then
drains only bytes already buffered to avoid assigning nearly identical ROS
timestamps to several frames delivered in one timeout-sized burst.

Optional launch arguments include `baudrate`, `topic`, `frame_id`, and
`node_prefix`. The default topic is `/uwb/ranges`.

## ROS mapping

For a local N1 frame containing a range to N0, the published message uses:

- `tag_id: node_1`;
- `ranges[0].anchor_id: node_0`;
- `ranges[0].range`: decoded metres;
- `ranges[0].quality: NaN` because the existing message has no RSSI fields and
  no validated RSSI-to-quality conversion is available.

The word `anchor_id` is inherited from the hardware-independent simulation
message. In DR mode the peer is another equal NODE, not necessarily a fixed
Anchor. Consumers must not interpret it as a surveyed Anchor without separate
configuration.

## Parser behavior

The incremental parser:

- accepts arbitrarily split serial reads;
- searches for the `55 05` prefix;
- reads the little-endian frame length;
- validates the length against the number of 7-byte node blocks;
- validates the additive checksum;
- resynchronizes after garbage or a damaged frame;
- decodes little-endian unsigned times and voltage;
- decodes the signed 24-bit distance in metres;
- decodes `fp_rssi` and `rx_rssi` using the documented `-2` scale.

Run its hardware-independent tests with:

```bash
python -m unittest discover \
  -s ros_ws/src/uwb_coop_localization/test -v
```

The tests include three real 29-byte frames supplied from the successful field
capture, plus fragmented input, checksum failure, garbage resynchronization, and
signed 24-bit decoding cases.

## Remaining field validation

Before mounting the system on a moving vehicle:

1. replay or parse the complete retained 14,544-byte capture in the target VM;
2. build the catkin workspace under Python 2.7;
3. verify `/uwb/ranges` with both nodes stationary;
4. log a tape-measured static distance sequence;
5. perform a hand-pushed vehicle test before enabling its motors.

Two nodes provide one inter-node range, not a unique 2D position. Real 2D
localization still requires enough surveyed reference nodes with suitable
geometry.
