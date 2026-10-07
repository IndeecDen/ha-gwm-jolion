package ru.jolion.locator;

import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27)
public class DiagnosticsTest {
    @Test public void exportsHealthWithoutCredentialsCoordinatesOrFreeformErrors() throws Exception {
        android.content.Context c=RuntimeEnvironment.getApplication();
        Config.prefs(c).edit().clear().putString("key","PRIVATE-KEY").putString("disk_oauth","PRIVATE-TOKEN")
            .putString("url","https://private.example").putString("network_last_latitude","55.123456")
            .putString("status","PRIVATE-ERROR").putString("storage_error","PRIVATE-STORAGE")
            .putLong("queued",42).putLong("metric_saved",12).putString("gps_state","STATIONARY")
            .putBoolean("gps_provider_enabled",true).putBoolean("gps_subscribed",true)
            .putLong("gnss_status_at",12345).putLong("last_gps_callback_at",23456).commit();
        JSONObject report=Diagnostics.snapshot(c);
        String text=report.toString();
        assertFalse(text.contains("PRIVATE"));assertFalse(text.contains("private.example"));assertFalse(text.contains("55.123456"));
        assertEquals(42,report.getJSONObject("tracking").getLong("queued"));
        assertTrue(report.getJSONObject("tracking").getBoolean("has_storage_error"));
        assertTrue(report.getJSONObject("tracking").getBoolean("gps_provider_enabled"));
        assertTrue(report.getJSONObject("tracking").getBoolean("gps_subscribed"));
        assertEquals(23456,report.getJSONObject("tracking").getLong("last_gps_callback_at"));
    }
}
