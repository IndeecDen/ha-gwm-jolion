package ru.jolion.locator;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import org.junit.*;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.RuntimeEnvironment;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.SQLiteMode;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = 27, manifest = Config.NONE)
@SQLiteMode(SQLiteMode.Mode.LEGACY)
public class QueueDbTest {
    private QueueDb db;
    private Context context;
    @Before public void setUp() { context = RuntimeEnvironment.getApplication(); context.deleteDatabase("points.db"); db = new QueueDb(context); }
    @After public void tearDown() { db.close(); context.deleteDatabase("points.db"); }
    private JSONObject point(int i) throws Exception { return new JSONObject().put("id", "point-" + i).put("timestamp_ms", i); }

    @Test public void sendsLatestThenOldestBacklog() throws Exception {
        for(int i=1;i<=205;i++) db.append(point(i));
        JSONArray batch = db.batch();
        assertEquals(200,batch.length());
        assertEquals("point-205",batch.getJSONObject(0).getString("id"));
        assertEquals("point-1",batch.getJSONObject(1).getString("id"));
        assertEquals("point-199",batch.getJSONObject(199).getString("id"));
        assertEquals(205,db.count());
    }
    @Test public void survivesReopenAndDeletesOnlyAcknowledged() throws Exception {
        db.append(point(1)); db.append(point(2)); db.close();
        db = new QueueDb(context);
        assertEquals(2,db.count());
        JSONArray sent=db.batch();
        db.acknowledge(new JSONArray().put("point-1"),sent);
        assertEquals(1,db.count());
        assertEquals("point-2",db.batch().getJSONObject(0).getString("id"));
    }
    @Test public void invalidAcknowledgementDoesNotDeleteAnything() throws Exception {
        db.append(point(1)); db.append(point(2));
        try {db.acknowledge(new JSONArray().put("point-1").put("foreign-id"),db.batch());fail("Expected rejection");}
        catch(IllegalArgumentException expected) {}
        assertEquals(2,db.count());
    }
    @Test public void pendingUnsentPointCannotBeDeletedByReply() throws Exception {
        db.append(point(1)); JSONArray sent=db.batch(); db.append(point(2));
        try {db.acknowledge(new JSONArray().put("point-2"),sent);fail("Expected rejection");}
        catch(IllegalArgumentException expected) {}
        assertEquals(2,db.count());
    }
    @Test public void destinationsNeverMixAfterSettingsChangeAndReopen() throws Exception {
        db.append(point(1),"https://old.test","car-a","old-key");
        db.append(point(2),"https://new.test","car-b","new-key");
        db.append(point(3),"https://old.test","car-a","old-key");
        ru.jolion.locator.Config.prefs(context).edit().putString("url","https://new.test").putString("vehicle","car-b").commit();
        db.close();db=new QueueDb(context);
        QueueDb.Batch batch=db.uploadBatch();
        assertEquals("https://old.test",batch.base);assertEquals("car-a",batch.vehicle);
        assertEquals("old-key",batch.token);assertEquals(2,batch.points.length());
        assertEquals("point-3",batch.points.getJSONObject(0).getString("id"));
        db.acknowledge(new JSONArray().put("point-1").put("point-3"),batch.points);
        batch=db.uploadBatch();assertEquals("https://new.test",batch.base);
        assertEquals("car-b",batch.vehicle);assertEquals(1,batch.points.length());
    }
    @Test public void rotatedKeyDoesNotDelayLatestLocationBehindOldBacklog() throws Exception {
        for(int i=1;i<=205;i++) db.append(point(i),"https://ha.test","car","old-key");
        db.append(point(206),"https://ha.test","car","new-key");
        QueueDb.Batch batch=db.uploadBatch();
        assertEquals("point-206",batch.points.getJSONObject(0).getString("id"));
        assertEquals(200,batch.points.length());
        assertEquals("point-1",batch.points.getJSONObject(1).getString("id"));
    }
    @Test public void modeSwitchJournalSurvivesRestartAndKeepsOtherVehicle() throws Exception {
        db.append(point(1),"https://ha.test","jolion","old");
        db.append(point(2),"https://ha.test","other","other-key");
        db.close();
        ru.jolion.locator.Config.prefs(context).edit().putString("vehicle","jolion").putString("transport","yandex_disk").putString("disk_folder","/JolionLocator").putString("disk_oauth","disk-token").putString("key","new-key").putString("route_from","https://ha.test").commit();
        db=new QueueDb(context);
        QueueDb.Batch batch=db.uploadBatch();assertEquals("yadisk:/JolionLocator",batch.base);assertEquals("disk-token",batch.relayToken);assertEquals("new-key",batch.token);
        assertEquals(1,batch.points.length());assertEquals(2,db.count());
        assertFalse(ru.jolion.locator.Config.prefs(context).contains("route_from"));
        db.acknowledge(new JSONArray().put("point-1"),batch.points);
        assertEquals("other",db.uploadBatch().vehicle);assertEquals("https://ha.test",db.uploadBatch().base);
    }
    @Test public void diskBatchDoesNotMixEncryptionKeys() throws Exception {
        db.append(point(1),"yadisk:/Folder","jolion","key-a","oauth");
        db.append(point(2),"yadisk:/Folder","jolion","key-b","oauth");
        assertEquals(1,db.uploadBatch().points.length());assertEquals("key-a",db.uploadBatch().token);
    }
    @Test public void versionTwoUpgradePreservesDestinationsAndAddsIndex() throws Exception {
        db.close();context.deleteDatabase("points.db");
        android.database.sqlite.SQLiteDatabase old=context.openOrCreateDatabase("points.db",0,null);
        old.execSQL("CREATE TABLE points (seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,body TEXT NOT NULL,base TEXT NOT NULL,vehicle TEXT NOT NULL,token TEXT NOT NULL)");
        old.execSQL("INSERT INTO points(id,body,base,vehicle,token) VALUES (?,?,?,?,?)",new Object[]{"point-1",point(1).toString(),"https://kept.test","car","key"});
        old.setVersion(2);old.close();
        db=new QueueDb(context);
        assertEquals("https://kept.test",db.uploadBatch().base);
        assertEquals(1,db.count());
        try(android.database.Cursor c=db.getReadableDatabase().rawQuery("SELECT name FROM sqlite_master WHERE name='queue_destination'",null)) {
            assertTrue(c.moveToFirst());
        }
        assertEquals(4,db.getReadableDatabase().getVersion());
    }
    @Test public void versionOneQueueMigratesWithoutLosingPoints() throws Exception {
        db.close();context.deleteDatabase("points.db");
        android.database.sqlite.SQLiteDatabase old=context.openOrCreateDatabase("points.db",0,null);
        old.execSQL("CREATE TABLE points (seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,body TEXT NOT NULL)");
        old.execSQL("INSERT INTO points(id,body) VALUES (?,?)",new Object[]{"point-1",point(1).toString()});
        old.setVersion(1);old.close();
        ru.jolion.locator.Config.prefs(context).edit().putString("url","https://legacy.test").putString("vehicle","legacy").putString("key","legacy-key").commit();
        db=new QueueDb(context);
        QueueDb.Batch batch=db.uploadBatch();assertEquals("https://legacy.test",batch.base);
        assertEquals("legacy",batch.vehicle);assertEquals("legacy-key",batch.token);
        assertEquals("point-1",batch.points.getJSONObject(0).getString("id"));
        assertEquals(1,db.count());
    }
}
