package ru.jolion.locator;

import android.Manifest;
import android.app.Activity;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.text.InputType;
import android.widget.*;
import java.net.URI;
import java.text.DateFormat;
import java.util.Date;

public class MainActivity extends Activity {
    private EditText url, vehicle, key, diskFolder, diskOauth, interval;
    private Spinner transport;
    private TextView status;
    private final Handler timer = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        public void run() {
            SharedPreferences p = Config.prefs(MainActivity.this);
            status.setText((p.getBoolean("enabled", false) ? "Запись включена" : "Запись остановлена") + "\n" + p.getString("gps_status", "GPS ещё не получен")
                + "\n" + p.getString("quality", "Точность GPS ещё неизвестна") + "\nТочек в очереди: " + p.getLong("queued", 0) + "\nПоследний GPS: " + date(p.getLong("last_fix", 0))
                + "\nОтправлено: " + date(p.getLong("last_sync", 0)) + "\n" + p.getString("status", "Введите настройки и нажмите «Начать запись»")
                + "\n" + p.getString("storage_error", "") + (getFilesDir().getUsableSpace() < 100*1024*1024 ? "\nМало места: осталось менее 100 МБ!" : ""));
            timer.postDelayed(this, 2000);
        }
    };
    private String date(long ms) { return ms == 0 ? "—" : DateFormat.getDateTimeInstance().format(new Date(ms)); }
    public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); layout.setPadding(32, 20, 32, 24);
        ScrollView scroll = new ScrollView(this); scroll.addView(layout); setContentView(scroll);
        TextView title = new TextView(this); title.setText("Jolion Locator"); title.setTextSize(28); layout.addView(title);
        SharedPreferences p = Config.prefs(this);
        transport=new Spinner(this);
        transport.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Напрямую HTTPS → Home Assistant","Через опубликованную папку Яндекс.Диска"}));
        layout.addView(transport);
        LinearLayout directBox=new LinearLayout(this);directBox.setOrientation(LinearLayout.VERTICAL);layout.addView(directBox);
        url = field(directBox, "Адрес Home Assistant: https://ha.example.ru", p.getString("url", ""));
        LinearLayout diskBox=new LinearLayout(this);diskBox.setOrientation(LinearLayout.VERTICAL);layout.addView(diskBox);
        diskFolder=field(diskBox,"Папка на Диске (заранее создайте и опубликуйте)",p.getString("disk_folder","/JolionLocator"));
        diskOauth=field(diskBox,"OAuth-токен Яндекс.Диска (только в приложении)",p.getString("disk_oauth",""));
        diskOauth.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        TextView diskHelp=new TextView(this);diskHelp.setText("Файлы шифруются ключом Locator. В HA выберите Яндекс.Диск и укажите публичную ссылку этой папки. Доступ через белый список зависит от оператора. При смене способа накопленная очередь этого автомобиля переводится на выбранный способ.");diskBox.addView(diskHelp);
        interval=field(layout,"Интервал отправки, секунд ("+Config.MIN_INTERVAL_SECONDS+"–"+Config.MAX_INTERVAL_SECONDS+")",String.valueOf(Config.intervalSeconds(this)));
        transport.setSelection("yandex_disk".equals(p.getString("transport","https"))?1:0);
        transport.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onItemSelected(AdapterView<?> parent,android.view.View view,int position,long id){directBox.setVisibility(position==0?android.view.View.VISIBLE:android.view.View.GONE);diskBox.setVisibility(position==1?android.view.View.VISIBLE:android.view.View.GONE);}
            public void onNothingSelected(AdapterView<?> parent){}
        });
        vehicle = field(layout, "ID автомобиля (тот же в интеграции)", p.getString("vehicle", "jolion"));
        key = field(layout, "Ключ автомобиля (перенесите в интеграцию HA)", Config.key(this));
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        CheckBox show = new CheckBox(this); show.setText("Показать ключ");
        show.setOnCheckedChangeListener((b, checked) -> key.setInputType(InputType.TYPE_CLASS_TEXT | (checked ? InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD : InputType.TYPE_TEXT_VARIATION_PASSWORD)));
        layout.addView(show);
        CheckBox boot = new CheckBox(this); boot.setText("Автозапуск записи после включения ГУ"); boot.setChecked(p.getBoolean("autostart", true));
        boot.setOnCheckedChangeListener((b, checked) -> Config.prefs(this).edit().putBoolean("autostart", checked).commit()); layout.addView(boot);
        Button background = new Button(this); background.setText("Разрешить фоновую работу / автозапуск"); background.setOnClickListener(v -> {
            new android.app.AlertDialog.Builder(this)
                .setTitle("Фоновая работа")
                .setMessage("Для непрерывной записи Android и прошивка ГУ не должны останавливать приложение. Если система предложит исключение из оптимизации батареи, разрешите его. Также добавьте Jolion Locator в список автозапуска прошивки, если такой список есть.")
                .setNegativeButton("Не сейчас", null)
                .setPositiveButton("Открыть настройки", (dialog, which) -> backgroundSettings())
                .show();
        }); layout.addView(background);
        TextView bootHelp = new TextView(this); bootHelp.setText("Для автозапуска сначала сохраните настройки и начните запись. Кнопка «Остановить запись» отключает запись до следующего ручного запуска. Если прошивка ГУ управляет списком автозапуска, разрешите в нём Jolion Locator."); layout.addView(bootHelp);
        Button qr = new Button(this); qr.setText("Показать QR подключения"); qr.setOnClickListener(v -> showPairing()); layout.addView(qr);
        Button start = new Button(this); start.setText("Сохранить и начать запись"); start.setOnClickListener(v -> start()); layout.addView(start);
        Button stop = new Button(this); stop.setText("Остановить запись"); stop.setOnClickListener(v -> {
            Config.prefs(this).edit().putBoolean("enabled", false).commit(); stopService(new Intent(this, TrackingService.class));
        }); layout.addView(stop);
        status = new TextView(this); status.setTextSize(18); status.setTextIsSelectable(true); layout.addView(status);
        TextView info = new TextView(this); info.setText("Android: " + Build.VERSION.RELEASE + " · API " + Build.VERSION.SDK_INT + "\nGPS запрашивается раз в секунду. Пока очередь пуста, отправка идёт каждые " + Config.intervalSeconds(this) + " секунд — одинаково для HTTPS и для Яндекс.Диска; как только очередь накапливается, точки уходят быстрее. Очередь хранится до подтверждения выбранного получателя — HA или Яндекс.Диска. Не очищайте данные приложения до синхронизации. Автозапуск и пробуждение нужно проверить на вашей прошивке."); layout.addView(info);
        TextView sync=new TextView(this);sync.setText("Для Яндекс.Диска этот интервал стоит выставить не больше, чем интервал опроса папки в настройках интеграции, иначе точки дольше лежат на Диске.");layout.addView(sync);
        if (p.getBoolean("enabled", false) && p.getBoolean("autostart", true) && checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
            startForegroundService(new Intent(this, TrackingService.class));
        }
    }
    private EditText field(LinearLayout parent, String hint, String value) {
        TextView label = new TextView(this); label.setText(hint); parent.addView(label);
        EditText field = new EditText(this); field.setSingleLine(true); field.setText(value); field.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS); parent.addView(field); return field;
    }
    private long queuedCount() {
        try (QueueDb db = new QueueDb(this)) { return db.count(); }
    }
    private void showPairing() {
        String id = vehicle.getText().toString().trim(), token = key.getText().toString().trim();
        if (!id.matches("[a-z0-9_-]{1,40}") || !token.matches("[A-Za-z0-9_-]{32,128}")) {
            Toast.makeText(this, "Проверьте ID и ключ", Toast.LENGTH_LONG).show(); return;
        }
        SharedPreferences p = Config.prefs(this);
        if (queuedCount() > 0 && !id.equals(p.getString("vehicle", "jolion"))) {
            Toast.makeText(this, "Сначала отправьте очередь с прежним ID", Toast.LENGTH_LONG).show(); return;
        }
        if (!p.edit().putString("vehicle", id).putString("key", token).commit()) {
            Toast.makeText(this, "Не удалось сохранить ключ", Toast.LENGTH_LONG).show(); return;
        }
        try {
            LinearLayout body = new LinearLayout(this); body.setOrientation(LinearLayout.VERTICAL); body.setPadding(24, 12, 24, 12);
            ImageView image = new ImageView(this); image.setImageBitmap(PairingQr.bitmap(id, token, 600)); image.setAdjustViewBounds(true);
            int size = Math.min(getResources().getDisplayMetrics().widthPixels - 100, (int)(280 * getResources().getDisplayMetrics().density));
            body.addView(image, new LinearLayout.LayoutParams(size, size));
            TextView text = new TextView(this); text.setText("ID: " + id + "\nКлюч: " + token + "\nВ настройках GWM Jolion включите Locator и нажмите «Ввести с QR» под ключом. Затем укажите адрес HA и начните запись."); text.setTextIsSelectable(true); body.addView(text);
            ScrollView scroll = new ScrollView(this); scroll.addView(body);
            new android.app.AlertDialog.Builder(this).setTitle("Подключение к Home Assistant").setView(scroll).setPositiveButton("Закрыть", null).show();
        } catch (Exception error) { Toast.makeText(this, "Не удалось создать QR", Toast.LENGTH_LONG).show(); }
    }
    private void backgroundSettings() {
        android.net.Uri packageUri=android.net.Uri.parse("package:"+getPackageName());
        PowerManager power=(PowerManager)getSystemService(POWER_SERVICE);
        Intent target = new Intent(power.isIgnoringBatteryOptimizations(getPackageName()) ? android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS : android.provider.Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, packageUri);
        try { startActivity(target); }
        catch (RuntimeException error) {
            try { startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS, packageUri)); }
            catch (RuntimeException unavailable) { Toast.makeText(this,"Эта прошивка не открывает настройки Android. Разрешите автозапуск Jolion Locator в меню ГУ.",Toast.LENGTH_LONG).show(); }
        }
    }
    private void start() {
        String base = url.getText().toString().trim().replaceAll("/+$", "");
        String id = vehicle.getText().toString().trim(); String token = key.getText().toString().trim();
        boolean disk=transport.getSelectedItemPosition()==1;
        String folder=diskFolder.getText().toString().trim(),oauth=diskOauth.getText().toString().trim();
        Integer seconds=Config.parseInterval(interval.getText().toString());
        if(seconds==null){Toast.makeText(this,"Интервал отправки: от "+Config.MIN_INTERVAL_SECONDS+" до "+Config.MAX_INTERVAL_SECONDS+" секунд",Toast.LENGTH_LONG).show();return;}
        try {
            URI uri = new URI(disk?"https://cloud-api.yandex.net":base);
            if (!"https".equals(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null) throw new Exception();
            if(disk && (!DiskTransport.validFolder(folder)||!oauth.matches("[!-~]{10,2048}")))throw new Exception();
            if (!id.matches("[a-z0-9_-]{1,40}") || !token.matches("[A-Za-z0-9_-]{32,128}")) throw new Exception();
        } catch (Exception e) { Toast.makeText(this, "Проверьте HTTPS или папку /JolionLocator и OAuth; ID a-z/0-9/_/-; ключ 32–128 символов", Toast.LENGTH_LONG).show(); return; }
        SharedPreferences p = Config.prefs(this);
        synchronized(Config.class) {
            String oldBase=Config.destination(this),newBase=disk?"yadisk:"+folder:base;
            boolean changedMode=oldBase.startsWith("yadisk:")!=disk;
            if(queuedCount()>0 && (!id.equals(p.getString("vehicle","jolion")) || (!changedMode && !newBase.equals(oldBase)))) {
                Toast.makeText(this,"С очередью можно сменить способ передачи, но нельзя менять ID или адрес внутри того же способа",Toast.LENGTH_LONG).show();return;
            }
            if(!p.edit().putString("url",base).putString("vehicle",id).putString("key",token).putString("transport",disk?"yandex_disk":"https").putString("disk_folder",folder).putString("disk_oauth",oauth).putString("interval",Integer.toString(seconds)).putString("route_from",changedMode?oldBase:"").commit()) {
                Toast.makeText(this,"Не удалось сохранить настройки",Toast.LENGTH_LONG).show();return;
            }
            if(changedMode)try(QueueDb db=new QueueDb(this)){db.reroute(oldBase,newBase,id,token,oauth);}
        }
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, 1); return;
        }
        p.edit().putBoolean("enabled", true).commit();
        startForegroundService(new Intent(this, TrackingService.class));
    }
    public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request == 1 && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) start();
    }
    public void onResume() { super.onResume(); timer.post(refresh); }
    public void onPause() { timer.removeCallbacks(refresh); super.onPause(); }
}
