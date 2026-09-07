# Changelog

## 0.1.0-alpha.20

Крупный cleanup-релиз пользовательского слоя Home Assistant. После полевых тестов интеграция перестаёт превращать каждый исследовательский raw-код в отдельную сущность и оставляет в Entity Registry только полезные рабочие кейсы.

### Entity Registry cleanup

- Config Entry schema повышена до v2 и добавлена одноразовая миграция существующих установок;
- миграция удаляет старые TPMS raw/status, window raw/window-learn, light raw, indicator raw, служебные vehicle/model/service entities и diagnostic helper entities;
- удаляются дублирующие кнопки `lock_vehicle` / `unlock_vehicle`: каноническим управлением становится `lock` entity;
- удаляется дублирующий `vehicle_unlocked` binary sensor;
- удаляется `gps_authorized`: для карты остаётся стандартный `device_tracker`, а факт наличия GPS доступен в attributes T-Box;
- индивидуальные окна пересоздаются как обычные user-facing binary sensors, а их `raw_state` переносится в attributes;
- live-уровни подогрева водительского и пассажирского сидений остаются полезными sensor entities с чистыми friendly names;
- raw protocol data не удаляются из parser/coordinator и продолжают попадать в Protocol Capture/diagnostics.

### Оптимизированный рабочий набор

Обычные sensors: запас хода, топливо L/%, пробег, давление/температура четырёх шин, уровни двух передних подогревов сидений и timestamp последнего обновления.

Обычные binary sensors: T-Box online, двигатель, общий статус дверей + 4 двери, общий статус окон + 4 окна, багажник и климат.

Native entities остаются основным способом управления:

- `lock` — открыть/закрыть автомобиль;
- `climate` — ON/OFF и температура;
- `number` — время работы климата;
- `device_tracker` — местоположение.

При Remote Control + PIN создаются только кнопки с полезным рабочим сценарием: engine start/stop, flash/horn, trunk open/close, rear defrost ON/OFF и steering heat ON/OFF. `Обновить данные` создаётся всегда.

### Убрано из обычного UI

- `close_windows` больше не создаёт кнопку: cloud response был успешным, но физического закрытия стекол в тесте не произошло;
- `open_windows`, panorama/sunshade, front-defrost и Cabin Clean не создают entity buttons;
- экспериментальные/неподтверждённые comfort status binary sensors удалены;
- экспериментальные опции оборудования убраны из обычного Options Flow; остаются только обогрев руля, заднего стекла и status двух передних подогревов сидений.

Низкоуровневые `gwm_jolion.*` services сохранены для обратной совместимости и протокольных тестов, но bundled cards больше не предлагают неподтверждённые действия.

### Bundled cards

- добавлен alpha.20 compatibility layer, который позволяет карточкам работать без удалённых raw/helper entities;
- raw уровни четырёх окон читаются из `raw_state` соответствующих window binary sensors;
- lock-status читается из native `lock` entity;
- GSM/model/oil/GPS/feature flags читаются из attributes `T-Box онлайн`;
- last-command и Protocol Capture metadata читаются из attributes кнопки `Обновить данные`;
- в основной карточке исправлена историческая pre-field-test перестановка FL/FR и RL/RR окон;
- физически неподтверждённое управление окнами скрыто, при этом статус и анимация четырёх окон сохранены;
- remote-card/editor фильтруют experimental controls и неподтверждённый `Defrost` status;
- фронтенд cache key обновлён до `0.1.0-alpha.20`.

### Protocol / telemetry

Новые GWM payload в этом релизе не угадываются. Сохраняются результаты recovered marker-теста:

- `2210001=FL`, `2210002=FR`, `2210003=RL`, `2210004=RR`;
- `2210001`: `1=closed`, `3=partial`, `2=full open`; generic window decoder: `1=closed`, `2/3=not closed`;
- `2016001`: `0=OFF`, `2=RUNNING`; отдельный ACC signal не найден;
- `2202001`: `0=climate OFF`, `1=climate ON`;
- `2204008` остаётся только кандидатом дальнего света;
- отдельные live status для steering/rear/front-defrost не считаются подтверждёнными.

### Migration note

`alpha.20` намеренно является breaking cleanup для alpha-ветки. Автоматизации, напрямую использовавшие удалённые raw/helper entity IDs, нужно перевести на нормальные user-facing entities либо использовать Protocol Capture/diagnostics. Старые JSONL capture-файлы в `/config/gwm_jolion_protocol_capture/` не удаляются.

## 0.1.0-alpha.19.7

Полевой protocol-релиз по восстановленной 68-record JSONL-сессии `alpha.19.5`:

- подтверждены физические позиции всех четырёх окон;
- climate code `2202001` переведён в confirmed;
- ACC-тест подтвердил отсутствие отдельного найденного ACC-кода и `2016001=2` только для RUNNING;
- `2204008` зафиксирован как кандидат дальнего света, без активации headlights animation;
- raw sensors четырёх окон временно были вынесены в Entity Registry для проверки — в `alpha.20` они заменены attributes чистых window entities.

## 0.1.0-alpha.19.6

UX-релиз remote-card:

- широкий SUV top-view `1100×520`;
- FR/RR сверху, FL/RL снизу;
- независимые двери, окна, багажник, engine/climate animation;
- статусные плитки переведены на сетку `4×2` с видимыми значениями топлива/пробега и остальных состояний.

## 0.1.0-alpha.19.5

Исправлена ориентация remote-card после проверки на реальном Lovelace-экране: верх сцены = правая сторона автомобиля, низ = левая, капот слева, багажник справа.

Полная история предыдущих alpha-релизов доступна в GitHub Releases и тегах репозитория:

https://github.com/IndeecDen/ha-gwm-jolion/releases
