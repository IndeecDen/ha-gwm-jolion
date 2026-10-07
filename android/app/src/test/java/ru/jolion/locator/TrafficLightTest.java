package ru.jolion.locator;

import android.Manifest;
import android.app.Application;
import android.content.Context;
import android.location.Location;
import android.os.SystemClock;
import java.lang.reflect.Field;
import java.time.Duration;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.TimeUnit;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.SQLiteMode;
import org.robolectric.shadows.ShadowSystemClock;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27)
@SQLiteMode(SQLiteMode.Mode.LEGACY)
public class TrafficLightTest {
    private long timestamp=System.currentTimeMillis();
    private void drain(TrackingService service) throws Exception {
        Field field=TrackingService.class.getDeclaredField("writer");field.setAccessible(true);
        ((ExecutorService)field.get(service)).submit(()->{}).get(10,TimeUnit.SECONDS);
    }
    private void fix(TrackingService service,double meters,float speed) throws Exception {
        ShadowSystemClock.advanceBy(Duration.ofMillis(1500));
        timestamp+=1500;
        Location fix=new Location("gps");fix.setTime(timestamp);
        fix.setElapsedRealtimeNanos(SystemClock.elapsedRealtimeNanos());
        fix.setLatitude(55+meters/111195);fix.setLongitude(37);fix.setAccuracy(4);fix.setSpeed(speed);
        service.onLocationChanged(fix);drain(service);
    }
    @Test public void longLightKeepsHeartbeatAndRecordsSlowDepartureInsideParkingRadius() throws Exception {
        Context context=RuntimeEnvironment.getApplication();context.deleteDatabase("points.db");
        Config.prefs(context).edit().clear().putString("key","a".repeat(48)).putString("url","https://local.invalid").commit();
        Shadows.shadowOf((Application)context).grantPermissions(Manifest.permission.ACCESS_FINE_LOCATION);
        org.robolectric.android.controller.ServiceController<TrackingService> controller=Robolectric.buildService(TrackingService.class).create();
        TrackingService service=controller.get();drain(service);
        try {
            fix(service,0,8);fix(service,10,0);
            for(int i=0;i<40;i++)fix(service,10,0);
            long before=Config.prefs(context).getLong("metric_saved",0);
            assertTrue("Stationary heartbeat preserves the stop timeline",before>=5);
            assertTrue("Heartbeat does not store every stationary callback",before<10);
            fix(service,14,1.2f);fix(service,18,1.2f);fix(service,22,1.2f);
            assertEquals("Departure below former 7.2 km/h threshold is recorded",before+3,Config.prefs(context).getLong("metric_saved",0));
        } finally { controller.destroy(); }
    }
}
