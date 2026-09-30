package ru.jolion.locator;

import android.view.*;
import android.widget.*;
import org.json.JSONObject;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.*;
import org.robolectric.annotation.SQLiteMode;
import java.util.*;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@org.robolectric.annotation.Config(sdk=27)
@SQLiteMode(SQLiteMode.Mode.LEGACY)
public class TransportSettingsTest {
    private void collect(View view,List<View> result) {
        result.add(view);if(view instanceof ViewGroup){ViewGroup group=(ViewGroup)view;for(int i=0;i<group.getChildCount();i++)collect(group.getChildAt(i),result);}
    }
    @Test public void choosingDiskMovesExistingQueueWithoutChangingVehicle() throws Exception {
        android.content.Context context=RuntimeEnvironment.getApplication();
        context.deleteDatabase("points.db");
        Config.prefs(context).edit().clear().putString("url","https://ha.test").putString("vehicle","jolion").putString("key","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa").commit();
        try(QueueDb db=new QueueDb(context)){db.append(new JSONObject().put("id","queued-point-0001"));}
        org.robolectric.android.controller.ActivityController<MainActivity> controller=Robolectric.buildActivity(MainActivity.class).create();
        MainActivity activity=controller.get();List<View> views=new ArrayList<>();collect(activity.getWindow().getDecorView(),views);
        List<EditText> fields=new ArrayList<>();
        for(View view:views){if(view instanceof Spinner)((Spinner)view).setSelection(1);if(view instanceof EditText)fields.add((EditText)view);}
        fields.get(2).setText("oauth-token-for-test");
        for(View view:views)if(view instanceof Button && ((Button)view).getText().toString().equals("Сохранить и начать запись"))view.performClick();
        assertEquals("yandex_disk",Config.prefs(context).getString("transport",""));
        try(QueueDb db=new QueueDb(context)){QueueDb.Batch batch=db.uploadBatch();assertEquals("yadisk:/JolionLocator",batch.base);assertEquals("jolion",batch.vehicle);assertEquals("oauth-token-for-test",batch.relayToken);assertEquals(1,db.count());}
        controller.destroy();context.deleteDatabase("points.db");
    }
}
