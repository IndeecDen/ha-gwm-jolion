package ru.jolion.locator;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
public class BootReceiver extends BroadcastReceiver {
    static final String ACTION_WATCHDOG = "ru.jolion.locator.WATCHDOG";
    public void onReceive(Context c, Intent intent) {
        String action = intent.getAction();
        if (ACTION_WATCHDOG.equals(action)) {
            if (Config.prefs(c).getBoolean("enabled", false) && Config.prefs(c).getBoolean("autostart", true)) {
                try { c.startForegroundService(new Intent(c, TrackingService.class)); }
                catch (RuntimeException error) { Config.prefs(c).edit().putString("status", "Не удалось восстановить фоновую запись").apply(); }
            }
            return;
        }
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action) && !Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action)
                && !Intent.ACTION_USER_UNLOCKED.equals(action) && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) return;
        Config.bootPrefs(c).edit().putLong("last_boot_event", System.currentTimeMillis()).putString("last_boot_action", action).commit();
        boolean locked = Intent.ACTION_LOCKED_BOOT_COMPLETED.equals(action);
        // Direct Boot is used only to record the event. The actual service waits
        // for USER_UNLOCKED because its queue and Keystore secrets live in the
        // credential-protected storage and must not be opened before unlock.
        if (locked) return;
        if (Config.autostartEnabled(c)) {
            try {
                Config.prefs(c).edit().putLong("boot_start_requested", System.currentTimeMillis()).apply();
                c.startForegroundService(new Intent(c, TrackingService.class));
            } catch (RuntimeException error) { Config.prefs(c).edit().putString("status", "ГУ запретило автозапуск. Откройте приложение и разрешите фоновую работу в настройках ГУ.").apply(); }
        }
    }
}
