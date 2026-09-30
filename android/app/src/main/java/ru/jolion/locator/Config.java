package ru.jolion.locator;

import android.content.Context;
import android.content.SharedPreferences;
import java.security.SecureRandom;

final class Config {
    /** Shortest and longest gap between uploads the app accepts, in seconds. */
    static final int MIN_INTERVAL_SECONDS = 5;
    static final int MAX_INTERVAL_SECONDS = 300;
    static final int DEFAULT_INTERVAL_SECONDS = 30;

    /**
     * Parse the configured upload interval.
     *
     * Returns {@link #DEFAULT_INTERVAL_SECONDS} for an empty field and null for
     * anything unusable or out of range, so a typo is reported instead of being
     * silently clamped to a value the driver did not ask for.
     */
    static Integer parseInterval(String raw) {
        if (raw == null) return null;
        String text = raw.trim();
        if (text.isEmpty()) return DEFAULT_INTERVAL_SECONDS;
        int seconds;
        try { seconds = Integer.parseInt(text); }
        catch (NumberFormatException error) { return null; }
        if (seconds < MIN_INTERVAL_SECONDS || seconds > MAX_INTERVAL_SECONDS) return null;
        return seconds;
    }

    /**
     * The interval the driver chose, in seconds.
     *
     * Reads through {@link SharedPreferences#getAll()} rather than {@code getString}:
     * a value written as an int (an earlier build did exactly that) makes
     * {@code getString} throw {@link ClassCastException}, which would take down the
     * tracking service on every upload. Any stored type is accepted here instead.
     */
    static int intervalSeconds(Context c) {
        Object stored = prefs(c).getAll().get("interval");
        Integer parsed = parseInterval(stored == null ? null : String.valueOf(stored));
        return parsed == null ? DEFAULT_INTERVAL_SECONDS : parsed;
    }

    static SharedPreferences prefs(Context c) { return c.getSharedPreferences("locator", Context.MODE_PRIVATE); }
    static String destination(Context c) {
        return "yandex_disk".equals(prefs(c).getString("transport","https")) ? "yadisk:"+prefs(c).getString("disk_folder","/JolionLocator") : prefs(c).getString("url","");
    }
    static String key(Context c) {
        String key = prefs(c).getString("key", "");
        if (key.isEmpty()) {
            byte[] bytes = new byte[24]; new SecureRandom().nextBytes(bytes);
            StringBuilder out = new StringBuilder();
            for (byte b : bytes) out.append(String.format("%02x", b & 255));
            key = out.toString(); prefs(c).edit().putString("key", key).commit();
        }
        return key;
    }
}
