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
    private volatile boolean dbReady = false;
    private LocationManager locations;
    private ConnectivityManager connectivity;
    private ConnectivityManager.NetworkCallback networkCallback;
    private final ScheduledExecutorService worker = Executors.newSingleThreadScheduledExecutor();
    private final ExecutorService writer = Executors.newSingleThreadExecutor();
    private ScheduledFuture<?> pending;
    private boolean uploadRunning = false;
    private long retryMs = 5000;
    private volatile boolean closed = false;
    private final UploadWakeup wakeup = new UploadWakeup();
    private long lastFixElapsed = 0;
    private volatile Location lastAcceptedFix;
    private enum GpsState { COLD_START, GPS_ACTIVE, GPS_LOST, GPS_RECOVERING, STATIONARY }
    private volatile GpsState gpsState = GpsState.COLD_START;
    private int recoveryFixes = 0;
    private volatile Location stationaryAnchor;
    private Location recoveryCandidate;
    // Once the GPS receiver has produced a precise fix, the coarse network
    // positions are no longer needed: they only bridge the cold start, when the
    // satellite receiver has nothing to report yet.
    private boolean gpsLocked = false;
    private static final float GPS_MAX_ACCURACY_M = 100f;
    private static final float NETWORK_COLD_START_ACCURACY_M = 1500f;
    private static final double MIN_MOVEMENT_M = 3.0;
    private static final double MAX_REALISTIC_SPEED_KMH = 250.0;
    private static final long GAP_RESET_MS = 120_000L;
    private static final long MOVING_INTERVAL_MS = 1500L;
    private static final long SLOW_INTERVAL_MS = 4000L;
    private static final long PARKED_INTERVAL_MS = 20000L;
    private static final float MOVING_SPEED_MPS = 2.0f;
    private static final double STATIONARY_RADIUS_M = 20.0;
    private static final int RECOVERY_FIXES_REQUIRED = 2;
    private final Handler ui = new Handler(Looper.getMainLooper());
    private long serviceCreatedAt;
    private long gpsRequestedAt;
    private boolean firstFixRecorded;
    private GnssStatus.Callback gnssCallback;

    public void onCreate() {
        super.onCreate();
        serviceCreatedAt = SystemClock.elapsedRealtime();
        Config.prefs(this).edit().putLong("service_created_at", System.currentTimeMillis()).putString("startup_stage", "FOREGROUND_STARTING").apply();
        NotificationManager nm = (NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel("tracking", "Запись поездки", NotificationManager.IMPORTANCE_LOW));
        startForeground(1, notification("Запись включена. Ожидание GPS"));
        Config.prefs(this).edit().putLong("foreground_started_at", System.currentTimeMillis()).putString("startup_stage", "FOREGROUND_STARTED").apply();
        locations = (LocationManager)getSystemService(LOCATION_SERVICE);
        connectivity = (ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            status("Нет разрешения GPS. Откройте приложение."); stopSelf(); return;
        }
        writer.execute(() -> {
            try { db = new QueueDb(this); db.getWritableDatabase(); dbReady = true; Config.prefs(this).edit().putLong("db_ready_at", System.currentTimeMillis()).putString("startup_stage", "DB_READY").apply(); schedule(0); }
            catch (RuntimeException error) { status("Не удалось открыть очередь GPS"); Config.prefs(this).edit().putString("startup_stage", "DB_ERROR").apply(); }
        });
        try {
            gpsRequestedAt = SystemClock.elapsedRealtime();
            Config.prefs(this).edit().putLong("gps_requested_at", System.currentTimeMillis()).putString("startup_stage", "GPS_REQUESTED").apply();
            locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, MOVING_INTERVAL_MS, 0, this);
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
            if (Build.VERSION.SDK_INT >= 24) {
                gnssCallback = new GnssStatus.Callback() {
                    public void onSatelliteStatusChanged(GnssStatus status) {
                        int visible = status.getSatelliteCount(), used = 0, gps = 0, glonass = 0, galileo = 0, beidou = 0;
                        for (int i=0;i<visible;i++) if (status.usedInFix(i)) { used++; int type=status.getConstellationType(i); if(type==GnssStatus.CONSTELLATION_GPS)gps++; else if(type==GnssStatus.CONSTELLATION_GLONASS)glonass++; else if(type==GnssStatus.CONSTELLATION_GALILEO)galileo++; else if(type==GnssStatus.CONSTELLATION_BEIDOU)beidou++; }
                        Config.prefs(TrackingService.this).edit().putLong("gnss_visible", visible).putLong("gnss_used", used).putLong("gnss_gps", gps).putLong("gnss_glonass", glonass).putLong("gnss_galileo", galileo).putLong("gnss_beidou", beidou).apply();
                    }
                };
                locations.registerGnssStatusCallback(gnssCallback);
            }
        } catch (RuntimeException e) { status("GPS недоступен. Проверьте разрешения и источник координат ГУ."); }
        scheduleWatchdog();
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
            if (lastFixElapsed > 0 && SystemClock.elapsedRealtime()-lastFixElapsed > GAP_RESET_MS
                    && (gpsState == GpsState.GPS_ACTIVE || gpsState == GpsState.STATIONARY)) {
                gpsState = GpsState.GPS_LOST; gpsLocked = true; publishState();
            }
            scheduleWatchdog();
            Config.prefs(TrackingService.this).edit().putString("gps_status", gps).putString("gps_state", gpsState.name()).apply();
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
        count("received");
        if (!firstFixRecorded && LocationManager.GPS_PROVIDER.equals(fix.getProvider())) {
            firstFixRecorded = true;
            long now = SystemClock.elapsedRealtime();
            Config.prefs(this).edit().putLong("first_fix_at", System.currentTimeMillis()).putLong("cold_start_ms", gpsRequestedAt == 0 ? 0 : now-gpsRequestedAt).putString("startup_stage", "FIRST_FIX").apply();
        }
        if (fix.isFromMockProvider() || !fix.hasAccuracy() || ageNs < 0 || ageNs > 15000000000L) { count("rejected_stale"); return; }
        boolean networkRecovery = !gps && gpsLocked && gpsState == GpsState.GPS_LOST;
        if (!acceptProvider(fix.getProvider(), fix.getAccuracy(), gpsLocked, networkRecovery)) { count("rejected_provider"); return; }
        if (!Double.isFinite(fix.getLatitude()) || !Double.isFinite(fix.getLongitude()) || Math.abs(fix.getLatitude()) > 90 || Math.abs(fix.getLongitude()) > 180 || !Float.isFinite(fix.getAccuracy()) || fix.getAccuracy() < 0) { count("rejected_coordinates"); return; }
        if (fix.getTime() < 1577836800000L || fix.getTime() > System.currentTimeMillis()+300000L) { count("rejected_time"); status("Неверное время GPS или системных часов. Проверьте дату ГУ."); return; }
        if (networkRecovery) {
            Config.prefs(this).edit().putString("network_last_latitude", Double.toString(fix.getLatitude()))
                    .putString("network_last_longitude", Double.toString(fix.getLongitude()))
                    .putLong("network_last_fix", fix.getTime()).apply();
            count("network_recovery");
            return;
        }
        if (fix.hasSpeed() && (!Float.isFinite(fix.getSpeed()) || fix.getSpeed() < 0 || fix.getSpeed()*3.6 > 400)) { count("rejected_speed"); return; }
        if (lastFixElapsed > 0 && SystemClock.elapsedRealtime()-lastFixElapsed < 900) { count("rejected_rate"); return; }
        Location transitionReference = recoveryCandidate != null ? recoveryCandidate : lastAcceptedFix;
        if (!transitionAllowed(transitionReference, fix)) { count("rejected_transition"); return; }
        if (gps && gpsState == GpsState.GPS_LOST) {
            recoveryCandidate = fix;
            recoveryFixes = 1;
            gpsState = GpsState.GPS_RECOVERING;
            count("recovery_candidates");
            publishState();
            return;
        }
        if (gpsState != GpsState.GPS_RECOVERING && !isMoving(fix) && stationaryAnchor != null && distanceMeters(stationaryAnchor, fix) < STATIONARY_RADIUS_M) {
            lastFixElapsed = SystemClock.elapsedRealtime();
            count("rejected_stationary"); return;
        }
        lastFixElapsed = SystemClock.elapsedRealtime();
        if (gps) {
            gpsLocked = true;
            if (gpsState == GpsState.GPS_RECOVERING) { recoveryFixes++; if (recoveryFixes >= RECOVERY_FIXES_REQUIRED) gpsState = isMoving(fix) ? GpsState.GPS_ACTIVE : GpsState.STATIONARY; }
            else gpsState = isMoving(fix) ? GpsState.GPS_ACTIVE : GpsState.STATIONARY;
            recoveryCandidate = null;
            if (!isMoving(fix)) stationaryAnchor = fix;
            else stationaryAnchor = null;
        }
        else if (gpsState == GpsState.COLD_START || gpsState == GpsState.GPS_LOST) gpsState = GpsState.COLD_START;
        applyLocationMode(fix); publishState();
        final String base=Config.destination(this),vehicle=Config.prefs(this).getString("vehicle", "jolion");
        writer.execute(() -> {
            try {
                // Keystore access stays off the callback/main path so the first
                // GNSS fix can be handled without waiting for crypto storage.
                String relayToken=Config.diskOauth(this), token=Config.key(this);
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
                    db.append(p,switched?selected:base,vehicle,switched?Config.key(this):token,switched?Config.diskOauth(this):relayToken);
                }
                // Advance the filter only after the point is durable. If the
                // queue cannot be written, the next fix must still be compared
                // with the last point that actually reached SQLite.
                synchronized (TrackingService.this) { lastAcceptedFix = fix; }
                count("saved");
                Config.prefs(this).edit().putString("quality", "Точность GPS: ±"+Math.round(fix.getAccuracy())+" м · погрешность скорости: "+(p.isNull("speed_accuracy_kmh")?"неизвестна":"±"+Math.round(p.getDouble("speed_accuracy_kmh"))+" км/ч")).apply();
                Config.prefs(this).edit().putLong("last_fix", fix.getTime()).putString("storage_error", "").apply();
                // A service may have started with an empty queue. Start the upload
                // as soon as the first fix is durably stored instead of waiting for
                // the next connectivity callback (which may never happen).
                schedule(0);
            } catch (Exception e) { Config.prefs(this).edit().putString("storage_error", "ОШИБКА ЗАПИСИ: проверьте свободное место. Точка не сохранена.").apply(); }
        });
    }
    private synchronized void schedule(long delay) {
        if (closed) { return; }
        if (uploadRunning || (pending != null && !pending.isDone())) return;
        pending = worker.schedule(this::upload, delay, TimeUnit.MILLISECONDS);
    }
    private synchronized void networkAvailable() {
        wakeup.networkAvailable();
        if (pending != null && !pending.isDone()) { pending.cancel(false); pending = null; }
        schedule(0);
    }
    private boolean isMoving(Location fix) { return fix.hasSpeed() && Float.isFinite(fix.getSpeed()) && fix.getSpeed() >= MOVING_SPEED_MPS; }
    private static double distanceMeters(Location a, Location b) {
        float[] result = new float[1];
        Location.distanceBetween(a.getLatitude(), a.getLongitude(), b.getLatitude(), b.getLongitude(), result);
        return result[0];
    }
    private synchronized void applyLocationMode(Location fix) {
        if (locations == null || !LocationManager.GPS_PROVIDER.equals(fix.getProvider())) return;
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) return;
        long interval = isMoving(fix) ? MOVING_INTERVAL_MS : (fix.hasSpeed() && fix.getSpeed() > 0.5f ? SLOW_INTERVAL_MS : PARKED_INTERVAL_MS);
        try { locations.removeUpdates(this); locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, interval, 0, this); locations.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 30000, 0, this); } catch (SecurityException ignored) { }
    }
    private void publishState() { Config.prefs(this).edit().putString("gps_state", gpsState.name()).apply(); }
    private void count(String name) {
        synchronized (Config.class) {
            String key = "metric_" + name; SharedPreferences p = Config.prefs(this);
            p.edit().putLong(key, p.getLong(key, 0) + 1).apply();
        }
    }
    private void retryIfValidated(Network network) {
        NetworkCapabilities caps = connectivity.getNetworkCapabilities(network);
        if (caps != null && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                && caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) networkAvailable();
    }
    private void upload() {
        final long started;
        synchronized (this) { if (closed || uploadRunning) return; uploadRunning = true; pending = null; started = wakeup.begin(); }
        HttpsURLConnection connection = null;
        long next = 5000;
        try {
            if (!dbReady || db == null) { next = 5000; return; }
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
                String oauth=base.equals(Config.destination(this)) ? Config.diskOauth(this) : batch.relayToken;
                new DiskTransport().send(batch,oauth);
                JSONArray ids=new JSONArray();for(int i=0;i<points.length();i++)ids.put(points.getJSONObject(i).getString("id"));
                db.acknowledge(ids,points);
                long remaining=db.count();
                Config.prefs(this).edit().putLong("queued",remaining).putLong("last_sync",System.currentTimeMillis()).apply();
                status("Передано на Яндекс.Диск; получение Home Assistant проверяется в HA");retryMs=5000;
                count("uploaded");
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
            count("uploaded");
            long count = db.count();
            Config.prefs(this).edit().putLong("queued", count).putLong("last_sync", System.currentTimeMillis()).apply();
            status("Связь с Home Assistant установлена"); retryMs = 5000;
            next = count > 0 ? 250 : Config.intervalSeconds(this)*1000L;
        } catch (Exception e) {
            count("retries");
            status("Нет подтверждения сервера. Данные остаются в очереди.");
            retryMs = Math.min(retryMs*2, 300000); next = retryMs;
        } finally {
            if (connection != null) connection.disconnect();
            synchronized (this) { uploadRunning = false; schedule(wakeup.nextDelay(started, next)); }
        }
    }
    public void onProviderDisabled(String provider) { status("GPS выключен"); }
    public void onProviderEnabled(String provider) { status("GPS включен, ожидание координат"); }
    public void onStatusChanged(String provider, int status, Bundle extras) {}
    public void onDestroy() {
        synchronized (this) { closed = true; if (pending != null) pending.cancel(false); }
        ui.removeCallbacks(health);
        if (locations != null) locations.removeUpdates(this);
        if (Build.VERSION.SDK_INT >= 24 && locations != null && gnssCallback != null) locations.unregisterGnssStatusCallback(gnssCallback);
        if (networkCallback != null) connectivity.unregisterNetworkCallback(networkCallback);
        worker.shutdown(); writer.shutdown();
        new Thread(() -> {
            try { worker.awaitTermination(60, TimeUnit.SECONDS); writer.awaitTermination(60, TimeUnit.SECONDS); }
            catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            if (worker.isTerminated() && writer.isTerminated() && db != null) db.close();
        }, "locator-close").start();
        super.onDestroy();
    }
    private void scheduleWatchdog() {
        AlarmManager alarms = (AlarmManager)getSystemService(ALARM_SERVICE);
        Intent intent = new Intent(this, BootReceiver.class).setAction(BootReceiver.ACTION_WATCHDOG);
        PendingIntent pending = PendingIntent.getBroadcast(this, 77, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        long at = System.currentTimeMillis() + 60000L;
        if (Build.VERSION.SDK_INT >= 23) alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, at, pending); else alarms.setExact(AlarmManager.RTC_WAKEUP, at, pending);
    }
    public void onTaskRemoved(Intent rootIntent) {
        if (!closed && Config.prefs(this).getBoolean("enabled", false)) schedule(1000);
        super.onTaskRemoved(rootIntent);
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
        return acceptProvider(provider, accuracy, gpsLocked, false);
    }
    static boolean acceptProvider(String provider, float accuracy, boolean gpsLocked, boolean recoveryNetwork) {
        boolean gps = LocationManager.GPS_PROVIDER.equals(provider);
        if (accuracy > (gps ? GPS_MAX_ACCURACY_M : NETWORK_COLD_START_ACCURACY_M)) return false;
        return gps || !gpsLocked || recoveryNetwork;
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

