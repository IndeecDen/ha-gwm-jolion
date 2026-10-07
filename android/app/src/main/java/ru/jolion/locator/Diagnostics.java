package ru.jolion.locator;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;
import org.json.JSONObject;

/** Allowlist only: preferences can contain credentials, coordinates and URLs. */
final class Diagnostics {
    static JSONObject snapshot(Context context) throws Exception {
        JSONObject report=new JSONObject();
        report.put("schema",1);
        report.put("created_at_ms",System.currentTimeMillis());
        report.put("app_version",context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionName);
        report.put("app_version_code",context.getPackageManager().getPackageInfo(context.getPackageName(),0).versionCode);
        report.put("android_api",Build.VERSION.SDK_INT);
        report.put("supported_abis",new org.json.JSONArray(java.util.Arrays.asList(Build.SUPPORTED_ABIS)));
        SharedPreferences prefs=Config.prefs(context);
        JSONObject values=new JSONObject();
        for(String key:new String[]{"enabled","autostart","queued","last_fix","last_sync","cold_start_ms",
                "first_fix_at","service_created_at","foreground_started_at","db_ready_at","gps_requested_at",
                "gnss_used","gnss_visible","gnss_gps","gnss_glonass","gnss_galileo","gnss_beidou",
                "gps_provider_enabled","network_provider_enabled","gps_subscribed","network_subscribed",
                "gnss_registered","gnss_status_at","gnss_ttff_ms","last_gps_callback_at","last_network_callback_at"}) {
            Object value=prefs.getAll().get(key);
            if(value instanceof Number || value instanceof Boolean)values.put(key,value);
        }
        for(java.util.Map.Entry<String,?> entry:prefs.getAll().entrySet())
            if(entry.getKey().startsWith("metric_") && entry.getValue() instanceof Number)values.put(entry.getKey(),entry.getValue());
        String gps=prefs.getString("gps_state","");
        if(java.util.Arrays.asList("COLD_START","GPS_ACTIVE","GPS_LOST","GPS_RECOVERING","STATIONARY").contains(gps))values.put("gps_state",gps);
        String stage=prefs.getString("startup_stage","");
        if(java.util.Arrays.asList("FOREGROUND_STARTING","FOREGROUND_STARTED","DB_READY","DB_ERROR","GPS_REQUESTED","FIRST_FIX").contains(stage))values.put("startup_stage",stage);
        values.put("transport","yandex_disk".equals(prefs.getString("transport","https"))?"yandex_disk":"https");
        // Free-form exception text can include tokens/URLs. Export presence only.
        for(String key:new String[]{"storage_error","secret_error"})values.put("has_"+key,!prefs.getString(key,"").isEmpty());
        report.put("tracking",values);
        JSONObject boot=new JSONObject();
        for(java.util.Map.Entry<String,?> entry:Config.bootPrefs(context).getAll().entrySet())
            if(entry.getValue() instanceof Long && (entry.getKey().equals("last_boot_event") || entry.getKey().equals("last_service_start")))boot.put(entry.getKey(),entry.getValue());
        report.put("boot",boot);
        report.put("free_storage_bytes",context.getFilesDir().getUsableSpace());
        return report;
    }
}
