package ru.jolion.locator;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.location.*;
import android.net.*;
import android.os.*;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.*;
import javax.net.ssl.HttpsURLConnection;

public class TrackingService extends Service implements LocationListener {
    private QueueDb db;
    private LocationManager locations;
    private ConnectivityManager connectivity;
    private ConnectivityManager.NetworkCallback networkCallback;
    private final ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService writer = Executors.newSingleThreadExecutor();
    private ScheduledFuture<?> pending;
    private long retryMs = 5000;
    private volatile boolean closed = false;
    private final UploadWakeup wakeup = new UploadWakeup();
    private long lastFixElapsed = 0;
    private volatile Location lastAcceptedFix;
    // Once the GPS receiver has produced a precise fix, the coarse network
    // positions are no longer needed: they only bridge the cold start, when the
    // satellite receiver has nothing to report yet.
    private boolean gpsLocked = false;
    private static final float GPS_MAX_ACCURACY_M = 100f;
    private static final float NETWORK_COLD_START_ACCURACY_M = 1500f;
    private static final double MIN_MOVEMENT_M = 3.0;
    private static final double MAX_REALISTIC_SPEED_KMH = 250.0;
    private static final long GAP_RESET_MS = 120_000L;
    private final Handler ui = new Handler(Looper.getMainLooper());

