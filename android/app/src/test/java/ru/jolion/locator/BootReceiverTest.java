package ru.jolion.locator;
import android.content.*;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk=27,manifest=Config.NONE)
public class BootReceiverTest {
    private int starts;
    private Context context;
    @Before public void setup(){
        context=new ContextWrapper(RuntimeEnvironment.getApplication()){
            @Override public ComponentName startForegroundService(Intent intent){starts++;return intent.getComponent();}
        };
        ru.jolion.locator.Config.prefs(context).edit().clear().commit();
    }
    @Test public void startsEnabledRecordingOnBootAndUpdate(){
        ru.jolion.locator.Config.prefs(context).edit().putBoolean("enabled",true).commit();
        new BootReceiver().onReceive(context,new Intent(Intent.ACTION_BOOT_COMPLETED));
        new BootReceiver().onReceive(context,new Intent(Intent.ACTION_MY_PACKAGE_REPLACED));
        assertEquals(2,starts);
    }
    @Test public void respectsAutostartAndStopAndUnknownActions(){
        BootReceiver receiver=new BootReceiver();
        receiver.onReceive(context,new Intent(Intent.ACTION_BOOT_COMPLETED));
        ru.jolion.locator.Config.prefs(context).edit().putBoolean("enabled",true).putBoolean("autostart",false).commit();
        receiver.onReceive(context,new Intent(Intent.ACTION_BOOT_COMPLETED));
        ru.jolion.locator.Config.prefs(context).edit().putBoolean("autostart",true).commit();
        receiver.onReceive(context,new Intent("unknown"));assertEquals(0,starts);
    }
}
