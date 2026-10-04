package ru.jolion.locator;

import android.content.Context;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;
import org.json.JSONArray;
import org.json.JSONObject;

final class QueueDb extends SQLiteOpenHelper {
    private final Context context;
    QueueDb(Context c) { super(c, "points.db", null, 4); context=c.getApplicationContext(); }
    public void onConfigure(SQLiteDatabase db) { db.execSQL("PRAGMA synchronous=FULL"); }
    public void onOpen(SQLiteDatabase db) {
        synchronized(Config.class) {
            String old=Config.prefs(context).getString("route_from", "");
            if(!old.isEmpty()) {
                ContentValues v=new ContentValues();v.put("base",Config.destination(context));v.put("token",Config.key(context));v.put("relay_token",Config.diskOauth(context));
                db.update("points",v,"base=? AND vehicle=?",new String[]{old,Config.prefs(context).getString("vehicle","jolion")});
                Config.prefs(context).edit().remove("route_from").commit();
            }
        }
    }
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE points (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, body TEXT NOT NULL)");
        addDestination(db);
        indexDestination(db);
        addRelay(db);
    }
    private void addDestination(SQLiteDatabase db) {
        db.execSQL("ALTER TABLE points ADD COLUMN base TEXT NOT NULL DEFAULT ''");
        db.execSQL("ALTER TABLE points ADD COLUMN vehicle TEXT NOT NULL DEFAULT ''");
        db.execSQL("ALTER TABLE points ADD COLUMN token TEXT NOT NULL DEFAULT ''");
        ContentValues values=new ContentValues();
        values.put("base", Config.prefs(context).getString("url", ""));
        values.put("vehicle", Config.prefs(context).getString("vehicle", "jolion"));
        values.put("token", Config.key(context));
        db.update("points",values,null,null);
    }
    public void onUpgrade(SQLiteDatabase db, int oldVersion, int newVersion) {
        if(oldVersion<1 || oldVersion>3 || newVersion!=4) throw new IllegalStateException("Unsupported queue version");
        if(oldVersion<2) addDestination(db);
        indexDestination(db);
        addRelay(db);
    }
    private void addRelay(SQLiteDatabase db) { db.execSQL("ALTER TABLE points ADD COLUMN relay_token TEXT NOT NULL DEFAULT ''"); }
    private void indexDestination(SQLiteDatabase db) {
        db.execSQL("CREATE INDEX IF NOT EXISTS queue_destination ON points(base,vehicle,seq)");
    }
    void append(JSONObject point) throws Exception {
         append(point,Config.prefs(context).getString("url", ""),Config.prefs(context).getString("vehicle", "jolion"),Config.key(context));
    }
    void append(JSONObject point, String base, String vehicle, String token) throws Exception {
        append(point,base,vehicle,token,"");
    }
    void append(JSONObject point, String base, String vehicle, String token, String relayToken) throws Exception {
        ContentValues v = new ContentValues(); v.put("id", point.getString("id")); v.put("body", point.toString());
        v.put("base",base);v.put("vehicle",vehicle);v.put("token",token);v.put("relay_token",relayToken);
        getWritableDatabase().insertOrThrow("points", null, v);
    }
    void reroute(String oldBase,String newBase,String vehicle,String key,String relayToken) {
        ContentValues values=new ContentValues();values.put("base",newBase);values.put("token",key);values.put("relay_token",relayToken);
        getWritableDatabase().update("points",values,"base=? AND vehicle=?",new String[]{oldBase,vehicle});
    }
    static final class Batch {
        final String base,vehicle,token,relayToken;
        final JSONArray points;
        Batch(String b,String v,String t,JSONArray p) {this(b,v,t,"",p);}
        Batch(String b,String v,String t,String r,JSONArray p) {base=b;vehicle=v;token=t;relayToken=r;points=p;}
    }
    Batch uploadBatch() throws Exception {
        try(Cursor c=getReadableDatabase().rawQuery("SELECT base,vehicle,token,relay_token FROM points ORDER BY seq LIMIT 1",null)) {
            if(!c.moveToFirst())return null;
            String base=c.getString(0),vehicle=c.getString(1),token=c.getString(2);
            JSONArray points=new JSONArray();
            // Authentication can rotate without changing the destination of recorded points.
            boolean relay=base.startsWith("yadisk:");
            String relayToken=c.getString(3);
            String group="base=? AND vehicle=?"+(relay?" AND token=? AND relay_token=?":"");
            java.util.ArrayList<String> args=new java.util.ArrayList<>();
             for(int i=0;i<3;i++){args.add(base);args.add(vehicle);if(relay){args.add(token);args.add(relayToken);}}
             String sql="SELECT body FROM points WHERE seq=(SELECT MAX(seq) FROM points WHERE "+group+") UNION ALL SELECT body FROM (SELECT body FROM points WHERE "+group+" AND seq<(SELECT MAX(seq) FROM points WHERE "+group+") ORDER BY seq LIMIT 199)";
             try(Cursor rows=getReadableDatabase().rawQuery(sql,args.toArray(new String[0]))) {
                 int bytes=32;
                 while(rows.moveToNext()) {
                     String body=rows.getString(0);
                     if (bytes + body.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 60000 && points.length() > 0) break;
                     points.put(new JSONObject(body)); bytes += body.getBytes(java.nio.charset.StandardCharsets.UTF_8).length;
                 }
             }
            return new Batch(base,vehicle,token,relayToken,points);
        }
    }
    JSONArray batch() throws Exception {
        Batch batch=uploadBatch();
        return batch==null ? new JSONArray() : batch.points;
    }
    void acknowledge(JSONArray ids, JSONArray sent) throws Exception {
        java.util.HashSet<String> expected = new java.util.HashSet<>();
        for (int i=0; i<sent.length(); i++) expected.add(sent.getJSONObject(i).getString("id"));
        java.util.ArrayList<String> checked = new java.util.ArrayList<>();
        for (int i=0; i<ids.length(); i++) {
            String id = ids.getString(i);
            if (!expected.contains(id)) throw new IllegalArgumentException("Unexpected acknowledgement");
            checked.add(id);
        }
        SQLiteDatabase db = getWritableDatabase(); db.beginTransaction();
        try {
            for (String id : checked) db.delete("points", "id=?", new String[]{id});
            db.setTransactionSuccessful();
        } finally { db.endTransaction(); }
    }
    long count() {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT COUNT(*) FROM points", null)) { c.moveToFirst(); return c.getLong(0); }
    }
}
