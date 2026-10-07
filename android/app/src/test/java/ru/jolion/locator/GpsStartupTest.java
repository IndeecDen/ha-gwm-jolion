package ru.jolion.locator;

import android.Manifest;
import android.app.Application;
import android.content.Context;
import android.content.SharedPreferences;
import android.location.Location;
import android.location.LocationManager;
import android.os.SystemClock;
import java.lang.reflect.Field;
import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.android.controller.ServiceController;
import org.robolectric.annotation.SQLiteMode;
import org.robolectric.shadows.ShadowLocationManager;
import org.robolectric.shadows.ShadowSystemClock;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27)
@SQLiteMode(SQLiteMode.Mode.LEGACY)
public class GpsStartupTest {
    @org.robolectric.annotation.Implements(LocationManager.class)
    public static class BrokenNetwork extends ShadowLocationManager {
        @org.robolectric.annotation.Implementation
        protected void requestLocationUpdates(String provider,long interval,float distance,
                android.location.LocationListener listener,android.os.Looper looper) {
            if ("network".equals(provider)) throw new IllegalArgumentException("Network provider unavailable");
            super.requestLocationUpdates(provider,interval,distance,listener,looper);
        }
    }
    private SharedPreferences prefs;
    private LocationManager manager;
    private ShadowLocationManager locations;

    @Before public void setup() {
        Context context=RuntimeEnvironment.getApplication();
        context.deleteDatabase("points.db");
        prefs=Config.prefs(context);
        prefs.edit().clear().putString("key", "a".repeat(48)).putString("url", "https://local.invalid").commit();
        Shadows.shadowOf((Application)context).grantPermissions(Manifest.permission.ACCESS_FINE_LOCATION);
        manager=(LocationManager)context.getSystemService(Context.LOCATION_SERVICE);
        locations=Shadows.shadowOf(manager);
        locations.setProviderEnabled("gps", true);
        ShadowSystemClock.advanceBy(Duration.ofSeconds(60));
    }
    private Location fix(long ageMs) {
        Location fix=new Location("gps");
        fix.setTime(System.currentTimeMillis()-ageMs);
        fix.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos()-ageMs*1000000);
        fix.setLatitude(55);fix.setLongitude(37);fix.setAccuracy(5);
        return fix;
    }
    private void drain(TrackingService service) throws Exception {
        Field field=TrackingService.class.getDeclaredField("writer");field.setAccessible(true);
        ((ExecutorService)field.get(service)).submit(()->{}).get(10,TimeUnit.SECONDS);
    }
    @Test public void missingNetworkDoesNotPreventGpsCacheOrGnssRegistration() throws Exception {
        locations.removeProvider("network");
        locations.setLastKnownLocation("gps",fix(2000));
        ServiceController<TrackingService> controller=Robolectric.buildService(TrackingService.class).create();
        try {
            drain(controller.get());
            assertTrue(prefs.getBoolean("gps_subscribed",false));
            assertTrue(prefs.getBoolean("gnss_registered",false));
            assertFalse(prefs.getBoolean("network_subscribed",true));
            assertEquals(1,prefs.getLong("metric_saved",0));
            assertFalse("Cache access is not a live callback",prefs.contains("last_gps_callback_at"));
        } finally { controller.destroy(); }
    }
    @Test public void staleCacheIsRejectedAndOldSessionMetricsAreCleared() throws Exception {
        prefs.edit().putLong("cold_start_ms",300214).putLong("first_fix_at",1)
                .putLong("gnss_visible",12).putLong("gnss_status_at",1).putString("status","GPS выключен").commit();
        locations.setLastKnownLocation("gps",fix(30000));
        ServiceController<TrackingService> controller=Robolectric.buildService(TrackingService.class).create();
        try {
            drain(controller.get());
            assertEquals(0,prefs.getLong("metric_saved",0));
            assertFalse(prefs.contains("first_fix_at"));assertFalse(prefs.contains("cold_start_ms"));
            assertEquals(0,prefs.getLong("gnss_visible",-1));assertFalse(prefs.contains("gnss_status_at"));
            assertNotEquals("GPS выключен",prefs.getString("status",""));
        } finally { controller.destroy(); }
    }
    @Test @org.robolectric.annotation.Config(shadows=BrokenNetwork.class)
    public void failingNetworkRequestDoesNotSkipFreshGpsSeed() throws Exception {
        locations.setLastKnownLocation("gps",fix(1000));
        ServiceController<TrackingService> controller=Robolectric.buildService(TrackingService.class).create();
        try {
            drain(controller.get());
            assertEquals(1,prefs.getLong("metric_network_request_errors",0));
            assertEquals(1,prefs.getLong("metric_saved",0));
            assertTrue(prefs.getBoolean("gnss_registered",false));
        } finally { controller.destroy(); }
    }
    @Test public void silentSubscriptionRecoversWithoutDuplicatesAndRetriesAreThrottled() throws Exception {
        ServiceController<TrackingService> controller=Robolectric.buildService(TrackingService.class).create();
        TrackingService service=controller.get();
        try {
            drain(service);
            manager.removeUpdates(service); // Simulate lost registration after head-unit sleep.
            ShadowSystemClock.advanceBy(Duration.ofSeconds(121));
            service.checkGpsHealth();
            assertEquals(1,locations.getLocationUpdateListeners("gps").size());
            assertEquals(1,prefs.getLong("metric_gps_resubscriptions",0));
            service.checkGpsHealth();
            assertEquals(1,prefs.getLong("metric_gps_resubscriptions",0));
            service.onLocationChanged(fix(0));drain(service);
            assertEquals(1,prefs.getLong("metric_saved",0));
            ShadowSystemClock.advanceBy(Duration.ofSeconds(100));
            service.onLocationChanged(fix(0));drain(service);
            ShadowSystemClock.advanceBy(Duration.ofSeconds(30));
            service.checkGpsHealth();
            assertEquals("Live fixes suppress retries",1,prefs.getLong("metric_gps_resubscriptions",0));
        } finally { controller.destroy(); }
    }
    @Test public void disabledGpsIsNotRepeatedlyRequested() throws Exception {
        locations.setProviderEnabled("gps",false);
        ServiceController<TrackingService> controller=Robolectric.buildService(TrackingService.class).create();
        try {
            drain(controller.get());
            ShadowSystemClock.advanceBy(Duration.ofSeconds(121));
            controller.get().checkGpsHealth();
            assertFalse(prefs.getBoolean("gps_provider_enabled",true));
            assertEquals(0,prefs.getLong("metric_gps_resubscriptions",0));
        } finally { controller.destroy(); }
    }
}
