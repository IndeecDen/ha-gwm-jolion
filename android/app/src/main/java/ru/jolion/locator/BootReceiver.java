package ru.jolion.locator;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
public class BootReceiver extends BroadcastReceiver {
    public void onReceive(Context c, Intent intent) {
        String action = intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action) && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)) return;
        if (Config.prefs(c).getBoolean("enabled", false) && Config.prefs(c).getBoolean("autostart", true)) {
            try { c.startForegroundService(new Intent(c, TrackingService.class)); }
            catch (RuntimeException error) { Config.prefs(c).edit().putString("status", "ГУ запретило автозапуск. Откройте приложение и разрешите фоновую работу в настройках ГУ.").apply(); }
        }
    }
}
