package ru.jolion.locator;

import android.Manifest;
import android.app.Activity;
import android.app.ProgressDialog;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.text.InputType;
import android.widget.*;
import android.net.Uri;
import java.io.File;
import java.net.URI;
import java.text.DateFormat;
import java.util.Date;

public class MainActivity extends Activity {
    private EditText url, vehicle, key, diskFolder, diskOauth, interval;
    private Spinner transport;
    private TextView status;
    private TextView recordingSummary, gpsSummary, deliverySummary, attention;
    private Button startButton, stopButton;
    private final ScrollView[] pages = new ScrollView[3];
    private final Button[] tabs = new Button[3];
    private int selectedPage;
    private File pendingUpdate;
    private Thread updateThread;
    private boolean updateBusy;
    private android.app.Dialog updateDialog;
    private final java.util.concurrent.ExecutorService settingsWorker=java.util.concurrent.Executors.newSingleThreadExecutor();
    private boolean settingsBusy;
    private boolean secretsReady;
    private int startGeneration;
    private final Handler timer = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new Runnable() {
        public void run() {
            SharedPreferences p = Config.prefs(MainActivity.this);
            renderDashboard(p);
            status.setText((p.getBoolean("enabled", false) ? "Запись включена" : "Запись остановлена") + "\n" + p.getString("gps_status", "GPS ещё не получен")
                + "\n" + p.getString("quality", "Точность GPS ещё неизвестна") + "\nТочек в очереди: " + p.getLong("queued", 0) + "\nПоследний GPS: " + date(p.getLong("last_fix", 0))
                + "\nСостояние GPS: " + p.getString("gps_state", "COLD_START") + "\n" + metrics(p) + "\n" + gnssSummary(p) + "\nЗапуск: " + p.getString("startup_stage", "—") + startupTiming(p) + "\nОтправлено: " + date(p.getLong("last_sync", 0)) + "\n" + p.getString("status", "Введите настройки и нажмите «Начать запись»")
                + (secretsReady ? "" : "\nЧтение ключей…") + (settingsBusy ? "\nСохранение настроек…" : "")
                + "\n" + p.getString("secret_error", "") + "\n" + p.getString("storage_error", "") + (getFilesDir().getUsableSpace() < 100*1024*1024 ? "\nМало места: осталось менее 100 МБ!" : ""));
            timer.postDelayed(this, 2000);
        }
    };
    private String date(long ms) { return ms == 0 ? "—" : DateFormat.getDateTimeInstance().format(new Date(ms)); }
    private String metrics(SharedPreferences p) {
        return "GPS: получено " + p.getLong("metric_received", 0) + ", сохранено " + p.getLong("metric_saved", 0)
            + ", отфильтровано " + (p.getLong("metric_rejected_transition", 0) + p.getLong("metric_rejected_provider", 0) + p.getLong("metric_rejected_stale", 0))
            + "; отправлено " + p.getLong("metric_uploaded", 0) + ", повторов " + p.getLong("metric_retries", 0);
    }
    private String startupTiming(SharedPreferences p) {
        long cold = p.getLong("cold_start_ms", 0);
        return cold > 0 ? " · первый GPS за " + (cold / 1000.0) + " с" : "";
    }
    static String gnssSummary(SharedPreferences p) {
        long updated=p.getLong("gnss_status_at",0);
        if (updated==0) return "GNSS: сведения о спутниках ещё не получены";
        long age=Math.max(0,(System.currentTimeMillis()-updated)/1000);
        return "GNSS: " + p.getLong("gnss_used",0) + "/" + p.getLong("gnss_visible",0)
                + " спутников (GPS " + p.getLong("gnss_gps",0) + ", GLONASS " + p.getLong("gnss_glonass",0)
                + ", Galileo " + p.getLong("gnss_galileo",0) + ")" + (age>30 ? " · данные " + age + " с назад" : "");
    }
    public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = column(); root.setPadding(dp(16),dp(8),dp(16),dp(8));
        setContentView(root);
        TextView title = new TextView(this); title.setText("Jolion Locator"); title.setTextSize(24); root.addView(title);
        LinearLayout navigation=new LinearLayout(this);root.addView(navigation);
        android.widget.FrameLayout body=new android.widget.FrameLayout(this);
        root.addView(body,new LinearLayout.LayoutParams(-1,0,1));
        String[] names={"Состояние","Настройки","Диагностика"};
        LinearLayout[] contents=new LinearLayout[3];
        for(int i=0;i<3;i++) {
            final int page=i;
            tabs[i]=button(names[i]);tabs[i].setOnClickListener(v->selectPage(page));
            navigation.addView(tabs[i],new LinearLayout.LayoutParams(0,-2,1));
            pages[i]=new ScrollView(this);pages[i].setFillViewport(true);
            contents[i]=column();contents[i].setPadding(0,dp(12),0,dp(12));pages[i].addView(contents[i]);
            body.addView(pages[i],new android.widget.FrameLayout.LayoutParams(-1,-1));
        }
        LinearLayout dashboard=contents[0], layout=contents[1], details=contents[2];
        recordingSummary=new TextView(this);recordingSummary.setTextSize(26);dashboard.addView(recordingSummary);
        attention=new TextView(this);attention.setTextSize(18);attention.setTextColor(0xff9b3500);dashboard.addView(attention);
        LinearLayout cards=new LinearLayout(this);
        boolean wide=getResources().getConfiguration().screenWidthDp>=700;
        cards.setOrientation(wide?LinearLayout.HORIZONTAL:LinearLayout.VERTICAL);dashboard.addView(cards);
        gpsSummary=summaryCard(cards,"GPS и спутники",wide);
        deliverySummary=summaryCard(cards,"Передача точек",wide);
        TextView hint=new TextView(this);hint.setText("Запись продолжится после закрытия экрана. Подключение и автозапуск — в настройках.");hint.setTextSize(16);dashboard.addView(hint);
        LinearLayout controls=new LinearLayout(this);root.addView(controls);
        SharedPreferences p = Config.prefs(this);
        transport=new Spinner(this);
        transport.setAdapter(new ArrayAdapter<String>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Напрямую HTTPS → Home Assistant","Через опубликованную папку Яндекс.Диска"}));
        layout.addView(transport);
        LinearLayout directBox=new LinearLayout(this);directBox.setOrientation(LinearLayout.VERTICAL);layout.addView(directBox);
        url = field(directBox, "Адрес Home Assistant: https://ha.example.ru", p.getString("url", ""));
        LinearLayout diskBox=new LinearLayout(this);diskBox.setOrientation(LinearLayout.VERTICAL);layout.addView(diskBox);
        diskFolder=field(diskBox,"Папка на Диске (заранее создайте и опубликуйте)",p.getString("disk_folder","/JolionLocator"));
        diskOauth=field(diskBox,"OAuth-токен Яндекс.Диска (только в приложении)","");
        diskOauth.setEnabled(false);
        diskOauth.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        TextView diskHelp=new TextView(this);diskHelp.setText("Файлы шифруются ключом Locator. В HA выберите Яндекс.Диск и укажите публичную ссылку этой папки. Доступ через белый список зависит от оператора. При смене способа накопленная очередь этого автомобиля переводится на выбранный способ.");diskBox.addView(diskHelp);
        interval=field(layout,"Интервал отправки, секунд ("+Config.MIN_INTERVAL_SECONDS+"–"+Config.MAX_INTERVAL_SECONDS+")",String.valueOf(Config.intervalSeconds(this)));
        transport.setSelection("yandex_disk".equals(p.getString("transport","https"))?1:0);
        transport.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onItemSelected(AdapterView<?> parent,android.view.View view,int position,long id){directBox.setVisibility(position==0?android.view.View.VISIBLE:android.view.View.GONE);diskBox.setVisibility(position==1?android.view.View.VISIBLE:android.view.View.GONE);}
            public void onNothingSelected(AdapterView<?> parent){}
        });
        vehicle = field(layout, "ID автомобиля (тот же в интеграции)", p.getString("vehicle", "jolion"));
        key = field(layout, "Ключ автомобиля (перенесите в интеграцию HA)", "");
        key.setEnabled(false);
        settingsWorker.execute(() -> {
            String savedKey=Config.key(getApplicationContext()), savedOauth=Config.diskOauth(getApplicationContext());
            updateUi(() -> { key.setText(savedKey); diskOauth.setText(savedOauth); key.setEnabled(true); diskOauth.setEnabled(true); secretsReady=true; renderDashboard(Config.prefs(this)); });
        });
        key.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        CheckBox show = new CheckBox(this); show.setText("Показать ключ");
        show.setOnCheckedChangeListener((b, checked) -> key.setInputType(InputType.TYPE_CLASS_TEXT | (checked ? InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD : InputType.TYPE_TEXT_VARIATION_PASSWORD)));
        layout.addView(show);
        CheckBox boot = new CheckBox(this); boot.setText("Автозапуск записи после включения ГУ"); boot.setChecked(p.getBoolean("autostart", true));
        boot.setOnCheckedChangeListener((b, checked) -> { Config.prefs(this).edit().putBoolean("autostart", checked).commit(); Config.mirrorBootState(this, p.getBoolean("enabled", false), checked); }); layout.addView(boot);
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
        Button updates = button("Проверить обновления"); updates.setOnClickListener(v -> checkUpdates()); details.addView(updates);
        Button diagnostics = new Button(this); diagnostics.setText("Сохранить диагностику"); diagnostics.setOnClickListener(v -> {
            Intent create=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/json").addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,"Jolion-Locator-diagnostics.json");
            try { startActivityForResult(create,2); }
            catch(RuntimeException error){Toast.makeText(this,"Выбор файла недоступен на этой прошивке",Toast.LENGTH_LONG).show();}
        }); details.addView(diagnostics);
        Button start = button("Сохранить и начать запись"); startButton=start; start.setOnClickListener(v -> start()); controls.addView(start,new LinearLayout.LayoutParams(0,-2,1));
        Button stop = new Button(this); stop.setText("Остановить запись"); stop.setOnClickListener(v -> {
            startGeneration++;
            Config.prefs(this).edit().putBoolean("enabled", false).commit(); Config.mirrorBootState(this, false, p.getBoolean("autostart", true)); stopService(new Intent(this, TrackingService.class));
            renderDashboard(p);
        }); stopButton=stop; controls.addView(stop,new LinearLayout.LayoutParams(0,-2,1));
        status = new TextView(this); status.setTextSize(18); status.setTextIsSelectable(true); details.addView(status);
        TextView info = new TextView(this); info.setText("Android: " + Build.VERSION.RELEASE + " · API " + Build.VERSION.SDK_INT + "\nGPS запрашивается каждые 1,5 секунды. Очередь хранится до подтверждения выбранного получателя — HA или Яндекс.Диска. Получение точек с Диска проверяется в Home Assistant."); details.addView(info);
        TextView sync=new TextView(this);sync.setText("Для Яндекс.Диска этот интервал стоит выставить не больше, чем интервал опроса папки в настройках интеграции, иначе точки дольше лежат на Диске.");layout.addView(sync);
        interval.setInputType(InputType.TYPE_CLASS_NUMBER);
        comfortableControls(root);
        selectPage(state==null?0:state.getInt("locator_page",0));
        renderDashboard(p);
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
        if (!secretsReady || settingsBusy) { Toast.makeText(this,"Дождитесь чтения или сохранения настроек",Toast.LENGTH_SHORT).show(); return; }
        String id = vehicle.getText().toString().trim(), token = key.getText().toString().trim();
        if (!id.matches("[a-z0-9_-]{1,40}") || !token.matches("[A-Za-z0-9_-]{32,128}")) {
            Toast.makeText(this, "Проверьте ID и ключ", Toast.LENGTH_LONG).show(); return;
        }
        settingsBusy=true;
        settingsWorker.execute(() -> {
            try {
                synchronized(Config.class) {
                    SharedPreferences p=Config.prefs(this);
                    if (queuedCount()>0 && !id.equals(p.getString("vehicle","jolion")))throw new IllegalStateException("Сначала отправьте очередь с прежним ID");
                    if (!p.edit().putString("vehicle",id).commit() || !Config.putSecrets(this,token,Config.diskOauth(this)))throw new IllegalStateException("Не удалось сохранить ключ");
                }
                android.graphics.Bitmap bitmap=PairingQr.bitmap(id,token,600);
                updateUi(() -> { settingsBusy=false; showPairingDialog(id,token,bitmap); });
            } catch(Exception error) { updateUi(() -> { settingsBusy=false; Toast.makeText(this,"Не удалось подготовить QR. Проверьте очередь и настройки.",Toast.LENGTH_LONG).show(); }); }
        });
    }
    private int dp(int value) { return Math.round(value*getResources().getDisplayMetrics().density); }
    private LinearLayout column() { LinearLayout box=new LinearLayout(this);box.setOrientation(LinearLayout.VERTICAL);return box; }
    private Button button(String text) { Button b=new Button(this);b.setText(text);b.setAllCaps(false);b.setTextSize(18);b.setMinHeight(dp(56));return b; }
    private TextView summaryCard(LinearLayout parent,String title,boolean wide) {
        LinearLayout box=column();box.setPadding(dp(16),dp(12),dp(16),dp(16));
        android.graphics.drawable.GradientDrawable background=new android.graphics.drawable.GradientDrawable();
        background.setColor(0xffeef2f5);background.setCornerRadius(dp(12));box.setBackground(background);
        LinearLayout.LayoutParams size=wide?new LinearLayout.LayoutParams(0,-2,1):new LinearLayout.LayoutParams(-1,-2);
        size.setMargins(dp(4),dp(8),dp(4),dp(12));parent.addView(box,size);
        TextView label=new TextView(this);label.setText(title);label.setTextSize(16);label.setTextColor(0xff415365);box.addView(label);
        TextView value=new TextView(this);value.setTextSize(20);value.setTextColor(0xff142536);value.setPadding(0,dp(8),0,0);box.addView(value);return value;
    }
    private void comfortableControls(android.view.View view) {
        if(view instanceof Button) { ((Button)view).setAllCaps(false);((Button)view).setTextSize(18);view.setMinimumHeight(dp(56)); }
        if(view instanceof EditText || view instanceof Spinner) view.setMinimumHeight(dp(56));
        if(view instanceof android.view.ViewGroup) for(int i=0;i<((android.view.ViewGroup)view).getChildCount();i++) comfortableControls(((android.view.ViewGroup)view).getChildAt(i));
    }
    private void selectPage(int page) {
        selectedPage=Math.max(0,Math.min(2,page));
        for(int i=0;i<3;i++) { pages[i].setVisibility(i==selectedPage?android.view.View.VISIBLE:android.view.View.GONE);tabs[i].setEnabled(i!=selectedPage); }
        if(selectedPage!=1) {
            android.view.View focus=getCurrentFocus();
            if(focus!=null) { ((android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).hideSoftInputFromWindow(focus.getWindowToken(),0);focus.clearFocus(); }
        }
    }
    @Override public void onBackPressed() { if(selectedPage!=0)selectPage(0);else super.onBackPressed(); }
    @Override protected void onSaveInstanceState(Bundle state) { state.putInt("locator_page",selectedPage);super.onSaveInstanceState(state); }
    static String gpsHeadline(SharedPreferences p,long now) {
        if(!p.getBoolean("enabled",false))return "Запись остановлена";
        if(p.contains("gps_provider_enabled")&&!p.getBoolean("gps_provider_enabled",true))return "GPS выключен в Android";
        long callback=p.getLong("last_gps_callback_at",0);
        if(callback==0)return "Ожидание координат GPS";
        if(now-callback>120000)return "Давно нет координат GPS";
        String state=p.getString("gps_state","");
        if("GPS_ACTIVE".equals(state))return "GPS · движение";
        if("STATIONARY".equals(state))return "GPS · остановка";
        if("GPS_RECOVERING".equals(state))return "Проверка GPS после потери сигнала";
        return "Ожидание пригодной GPS-точки";
    }
    static String age(long timestamp,long now) {
        if(timestamp<=0)return "ещё не было";
        long seconds=Math.max(0,(now-timestamp)/1000);
        if(seconds<60)return seconds+" с назад";
        if(seconds<3600)return seconds/60+" мин назад";
        return seconds/3600+" ч назад";
    }
    private void renderDashboard(SharedPreferences p) {
        long now=System.currentTimeMillis();boolean enabled=p.getBoolean("enabled",false);
        recordingSummary.setText(enabled?"Запись включена":"Запись остановлена");
        recordingSummary.setTextColor(enabled?0xff176642:0xff536170);
        gpsSummary.setText(gpsHeadline(p,now)+"\n\n"+gnssSummary(p)+"\nПоследняя сохранённая точка: "+age(p.getLong("last_fix",0),now)+"\n"+p.getString("quality","Точность ещё неизвестна"));
        boolean disk="yandex_disk".equals(p.getString("transport","https"));long queued=p.getLong("queued",0);
        deliverySummary.setText((disk?"Яндекс.Диск":"Home Assistant · HTTPS")+"\n\nВ очереди: "+queued+" точек\nПоследняя передача: "+age(p.getLong("last_sync",0),now)+"\n"+(disk?"Доставка из Диска в HA проверяется в HA.":"Точки удаляются после подтверждения HA.")
                +"\n"+p.getString("status","Передач ещё не было"));
        String message=p.getString("storage_error","");
        if(message.isEmpty())message=p.getString("secret_error","");
        if(message.isEmpty()&&getFilesDir().getUsableSpace()<100*1024*1024)message="Мало свободного места: менее 100 МБ";
        if(message.isEmpty()&&checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)!=PackageManager.PERMISSION_GRANTED)message="Нет разрешения на местоположение. При запуске записи появится запрос.";
        if(message.isEmpty()&&settingsBusy)message="Сохранение настроек…";
        if(message.isEmpty()&&!secretsReady)message="Чтение настроек подключения…";
        attention.setText(message);attention.setVisibility(message.isEmpty()?android.view.View.GONE:android.view.View.VISIBLE);
        startButton.setEnabled(secretsReady&&!settingsBusy);startButton.setText(enabled?"Сохранить настройки":"Сохранить и начать запись");
        stopButton.setEnabled(enabled||settingsBusy);
    }
    private void showPairingDialog(String id,String token,android.graphics.Bitmap bitmap) {
        try {
            LinearLayout body = new LinearLayout(this); body.setOrientation(LinearLayout.VERTICAL); body.setPadding(24, 12, 24, 12);
            ImageView image = new ImageView(this); image.setImageBitmap(bitmap); image.setAdjustViewBounds(true);
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
    private void checkUpdates() {
        if (updateBusy || isFinishing() || isDestroyed()) return;
        updateBusy = true;
        Toast.makeText(this, "Проверка обновлений…", Toast.LENGTH_SHORT).show();
        updateThread = new Thread(() -> {
            try {
                String installed = UpdateChecker.installedVersion(this);
                UpdateChecker.Release release = UpdateChecker.findLatest(UpdateChecker.get(UpdateChecker.RELEASES_URL), installed.contains("-"));
                if (release == null || UpdateChecker.compareVersions(release.version, installed) <= 0) {
                    updateUi(() -> { updateBusy=false; Toast.makeText(this, "Установлена последняя версия", Toast.LENGTH_LONG).show(); }); return;
                }
                updateUi(() -> confirmUpdate(release));
            } catch (Exception error) {
                updateUi(() -> { updateBusy=false; Toast.makeText(this, "Не удалось проверить обновления: " + error.getMessage(), Toast.LENGTH_LONG).show(); });
            }
        }, "update-check");
        updateThread.start();
    }
    private void updateUi(Runnable action) {
        runOnUiThread(() -> { if (!isFinishing() && !isDestroyed()) action.run(); });
    }
    private void confirmUpdate(UpdateChecker.Release release) {
        if (isFinishing() || isDestroyed()) return;
        updateBusy=false;
        if (updateDialog != null) updateDialog.dismiss();
        updateDialog = new android.app.AlertDialog.Builder(this).setTitle("Доступно обновление " + release.version)
            .setMessage((release.size > 0 ? "Размер: " + (release.size / 1024) + " КБ\n\n" : "") + release.notes)
            .setNegativeButton("Позже", null).setPositiveButton("Скачать", (dialog, which) -> downloadUpdate(release)).show();
    }
    private void downloadUpdate(UpdateChecker.Release release) {
        if (updateBusy || isFinishing() || isDestroyed()) return;
        updateBusy=true;
        ProgressDialog progress = new ProgressDialog(this); progress.setMessage("Скачивание APK…"); progress.setProgressStyle(ProgressDialog.STYLE_HORIZONTAL); progress.setMax(100); progress.setCancelable(false); progress.show();
        updateDialog=progress;
        updateThread = new Thread(() -> {
            try {
                File apk = UpdateChecker.download(getApplicationContext(), release, value -> updateUi(() -> progress.setProgress(value)));
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) { apk.delete(); return; }
                    updateBusy=false; progress.dismiss(); installUpdate(apk);
                });
            } catch (Exception error) {
                updateUi(() -> { updateBusy=false; progress.dismiss(); Toast.makeText(this, "Обновление отклонено: " + error.getMessage(), Toast.LENGTH_LONG).show(); });
            }
        }, "update-download");
        updateThread.start();
    }
    private void installUpdate(File apk) {
        if (Build.VERSION.SDK_INT >= 26 && !getPackageManager().canRequestPackageInstalls()) {
            pendingUpdate = apk;
            Config.prefs(this).edit().putString("pending_update", apk.getName()).apply();
            try {
                startActivity(new Intent(android.provider.Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName())));
                Toast.makeText(this, "Разрешите установку из Jolion Locator и вернитесь в приложение", Toast.LENGTH_LONG).show();
            } catch (RuntimeException unavailable) {
                Toast.makeText(this, "ГУ не открывает разрешение установки APK. Разрешите его в настройках приложений.", Toast.LENGTH_LONG).show();
            }
            return;
        }
        pendingUpdate = null;
        Config.prefs(this).edit().remove("pending_update").apply();
        Uri apkUri = new Uri.Builder().scheme("content").authority(getPackageName() + ".update-provider").appendPath(apk.getName()).build();
        Intent install = new Intent(Intent.ACTION_VIEW).setDataAndType(apkUri, "application/vnd.android.package-archive");
        install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try { startActivity(install); }
        catch (RuntimeException unavailable) { Toast.makeText(this, "Системный установщик APK недоступен", Toast.LENGTH_LONG).show(); }
    }
    private void start() {
        if (!secretsReady || settingsBusy) { Toast.makeText(this,"Дождитесь чтения или сохранения настроек",Toast.LENGTH_SHORT).show(); return; }
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
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION}, 1); return;
        }
        settingsBusy=true;
        final int generation=++startGeneration;
        settingsWorker.execute(() -> {
        try {
        SharedPreferences p = Config.prefs(this);
        synchronized(Config.class) {
            String oldBase=Config.destination(this),newBase=disk?"yadisk:"+folder:base;
            boolean changedMode=oldBase.startsWith("yadisk:")!=disk;
            if(queuedCount()>0 && (!id.equals(p.getString("vehicle","jolion")) || (!changedMode && !newBase.equals(oldBase)))) {
                throw new IllegalStateException("С очередью нельзя менять ID или адрес внутри одного способа передачи");
            }
            if(!p.edit().putString("url",base).putString("vehicle",id).putString("transport",disk?"yandex_disk":"https").putString("disk_folder",folder).putString("interval",Integer.toString(seconds)).putString("route_from",changedMode?oldBase:"").commit() || !Config.putSecrets(this, token, oauth)) {
                throw new IllegalStateException("Не удалось сохранить настройки");
            }
            if(changedMode)try(QueueDb db=new QueueDb(this)){db.reroute(oldBase,newBase,id,token,oauth);}
        }
        updateUi(() -> {
            settingsBusy=false;
            if(generation!=startGeneration)return;
            p.edit().putBoolean("enabled", true).apply(); Config.mirrorBootState(this, true, p.getBoolean("autostart", true));
            startForegroundService(new Intent(this, TrackingService.class));
            renderDashboard(p);
        });
        } catch(Exception error) { updateUi(() -> { settingsBusy=false; Toast.makeText(this,"Не удалось сохранить настройки. Проверьте очередь, ключ и свободное место.",Toast.LENGTH_LONG).show(); }); }
        });
    }
    public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request == 1 && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) start();
    }
    public void onResume() {
        super.onResume(); timer.post(refresh);
        if (pendingUpdate == null) {
            String name=Config.prefs(this).getString("pending_update","");
            if(!name.isEmpty()) { File candidate=new File(new File(getCacheDir(),"updates"),name); if(candidate.isFile())pendingUpdate=candidate; else Config.prefs(this).edit().remove("pending_update").apply(); }
        }
        if (pendingUpdate != null && (Build.VERSION.SDK_INT < 26 || getPackageManager().canRequestPackageInstalls())) installUpdate(pendingUpdate);
    }
    public void onPause() { timer.removeCallbacks(refresh); super.onPause(); }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(request!=2 || result!=RESULT_OK || data==null || data.getData()==null)return;
        Uri destination=data.getData();
        settingsWorker.execute(() -> {
            try(java.io.OutputStream out=getContentResolver().openOutputStream(destination,"wt")) {
                if(out==null)throw new java.io.IOException("No output stream");
                out.write(Diagnostics.snapshot(getApplicationContext()).toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));
                updateUi(() -> Toast.makeText(this,"Диагностика сохранена",Toast.LENGTH_LONG).show());
            } catch(Exception error) { updateUi(() -> Toast.makeText(this,"Не удалось сохранить диагностику",Toast.LENGTH_LONG).show()); }
        });
    }
    public void onDestroy() {
        settingsWorker.shutdown();
        if (updateThread != null) updateThread.interrupt();
        if (updateDialog != null) updateDialog.dismiss();
        timer.removeCallbacks(refresh);
        super.onDestroy();
    }
}