    public void onCreate() {
        super.onCreate();
        NotificationManager nm = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel("tracking", "Запись поездки", NotificationManager.IMPORTANCE_LOW));
        startForeground(1, notification("Запись включена. Ожидание GPS"));
        db = new QueueDb(this);
        try { db.getWritableDatabase(); } catch(RuntimeException error) { status("Не удалось открыть очередь GPS"); stopSelf(); return; }
        locations = (LocationManager)getSystemService(LOCATION_SERVICE);
        connectivity = (ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            status("Нет разрешения GPS. Откройте приложение."); stopSelf(); return;
        }
        try {
            locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000, 0, this);
            // The network provider reports a coarse position in seconds. It bridges
            // the GPS cold start so the track begins right away, and is dropped as
            // soon as the satellite receiver locks (see onLocationChanged).
            locations.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 30000, 0, this);
            // A service can take a while to start (for example after boot or when
            // the head unit is busy). LocationManager may already have a recent
            // fix by then, so seed the queue instead of waiting for the next poll.
            for (String provider : new String[]{LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER}) {
                Location last = locations.getLastKnownLocation(provider);
                if (last != null) onLocationChanged(last);
            }
        } catch (RuntimeException e) { status("GPS недоступен. Проверьте разрешения и источник координат ГУ."); }
        networkCallback = new ConnectivityManager.NetworkCallback() {
            public void onAvailable(Network n) { retryIfValidated(n); }
            public void onCapabilitiesChanged(Network n, NetworkCapabilities caps) {
                // Wi-Fi can stay connected while its upstream internet disappears.
                // Android reports recovery as a capabilities change, not onAvailable.
                if (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                        && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) networkAvailable();
            }
        };
        connectivity.registerDefaultNetworkCallback(networkCallback);
        schedule(0);
        ui.postDelayed(health, 10000);
    }
    private Notification notification(String text) {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new Notification.Builder(this, "tracking").setContentTitle("Jolion Locator").setContentText(text)
            .setSmallIcon(R.drawable.ic_locator).setContentIntent(open).setOngoing(true).build();
    }
    private final Runnable health = new Runnable() {
        public void run() {
            if (closed) return;
            String gps = lastFixElapsed == 0 ? "Ожидание GPS" : "GPS: " + ((SystemClock.elapsedRealtime()-lastFixElapsed)/1000) + " с назад";
            Config.prefs(TrackingService.this).edit().putString("gps_status", gps).apply();
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).notify(1, notification(gps));
            ui.postDelayed(this, 10000);
        }
    };
    private void status(String value) { Config.prefs(this).edit().putString("status", value).apply(); }
    public int onStartCommand(Intent i, int flags, int id) {
        if (!Config.prefs(this).getBoolean("enabled", false)) { stopSelf(); return START_NOT_STICKY; }
        return START_STICKY;
    }
    public IBinder onBind(Intent i) { return null; }
    public void onLocationChanged(Location incoming) {
        if (closed) return;
        Location fix = new Location(incoming);
        boolean gps = LocationManager.GPS_PROVIDER.equals(fix.getProvider());
        long ageNs = SystemClock.elapsedRealtimeNanos() - fix.getElapsedRealtimeNanos();
        if (fix.isFromMockProvider() || !fix.hasAccuracy() || ageNs < 0 || ageNs > 15000000000L) return;
        if (!acceptProvider(fix.getProvider(), fix.getAccuracy(), gpsLocked)) return;
        if (!Double.isFinite(fix.getLatitude()) || !Double.isFinite(fix.getLongitude()) || Math.abs(fix.getLatitude()) > 90 || Math.abs(fix.getLongitude()) > 180 || !Float.isFinite(fix.getAccuracy()) || fix.getAccuracy() < 0) return;
        if (fix.getTime() < 1577836800000L || fix.getTime() > System.currentTimeMillis()+300000L) { status("Неверное время GPS или системных часов. Проверьте дату ГУ."); return; }
        if (fix.hasSpeed() && (!Float.isFinite(fix.getSpeed()) || fix.getSpeed() < 0 || fix.getSpeed()*3.6 > 400)) return;
        if (lastFixElapsed > 0 && SystemClock.elapsedRealtime()-lastFixElapsed < 900) return;
        if (!transitionAllowed(lastAcceptedFix, fix)) return;
        lastFixElapsed = SystemClock.elapsedRealtime();
        if (gps) gpsLocked = true;
        final String base=Config.destination(this),relayToken=Config.prefs(this).getString("disk_oauth",""),vehicle=Config.prefs(this).getString("vehicle", "jolion"),token=Config.key(this);
        writer.execute(() -> {
            try {
                JSONObject p = new JSONObject();
                p.put("id", UUID.randomUUID().toString()); p.put("timestamp_ms", fix.getTime());
                p.put("latitude", fix.getLatitude()); p.put("longitude", fix.getLongitude());
                p.put("accuracy_m", fix.getAccuracy());
                p.put("speed_kmh", fix.hasSpeed() ? fix.getSpeed()*3.6 : JSONObject.NULL);
                p.put("speed_accuracy_kmh", fix.hasSpeed() && fix.hasSpeedAccuracy() && fix.getSpeedAccuracyMetersPerSecond()*3.6<=1000000 && Float.isFinite(fix.getSpeedAccuracyMetersPerSecond()) && fix.getSpeedAccuracyMetersPerSecond()>=0 ? fix.getSpeedAccuracyMetersPerSecond()*3.6 : JSONObject.NULL);
                p.put("bearing", fix.hasBearing() && Float.isFinite(fix.getBearing()) && fix.getBearing() >= 0 && fix.getBearing() <= 360 ? fix.getBearing() : JSONObject.NULL);
                p.put("altitude_m", fix.hasAltitude() && Double.isFinite(fix.getAltitude()) && fix.getAltitude() >= -1000 && fix.getAltitude() <= 15000 ? fix.getAltitude() : JSONObject.NULL);
                synchronized(Config.class) {
                    String selected=Config.destination(this);
                    boolean switched=vehicle.equals(Config.prefs(this).getString("vehicle","jolion")) && selected.startsWith("yadisk:")!=base.startsWith("yadisk:");
                    db.append(p,switched?selected:base,vehicle,switched?Config.key(this):token,switched?Config.prefs(this).getString("disk_oauth",""):relayToken);
                }
                // Advance the filter only after the point is durable. If the
                // queue cannot be written, the next fix must still be compared
                // with the last point that actually reached SQLite.
                synchronized (TrackingService.this) { lastAcceptedFix = fix; }
                Config.prefs(this).edit().putString("quality", "Точность GPS: ±"+Math.round(fix.getAccuracy())+" м · погрешность скорости: "+(p.isNull("speed_accuracy_kmh")?"неизвестна":"±"+Math.round(p.getDouble("speed_accuracy_kmh"))+" км/ч")).apply();
                Config.prefs(this).edit().putLong("last_fix", fix.getTime()).putLong("queued", db.count()).putString("storage_error", "").apply();
                // A service may have started with an empty queue. Start the upload
                // as soon as the first fix is durably stored instead of waiting for
                // the next connectivity callback (which may never happen).
                schedule(0);
            } catch (Exception e) { Config.prefs(this).edit().putString("storage_error", "ОШИБКА ЗАПИСИ: проверьте свободное место. Точка не сохранена.").apply(); }
        });
    }
    private synchronized void schedule(long delay) {
        if (closed) { return; }
        if (pending != null) { pending.cancel(false); }
        pending = worker.schedule(this::upload, delay, TimeUnit.MILLISECONDS);
    }
    private synchronized void networkAvailable() {
        wakeup.networkAvailable();
        schedule(0);
    }
    private void retryIfValidated(Network network) {
        NetworkCapabilities caps = connectivity.getNetworkCapabilities(network);
        if (caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) networkAvailable();
    }
    private void upload() {
        final long started;
        synchronized (this) { if (closed) return; started = wakeup.begin(); }
        HttpsURLConnection connection = null;
        long next = 5000;
        try {
            QueueDb.Batch batch=db.uploadBatch();
            Config.prefs(this).edit().putLong("queued", db.count()).apply();
            if (batch == null) return;
            JSONArray points=batch.points;
            Network active = connectivity.getActiveNetwork();
            NetworkCapabilities caps = active == null ? null : connectivity.getNetworkCapabilities(active);
            if (caps == null || !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)) throw new IOException("Offline");
            String base = batch.base;
            String vehicle = batch.vehicle;
            if(base.startsWith("yadisk:")) {
                String oauth=base.equals(Config.destination(this)) ? Config.prefs(this).getString("disk_oauth","") : batch.relayToken;
                new DiskTransport().send(batch,oauth);
                JSONArray ids=new JSONArray();for(int i=0;i<points.length();i++)ids.put(points.getJSONObject(i).getString("id"));
                db.acknowledge(ids,points);
                long remaining=db.count();
                Config.prefs(this).edit().putLong("queued",remaining).putLong("last_sync",System.currentTimeMillis()).apply();
                status("Передано на Яндекс.Диск; получение Home Assistant проверяется в HA");retryMs=5000;
                // The driver picks the interval; a large backlog still drains fast.
                next=remaining>200?1000:Config.intervalSeconds(this)*1000L;return;
            }
            URL endpoint = new URL(base + "/api/jolion_locator/v1/" + vehicle);
            if (!endpoint.getProtocol().equals("https")) throw new IOException("HTTPS required");
            connection = (HttpsURLConnection)endpoint.openConnection();
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(15000); connection.setReadTimeout(20000);
            connection.setRequestMethod("POST"); connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json");
            boolean current=base.equals(Config.prefs(this).getString("url", "")) && vehicle.equals(Config.prefs(this).getString("vehicle", "jolion"));
            connection.setRequestProperty("X-Jolion-Key", current ? Config.key(this) : batch.token);
            JSONObject payload = new JSONObject(); payload.put("version", 1); payload.put("points", points);
            byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(body.length);
            try (OutputStream out = connection.getOutputStream()) { out.write(body); }
            int code = connection.getResponseCode();
            if (code != 200) { status("HTTP " + code + ": очередь сохранена. Проверьте адрес, ключ и интеграцию."); next = Math.min(retryMs*2, 300000); retryMs = next; return; }
            ByteArrayOutputStream response = new ByteArrayOutputStream();
            try (InputStream in = connection.getInputStream()) {
                byte[] buf = new byte[4096]; int count;
                while ((count = in.read(buf)) != -1) {
                    if (response.size()+count > 65536) throw new IOException("Response too large");
                    response.write(buf, 0, count);
                }
            }
            JSONObject reply = new JSONObject(response.toString("UTF-8"));
            if (reply.getInt("version") != 1) throw new IOException("Protocol mismatch");
            JSONArray ack = reply.getJSONArray("ack");
            if (ack.length() == 0) throw new IOException("No acknowledgement");
            db.acknowledge(ack, points);
            long count = db.count();
            Config.prefs(this).edit().putLong("queued", count).putLong("last_sync", System.currentTimeMillis()).apply();
            status("Связь с Home Assistant установлена"); retryMs = 5000;
            next = count > 0 ? 250 : Config.intervalSeconds(this)*1000L;
        } catch (Exception e) {
            status("Нет подтверждения сервера. Данные остаются в очереди.");
            retryMs = Math.min(retryMs*2, 300000); next = retryMs;
        } finally {
            if (connection != null) connection.disconnect();
            synchronized (this) { schedule(wakeup.nextDelay(started, next)); }
        }
    }
    public void onProviderDisabled(String provider) { status("GPS выключен"); }
    public void onProviderEnabled(String provider) { status("GPS включен, ожидание координат"); }
    public void onStatusChanged(String provider, int status, Bundle extras) {}
    public void onDestroy() {
        synchronized (this) { closed = true; if (pending != null) pending.cancel(false); }
        ui.removeCallbacks(health);
        if (locations != null) locations.removeUpdates(this);
        if (networkCallback != null) connectivity.unregisterNetworkCallback(networkCallback);
        worker.shutdown(); writer.shutdown();
        new Thread(() -> {
            try { worker.awaitTermination(60, TimeUnit.SECONDS); writer.awaitTermination(60, TimeUnit.SECONDS); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            if (worker.isTerminated() && writer.isTerminated()) db.close();
        }, "locator-close").start();
        super.onDestroy();
    }
    /**
     * Whether a position from {@code provider} is worth recording.
     *
     * The satellite receiver is precise but slow to lock after a cold start; the
     * network provider reports a coarse position in seconds. The coarse fixes are
     * accepted only while the satellite receiver is still warming up, so the track
     * begins immediately and is never smeared once GPS takes over.
     */
    static boolean acceptProvider(String provider, float accuracy, boolean gpsLocked) {
        boolean gps = LocationManager.GPS_PROVIDER.equals(provider);
        if (accuracy > (gps ? GPS_MAX_ACCURACY_M : NETWORK_COLD_START_ACCURACY_M)) return false;
        return gps || !gpsLocked;
    }

    /** Reject duplicate GPS callbacks and physically impossible jumps before they reach SQLite. */
    static boolean transitionAllowed(Location previous, Location current) {
        if (previous == null) return true;
        if (current == null || current.getTime() <= previous.getTime()) return false;
        // A provider switch is deliberately accepted: network is only a cold-start
        // hint and must not prevent the first real satellite fix.
        if (!LocationManager.GPS_PROVIDER.equals(previous.getProvider())
                || !LocationManager.GPS_PROVIDER.equals(current.getProvider())) return true;
        long deltaMs = current.getTime() - previous.getTime();
        if (deltaMs > GAP_RESET_MS) return true;
        float[] result = new float[1];
        Location.distanceBetween(previous.getLatitude(), previous.getLongitude(),
                current.getLatitude(), current.getLongitude(), result);
        double distance = result[0];
        if (distance < MIN_MOVEMENT_M) return false;
        double speedKmh = distance / deltaMs * 3.6e3;
        return speedKmh <= MAX_REALISTIC_SPEED_KMH;
    }
}

