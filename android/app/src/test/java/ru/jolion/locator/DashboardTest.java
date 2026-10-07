package ru.jolion.locator;

import android.content.SharedPreferences;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.LooperMode;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27,qualifiers="w1024dp-h600dp-land")
@LooperMode(LooperMode.Mode.PAUSED)
public class DashboardTest {
    private TextView find(View view,String text) {
        if(view instanceof TextView && text.equals(((TextView)view).getText().toString()))return (TextView)view;
        if(view instanceof ViewGroup)for(int i=0;i<((ViewGroup)view).getChildCount();i++) {
            TextView result=find(((ViewGroup)view).getChildAt(i),text);if(result!=null)return result;
        }
        return null;
    }
    @Test public void sectionsKeepEditingAndBackReturnsToDashboard() {
        Config.prefs(RuntimeEnvironment.getApplication()).edit().clear().commit();
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create().start().resume().visible();
        try {
            MainActivity activity=controller.get();View root=activity.findViewById(android.R.id.content);
            TextView settings=find(root,"Настройки");assertNotNull(settings);settings.performClick();
            TextView label=find(root,"ID автомобиля (тот же в интеграции)");assertTrue(label.isShown());
            ViewGroup parent=(ViewGroup)label.getParent();
            android.widget.EditText id=(android.widget.EditText)parent.getChildAt(parent.indexOfChild(label)+1);
            id.setText("edited-car");
            find(root,"Диагностика").performClick();
            assertFalse(label.isShown());assertTrue(find(root,"Сохранить диагностику").isShown());
            assertTrue(find(root,"Остановить запись").isShown());
            activity.onBackPressed();
            assertTrue(find(root,"GPS и спутники").isShown());assertFalse(activity.isFinishing());
            settings.performClick();assertEquals("edited-car",id.getText().toString());
        } finally {controller.pause().stop().destroy();}
    }
    @Test public void oldActiveStateCannotPresentStaleGpsAsLive() {
        SharedPreferences p=Config.prefs(RuntimeEnvironment.getApplication());
        p.edit().clear().putBoolean("enabled",true).putBoolean("gps_provider_enabled",true)
                .putString("gps_state","GPS_ACTIVE").putLong("last_gps_callback_at",1000).commit();
        assertEquals("Давно нет координат GPS",MainActivity.gpsHeadline(p,122000));
        assertEquals("GPS · движение",MainActivity.gpsHeadline(p,2000));
        p.edit().putBoolean("gps_provider_enabled",false).commit();
        assertEquals("GPS выключен в Android",MainActivity.gpsHeadline(p,2000));
        p.edit().putBoolean("enabled",false).commit();
        assertEquals("Запись остановлена",MainActivity.gpsHeadline(p,2000));
    }
}
