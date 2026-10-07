package ru.jolion.locator;

import android.app.Dialog;
import android.os.Looper;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.concurrent.atomic.AtomicBoolean;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.LooperMode;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27)
@LooperMode(LooperMode.Mode.PAUSED)
public class UpdateLifecycleTest {
    @Test public void destroyedScreenIgnoresQueuedUpdateCallbacksAndClosesDialog() throws Exception {
        Config.prefs(RuntimeEnvironment.getApplication()).edit().clear().commit();
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create();
        MainActivity activity=controller.get();
        Method confirm=MainActivity.class.getDeclaredMethod("confirmUpdate",UpdateChecker.Release.class);confirm.setAccessible(true);
        confirm.invoke(activity,new UpdateChecker.Release("1.0.0","notes","https://local/apk","https://local/sums","test.apk",100));
        Field field=MainActivity.class.getDeclaredField("updateDialog");field.setAccessible(true);
        Dialog dialog=(Dialog)field.get(activity);assertTrue(dialog.isShowing());
        Method update=MainActivity.class.getDeclaredMethod("updateUi",Runnable.class);update.setAccessible(true);
        AtomicBoolean called=new AtomicBoolean();
        Thread reply=new Thread(()->{
            try { update.invoke(activity,(Runnable)()->called.set(true)); }
            catch(Exception error){throw new AssertionError(error);}
        });
        reply.start();reply.join();
        controller.destroy();
        Shadows.shadowOf(Looper.getMainLooper()).idle();
        assertFalse(dialog.isShowing());assertFalse(called.get());
    }
}
