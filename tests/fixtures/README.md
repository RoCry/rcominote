# USB parser oracle

`ioreg-hiveton.plist`: descriptor fields retained from the actual 2026-10-12
`ioreg -r -c IOUSBHostDevice -l -w 0 -a` capture, before CoMi unplug.
Hiveton is a separate device, deliberately chosen to avoid attributing it to CoMi.
Unrelated registry/process fields and device trees removed; retained values unchanged.

Captured failure: `system_profiler SPUSBDataType -json` returned an empty array
while IOKit showed 16 physical USB devices. `plutil` JSON conversion then failed
because raw plist contains binary `UsbDeviceSignature`. Interface nodes repeat
VID/PID, so enumerating every node containing those keys double-counts hardware.
The fixture preserves both interface nodes and the binary signature.
