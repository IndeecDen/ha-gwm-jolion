# Roadmap — GWM Jolion для Home Assistant

План развития после cleanup-релиза `0.1.0-alpha.20`.

Статусы:

- ✅ реализовано / подтверждено;
- 🟢 реализовано, но требует дополнительной полевой проверки;
- 🧪 эксперимент / protocol research;
- ⏳ запланировано.

## 0.1.0-alpha.20 — clean entity surface

- ✅ Entity Registry очищен от protocol/raw мусора и дублирующих сущностей;
- ✅ добавлена Config Entry migration v1 → v2, которая удаляет obsolete entities на существующей установке;
- ✅ raw telemetry остаётся внутри parser/coordinator, diagnostics и Protocol Capture;
- ✅ individual window binary sensors стали обычными user-facing entities и содержат `raw_state` attribute;
- ✅ seat heat levels `2220001/2220002` остаются отдельными полезными status sensors;
- ✅ native `lock` заменяет дублирующие lock/unlock buttons и `vehicle_unlocked` binary sensor;
- ✅ `device_tracker` остаётся единственным GPS entity;
- ✅ T-Box attributes консолидируют GSM raw, model code, oil raw, GPS availability и feature flags;
- ✅ Refresh button attributes консолидируют last-command и Protocol Capture status;
- ✅ public command buttons ограничены рабочими сценариями;
- ✅ `close_windows` удалён из обычного UI после неуспешного физического теста движения стекол;
- ✅ experimental open-windows/panorama/sunshade/front-defrost/Cabin Clean убраны из Entity Registry и bundled-card controls;
- ✅ Options Flow оставляет только оборудование, которое сейчас влияет на полезные public entities/commands;
- ✅ основная карточка исправляет историческую перестановку физических окон;
- ✅ remote-card продолжает анимировать четыре окна без отдельных raw sensor entities;
- ✅ headlights по-прежнему не привязаны к engine и не включаются по неподтверждённому light candidate.

## Подтверждённая телеметрия

### Основное состояние

- ✅ `2016001`: engine `0=OFF`, `2=RUNNING`;
- ✅ ACC-тест: `2016001` остаётся `0`, отдельный ACC signal не найден;
- ✅ `2208001`: lock `0=locked`, `1=unlocked`;
- ✅ `2206001`: trunk `0=closed`, `1=open`;
- ✅ 4 door states;
- ✅ `2202001`: climate `0=OFF`, `1=ON`;
- ✅ fuel L / calculated % / range / mileage;
- ✅ T-Box online;
- ✅ GPS location;
- ✅ pressure + temperature all four tires.

### Окна

- ✅ `2210001 = FL / водительское`;
- ✅ `2210002 = FR`;
- ✅ `2210003 = RL`;
- ✅ `2210004 = RR`;
- ✅ generic decoder: `1=closed`, `2/3=not closed`;
- ✅ для FL отдельно подтверждено `3=partial`, `2=full open`;
- ⏳ отдельно поймать raw `3` для FR/RL/RR медленным marker-тестом, если нужна точная анимация степени открытия каждого стекла.

### Сиденья

- ✅ `2220001` driver seat heat;
- ✅ `2220002` passenger seat heat;
- ✅ шкала обоих: `0=off`, `1=low`, `2=medium`, `3=high`;
- ⏳ найти подтверждённый T5 payload управления подогревом сидений; до этого status-only.

## Удалённое управление

### Рабочий основной набор

- ✅ start engine;
- ✅ stop engine;
- ✅ lock / unlock через native `lock`;
- ✅ climate ON/OFF + target temperature;
- ✅ climate runtime;
- ✅ trunk open / close;
- ✅ flash lights;
- ✅ horn;
- ✅ flash + horn;
- 🟢 rear defrost ON/OFF — команда есть, отдельный live status не подтверждён;
- 🟢 steering wheel heat ON/OFF — команда есть, отдельный live status не подтверждён.

### Требует протокольной проверки

- ⏳ найти фактически работающий T5 payload закрытия/открытия окон; текущий `0x08` cloud response не доказал движение стекол;
- ⏳ подтвердить/найти управление передними подогревами сидений;
- 🧪 panorama / sunshade payload сохранён только как исследовательский код;
- 🧪 front defrost / Cabin Clean сохранены только как исследовательские services/payload до повторных тестов.

## Свет

- 🟢 `2204008` — кандидат дальнего света: после `LIGHT_HIGH` был пойман `0→1`, затем `1→0`;
- ⏳ провести отдельный медленный тест `LIGHT_OFF → AUTO → PARKING → LOW → HIGH`, с marker + manual refresh и ожиданием нового `acquisitionTime` на каждом этапе;
- ⏳ после подтверждения подключить headlights animation к реальному light state;
- ✅ engine state никогда не используется как замена статуса фар.

## Следующие полезные данные

- ⏳ telemetry freshness: отдельный возраст cloud snapshot на основе `acquisitionTime`, чтобы различать свежий опрос и кэш GWM;
- ⏳ hood open/closed;
- ⏳ 12V battery voltage / SOC, если GWM Cloud отдаёт;
- ⏳ наружная температура;
- ⏳ температура салона;
- ⏳ coolant temperature;
- ⏳ дополнительные предупреждения автомобиля;
- ⏳ точная шкала GSM;
- ⏳ физическая интерпретация `oilQty`;
- ⏳ несколько автомобилей в одном аккаунте.

## Protocol Capture / diagnostics

- ✅ JSONL schema 2;
- ✅ timestamped файлы в `/config/gwm_jolion_protocol_capture/`;
- ✅ старые JSONL не удаляются при reload/update;
- ✅ baseline + change events + marker records;
- ✅ источники `poll`, `manual_button`, `remote_command`, `remote_start_guard`;
- ✅ privacy filter исключает VIN/credentials/account/exact location/device identifiers;
- ✅ raw protocol данные продолжают собираться после alpha.20, даже если для них больше нет отдельных Home Assistant entities;
- ⏳ при следующем protocol-heavy цикле добавить более удобный экспорт списка capture-файлов без превращения его в набор пользовательских entities.

## Карточки

- ✅ `custom:gwm-jolion-card` — рабочая control/status карточка;
- ✅ `custom:gwm-jolion-remote-card` — top-view animated card;
- ✅ капот слева, багажник справа;
- ✅ FR/RR сверху, FL/RL снизу;
- ✅ независимые 4 doors / 4 windows / trunk / engine / climate visuals;
- ✅ 8 основных status tiles с текстовыми значениями;
- ✅ alpha.20 cards используют curated entity surface и attributes вместо raw helper entities;
- ⏳ дальнейшая визуальная доработка top-view автомобиля без изменения уже подтверждённой геометрии;
- ⏳ hood/headlight animation только после подтверждённой telemetry.
