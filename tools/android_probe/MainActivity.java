package site.rocry.rcominote.probe;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.view.WindowManager;
import android.widget.TextView;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Fixed owned-device read-only experiment. No arbitrary commands, OTA or Internet. */
public final class MainActivity extends Activity {
    private static final String MAC = "50:C0:F0:AE:7C:0E", SERIAL = "C261CF0430";
    private static final UUID BS = uuid("0000e5e0-0000-1000-8000-00805f9b34fb");
    private static final UUID BW = uuid("0000e5e1-0000-1000-8000-00805f9b34fb");
    private static final UUID BN = uuid("0000e5e2-0000-1000-8000-00805f9b34fb");
    private static final UUID LS = uuid("e49a3001-f69a-11e8-8eb2-f2801f1b9fd1");
    private static final UUID LW = uuid("e49a3002-f69a-11e8-8eb2-f2801f1b9fd1");
    private static final UUID LN = uuid("e49a3003-f69a-11e8-8eb2-f2801f1b9fd1");
    private static final UUID CCCD = uuid("00002902-0000-1000-8000-00805f9b34fb");
    private static final byte[] PREPARE = unhex("1d108105000002000100");
    private static final byte[] START = unhex("1d108105000002002000");
    private static final byte[] HELP = unhex("1d1081070001040068656c70");
    private static final byte[] STOP = unhex("1d108105000002002100");
    private static final byte[] ACK = unhex("1d108107007f0400a0860100");
    private final Handler handler = new Handler(Looper.getMainLooper());
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic boyiWrite, boyiNotify, logWrite, logNotify;
    private FileOutputStream output;
    private TextView view;
    private String mode, run, stage = "setup", error, operation;
    private boolean connected, inFlight, writeDone, responseSeen, started, stopAttempted;
    private boolean cleanup, finished, ended, persistenceFailed, stopConfirmed;
    private int stageToken, ackCount, expectedAcks, rows, written, mtu = 23;
    private byte[] pending = new byte[0], initialInfo, reply;
    private long origin;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        view = new TextView(this);
        view.setPadding(24, 48, 24, 24);
        setContentView(view);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        try {
            mode = getIntent().getStringExtra("mode");
            run = getIntent().getStringExtra("run");
            require("info".equals(mode) || "help".equals(mode), "Intent mode must be info or help");
            require(run != null && run.matches("[a-zA-Z0-9_-]{1,64}"), "Invalid run name");
            File file = new File(getFilesDir(), run + ".jsonl");
            require(file.createNewFile(), "Refusing existing run file");
            output = new FileOutputStream(file, false);
            origin = SystemClock.elapsedRealtimeNanos();
            emit("session", "mode", mode, "run", run, "mac", MAC, "serial", SERIAL,
                "sdk", Build.VERSION.SDK_INT, "model", Build.MODEL, "wall_ms", System.currentTimeMillis());
            require(checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED,
                "BLUETOOTH_CONNECT permission required before launch");
            BluetoothManager manager = getSystemService(BluetoothManager.class);
            BluetoothAdapter adapter = manager.getAdapter();
            require(adapter != null && adapter.isEnabled(), "Bluetooth is unavailable or disabled");
            handler.postDelayed(() -> fail("55-second capture deadline"), 55000);
            handler.postDelayed(() -> { if (!finished) { fail("60-second hard deadline"); finish(false); } }, 60000);
            setStage("connect");
            inFlight = true;
            operation = "connect";
            emit("api", "name", "connectGatt", "transport", "LE", "phy", "1M");
            gatt = adapter.getRemoteDevice(MAC).connectGatt(this, false, callback,
                BluetoothDevice.TRANSPORT_LE, BluetoothDevice.PHY_LE_1M_MASK);
            require(gatt != null, "connectGatt returned null");
        } catch (Exception e) { fail(e.toString()); }
    }

    private void setStage(String next) {
        stage = next;
        int token = ++stageToken;
        emit("stage", "name", next);
        handler.postDelayed(() -> { if (!finished && !cleanup && token == stageToken) fail("Timeout: " + next); }, 7000);
    }

    private void event(String name, long timestamp, Runnable action, Object... fields) {
        handler.post(() -> {
            if (finished) return;
            try {
                Object[] values = new Object[fields.length + 2];
                values[0] = "callback_ns"; values[1] = timestamp;
                System.arraycopy(fields, 0, values, 2, fields.length);
                emit(name, values);
                action.run();
            } catch (Exception e) { fail(e.toString()); }
        });
    }

    private final BluetoothGattCallback callback = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt g, int status, int state) {
            event("connection", now(), () -> {
                if (state == BluetoothProfile.STATE_DISCONNECTED) {
                    connected = false; inFlight = false; fail("Disconnected, status=" + status); finish(false); return;
                }
                require(status == BluetoothGatt.GATT_SUCCESS && state == BluetoothProfile.STATE_CONNECTED,
                    "Unexpected connection callback");
                require(!connected && "connect".equals(operation), "Duplicate connection callback");
                connected = true; inFlight = false;
                if (cleanup) { attemptStop(); return; }
                setStage("discover"); begin("discover");
                require(gatt.discoverServices(), "discoverServices rejected");
            }, "status", status, "state", state);
        }
        @Override public void onServicesDiscovered(BluetoothGatt g, int status) {
            event("services", now(), () -> {
                complete("discover", status);
                if (cleanup) { attemptStop(); return; }
                boyiWrite = characteristic(BS, BW, BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE);
                boyiNotify = characteristic(BS, BN, BluetoothGattCharacteristic.PROPERTY_NOTIFY);
                if ("help".equals(mode)) {
                    logWrite = characteristic(LS, LW, BluetoothGattCharacteristic.PROPERTY_WRITE);
                    logNotify = characteristic(LS, LN, BluetoothGattCharacteristic.PROPERTY_NOTIFY);
                }
                emit("api", "name", "requestConnectionPriority", "priority", "HIGH");
                require(gatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH), "Priority request rejected");
                setStage("mtu"); begin("mtu");
                require(gatt.requestMtu(512), "requestMtu rejected");
            }, "status", status);
        }
        @Override public void onMtuChanged(BluetoothGatt g, int value, int status) {
            event("mtu", now(), () -> {
                // The peripheral can initiate negotiation before our own request.
                if (!inFlight || !"mtu".equals(operation)) {
                    require(status == BluetoothGatt.GATT_SUCCESS && value >= 23, "Unsolicited MTU change failed");
                    mtu = value; return;
                }
                complete("mtu", status); mtu = value;
                require(value >= 64, "MTU too small for fixed Boyi info response");
                if (cleanup) { attemptStop(); return; }
                subscribe(boyiNotify, "boyi_cccd");
            }, "status", status, "mtu", value);
        }
        @Override public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int status) {
            UUID owner = d.getCharacteristic().getUuid();
            event("descriptor_write", now(), () -> {
                complete("cccd:" + owner, status);
                if (cleanup) { attemptStop(); return; }
                if ("boyi_cccd".equals(stage)) sendBoyi(1, "serial");
                else { require("actions_cccd".equals(stage), "Unexpected CCCD stage"); sendActions(PREPARE, "prepare"); }
            }, "status", status, "characteristic", owner.toString(), "descriptor", d.getUuid().toString());
        }
        @Override public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic c, int status) {
            UUID id = c.getUuid();
            event("write_callback", now(), () -> {
                complete("write:" + id, status); writeDone = true;
                if (cleanup) { attemptStop(); return; }
                advance();
            }, "status", status, "characteristic", id.toString());
        }
        @Override public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            long timestamp = now();
            UUID id = c.getUuid();
            byte[] raw = c.getValue();
            byte[] value = raw == null ? new byte[0] : raw.clone();
            event("notify", timestamp, () -> {
                if (cleanup) return; // Raw bytes retained; failed stream is never resynchronized.
                if (BN.equals(id)) receiveBoyi(value);
                else if (LN.equals(id)) receiveActions(value);
                else throw new IllegalStateException("Unexpected notification UUID " + id);
                advance();
            }, "characteristic", id.toString(), "hex", hex(value));
        }
    };

    private BluetoothGattCharacteristic characteristic(UUID serviceId, UUID id, int properties) {
        BluetoothGattService service = gatt.getService(serviceId);
        require(service != null, "Missing service " + serviceId);
        BluetoothGattCharacteristic c = service.getCharacteristic(id);
        require(c != null && (c.getProperties() & properties) == properties, "Missing characteristic/property " + id);
        emit("characteristic", "service", serviceId.toString(), "uuid", id.toString(), "properties", c.getProperties());
        return c;
    }

    private void begin(String name) {
        require(!inFlight, "Concurrent GATT operation");
        inFlight = true; operation = name;
        emit("api", "name", name);
    }

    private void complete(String name, int status) {
        require(inFlight && name.equals(operation), "Unexpected GATT callback: " + name + ", pending=" + operation);
        inFlight = false;
        require(status == BluetoothGatt.GATT_SUCCESS, "GATT operation failed: " + name + " status=" + status);
    }

    private void subscribe(BluetoothGattCharacteristic c, String next) {
        setStage(next);
        emit("api", "name", "setCharacteristicNotification", "uuid", c.getUuid().toString());
        require(gatt.setCharacteristicNotification(c, true), "Local notification enable failed");
        BluetoothGattDescriptor descriptor = c.getDescriptor(CCCD);
        require(descriptor != null, "Missing CCCD");
        require(descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE), "CCCD value rejected");
        begin("cccd:" + c.getUuid());
        if (!gatt.writeDescriptor(descriptor)) { inFlight = false; throw new IllegalStateException("CCCD write rejected"); }
    }

    private void write(BluetoothGattCharacteristic c, byte[] bytes, int type) {
        writeDone = false;
        require(c.setValue(bytes), "Characteristic value rejected"); c.setWriteType(type);
        emit("write", "characteristic", c.getUuid().toString(), "hex", hex(bytes), "write_type", type);
        begin("write:" + c.getUuid());
        if (!gatt.writeCharacteristic(c)) { inFlight = false; throw new IllegalStateException("GATT write rejected"); }
    }

    private void sendBoyi(int opcode, String next) {
        setStage(next); responseSeen = false; reply = null;
        byte[] bytes = {(byte) 0xd2, 0x2d, 1, (byte) opcode, 0, 0, 0};
        int crc = crc16(bytes, 5); bytes[5] = (byte) crc; bytes[6] = (byte) (crc >> 8);
        write(boyiWrite, bytes, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
    }

    private void sendActions(byte[] bytes, String next) {
        setStage(next); responseSeen = false; expectedAcks++;
        if (bytes == START) started = true;
        if (bytes == STOP) stopAttempted = true;
        write(logWrite, bytes, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
    }

    private void receiveBoyi(byte[] b) {
        require(b.length >= 7 && (b[0] & 255) == 0xd2 && b[1] == 0x2d && b[2] == 1, "Invalid Boyi header");
        require(b.length == (b[4] & 255) + 7 && crc16(b, b.length - 2) == le16(b, b.length - 2), "Invalid Boyi length/CRC");
        int opcode = b[3] & 255;
        if (opcode == 15 || opcode == 25) { emit("boyi_event", "opcode", opcode); return; }
        int expected = "serial".equals(stage) ? 1 : ("info_before".equals(stage) || "info_after".equals(stage)) ? 5 : -1;
        require(opcode == expected && !responseSeen, "Unexpected/duplicate Boyi response");
        reply = Arrays.copyOfRange(b, 5, b.length - 2); responseSeen = true;
    }

    private void receiveActions(byte[] value) {
        require(!ended, "Actions bytes after END");
        int old = pending.length; pending = Arrays.copyOf(pending, old + value.length);
        System.arraycopy(value, 0, pending, old, value.length);
        require(pending.length <= 8192, "Actions buffer exceeded bound");
        while (pending.length >= 5) {
            require(pending[0] == 0x1d && (pending[2] & 255) == 0x81, "Invalid Actions header");
            int length = le16(pending, 3);
            require(length <= 4096, "Actions frame exceeded bound");
            if (pending.length < length + 5) break;
            byte[] frame = Arrays.copyOf(pending, length + 5);
            pending = Arrays.copyOfRange(pending, length + 5, pending.length);
            int command = frame[1] & 255;
            if (command == 0x10) {
                require(Arrays.equals(frame, ACK), "Invalid Actions ACK");
                require(++ackCount == expectedAcks, "Unexpected Actions ACK count"); responseSeen = true;
            } else if (command == 0xf0) {
                require(length >= 3 && le16(frame, 6) == length - 3, "Invalid Actions TLV length");
            } else if (command == 0xf1) {
                require(length == 0 && stopAttempted && pending.length == 0, "Invalid/premature Actions END"); ended = true;
            } else throw new IllegalStateException("Unknown Actions command " + command);
            emit("frame", "command", command, "hex", hex(frame));
        }
    }

    private void advance() {
        if (finished || cleanup || !writeDone || !responseSeen || inFlight) return;
        switch (stage) {
            case "serial":
                int end = 0; while (end < reply.length && reply[end] != 0) end++;
                require(SERIAL.equals(new String(reply, 0, end, StandardCharsets.US_ASCII)), "Serial does not match owned card");
                sendBoyi(5, "info_before"); break;
            case "info_before":
                require(reply.length >= 44 && reply[10] == 0 && reply[11] == 1 && reply[12] == 0 && reply[13] == 4,
                    "Expected idle FW010004"); initialInfo = reply.clone();
                emit("info_before", "hex", hex(initialInfo));
                if ("info".equals(mode)) finish(true); else subscribe(logNotify, "actions_cccd"); break;
            case "prepare": sendActions(START, "start"); break;
            case "start": sendActions(HELP, "help"); break;
            case "help": sendActions(STOP, "stop"); break;
            case "stop":
                if (!ended) return;
                require(ackCount == 4 && pending.length == 0, "Incomplete Actions stream");
                stopConfirmed = true;
                sendBoyi(5, "info_after"); break;
            case "info_after":
                emit("info_after", "hex", hex(reply), "matches", Arrays.equals(initialInfo, reply));
                require(Arrays.equals(initialInfo, reply), "Device info changed during experiment"); finish(true); break;
            default: throw new IllegalStateException("Unexpected response stage " + stage);
        }
    }

    private void fail(String message) {
        if (finished) return;
        if (error == null) { error = message; emit("error", "message", message); }
        if (!cleanup) {
            cleanup = true; stageToken++;
            handler.postDelayed(() -> finish(false), 4500);
        }
        try { attemptStop(); } catch (Exception e) { emit("cleanup_error", "message", e.toString()); }
        if (!started || !connected) finish(false);
    }

    private void attemptStop() {
        if (!cleanup || finished || !started || stopAttempted || !connected || inFlight) return;
        stopAttempted = true;
        stage = "cleanup_stop";
        emit("cleanup_stop", "reason", error);
        write(logWrite, STOP, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
    }

    private void finish(boolean ok) {
        if (finished) return;
        finished = true; handler.removeCallbacksAndMessages(null);
        emit("result", "ok", ok && error == null && !persistenceFailed, "error", error,
            "stage", stage, "mtu", mtu, "ack_count", ackCount, "expected_ack_count", expectedAcks,
            "end_received", ended, "pending_hex", hex(pending), "start_attempted", started,
            "stop_attempted", stopAttempted, "stop_confirmed", stopConfirmed,
            "pending_gatt_operation", inFlight ? operation : null, "connected_at_finish", connected);
        if (gatt != null) {
            try { emit("api", "name", "disconnect"); gatt.disconnect(); }
            catch (Exception e) { emit("close_error", "message", e.toString()); }
            try { emit("api", "name", "close"); gatt.close(); }
            catch (Exception e) { emit("close_error", "message", e.toString()); }
        }
        try { if (output != null) { output.getFD().sync(); output.close(); } }
        catch (IOException e) { persistenceFailed = true; }
        view.setText((ok && error == null && !persistenceFailed ? "COMPLETE" : "FAILED") + "\n" + run + "\n" + (error == null ? "" : error));
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private void emit(String kind, Object... fields) {
        if (output == null || persistenceFailed) return;
        try {
            JSONObject row = new JSONObject(); row.put("event", kind); row.put("elapsed_ns", now() - origin);
            for (int i = 0; i < fields.length; i += 2) row.put((String) fields[i], fields[i + 1] == null ? JSONObject.NULL : fields[i + 1]);
            byte[] bytes = (row + "\n").getBytes(StandardCharsets.UTF_8);
            if (rows >= 1024 || written + bytes.length > 512 * 1024) throw new IOException("Evidence bound exceeded");
            output.write(bytes); rows++; written += bytes.length;
            if (!cleanup && !finished && (rows >= 1000 || written > 480 * 1024)) handler.post(() -> fail("Evidence reserve reached"));
        } catch (Exception e) {
            persistenceFailed = true;
            handler.post(() -> fail("Evidence write failed: " + e));
        }
    }

    @Override public void onBackPressed() { fail("User requested exit"); }
    @Override protected void onDestroy() { if (!finished) fail("Activity destroyed before completion"); super.onDestroy(); }
    private static UUID uuid(String value) { return UUID.fromString(value); }
    private static long now() { return SystemClock.elapsedRealtimeNanos(); }
    private static void require(boolean condition, String message) { if (!condition) throw new IllegalStateException(message); }
    private static int le16(byte[] b, int i) { return (b[i] & 255) | ((b[i + 1] & 255) << 8); }
    private static int crc16(byte[] b, int count) {
        int crc = 0;
        for (int i = 0; i < count; i++) { crc ^= b[i] & 255; for (int n = 0; n < 8; n++) crc = (crc & 1) != 0 ? (crc >> 1) ^ 0xa001 : crc >> 1; }
        return crc;
    }
    private static String hex(byte[] b) {
        StringBuilder result = new StringBuilder(b.length * 2);
        for (byte value : b) result.append(String.format(Locale.ROOT, "%02x", value & 255)); return result.toString();
    }
    private static byte[] unhex(String text) {
        byte[] result = new byte[text.length() / 2];
        for (int i = 0; i < result.length; i++) result[i] = (byte) Integer.parseInt(text.substring(i * 2, i * 2 + 2), 16); return result;
    }
}
