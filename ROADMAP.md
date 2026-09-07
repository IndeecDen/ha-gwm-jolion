# Roadmap — GWM Jolion для Home Assistant

План развития `ha-gwm-jolion`.

Статусы:

- ✅ реализовано / подтверждено;
- 🟢 реализовано в Alpha и требует дальнейшей проверки;
- 🧪 экспериментальная функция;
- ⏳ запланировано.

## 0.1.0-alpha.19.7 — recovered field-test / four-window mapping

- ✅ восстановлена полная 68-record JSONL-сессия `alpha.19.5`;
- ✅ `2210001=FL`, `2210002=FR`, `2210003=RL`, `2210004=RR` физически закреплены marker-тестом;
- ✅ raw sensors всех четырёх окон добавлены как diagnostics;
- ✅ remote-card использует отдельные raw/binary состояния всех четырёх окон;
- ✅ `2202001` подтверждён как climate `0=OFF / 1=ON`;
- ✅ ACC-тест выполнен: `2016001` остаётся `0`, RUNNING=`2`; отдельный ACC code не найден;
- 🟢 `2204008` — кандидат дальнего света после `LIGHT_HIGH: 0→1`; нужен отдельный медленный повторный тест перед включением headlights animation;
- 🟡 отдельные live-status steering/rear/front-defrost в этом STATUS-наборе не подтверждены;
- ⏳ повторно проверить T5 `0x08` на физическое движение окон;
- ⏳ найти достоверный hood telemetry signal.


## 0.1.0-alpha.19.6 — wide SUV remote-card / visible status values

Этот раздел имеет приоритет над `alpha.19.5` для текущего визуального поведения карточки-пульта.

- ✅ центральная top-view пиктограмма `custom:gwm-jolion-remote-card` перерисована с более широкими и высокими SUV-пропорциями; viewBox `1100×520`;
- ✅ капот слева, багажник справа;
- ✅ верх сцены = правая сторона автомобиля (FR/RR), низ = левая (FL/RL);
- ✅ ось каждой SVG-двери остаётся на её левой кромке; FR/RR открываются вверх, FL/RL вниз;
- ✅ независимые анимации четырёх дверей, багажника, двигателя и климата сохранены;
- ✅ добавлены более выраженные детали кузова: решётка, капот, крыша, панорамная секция, рейлинги и зеркала;
- ✅ стандартные статусные плитки engine / climate / fuel / mileage / doors / windows / trunk / lock теперь всегда используют сетку `4×2` на обычной карточке;
- ✅ `Топливо` и `Пробег` показывают реальное состояние Home Assistant вместе с unit;
- ✅ значения статусов больше не скрываются однострочным ellipsis и могут переноситься;
- ✅ недоступные значения показываются как `Нет данных`;
- ✅ на очень маленьком контейнере статусы переходят в 2 колонки;
- ✅ `Defrost` добавлен как опциональная статусная плитка в visual editor;
- ✅ regression-тесты проверяют широкую геометрию, FR/RR сверху, FL/RL снизу, петли, driver-window placement и наличие текстовых значений топлива/пробега;
- 🟢 подтверждённое водительское окно `2210001` остаётся на FL со шкалой `1=closed`, `3=partial`, `2=full open`;
- ✅ позиции `2210002..2210004` физически закреплены recovered marker-тестом `alpha.19.5`;
- ⏳ фары: подключить анимацию только после физического подтверждения `2204007/2204008`;
- ⏳ капот: подключить анимацию только после обнаружения достоверного hood telemetry signal;
- ⏳ повторно проверить T5 `0x08` для физического закрытия/открытия окон;
- ✅ последовательность `VEHICLE_SLEEP → DOOR_WAKE → IGNITION_ACC → ENGINE_RUNNING → ENGINE_STOPPED → VEHICLE_LOCKED` проверена: отдельный ACC-код не найден, `2016001=1` не наблюдалось.

## 0.1.0-alpha.19.5 — corrected large remote-card layout

Исторический UX-релиз, в котором была исправлена ориентация сцены после проверки на реальном экране.

- ✅ капот слева, багажник справа;
- ✅ **верх сцены = правая сторона автомобиля**, низ = левая;
- ✅ FR = передняя правая сверху спереди, RR = задняя правая сверху сзади;
- ✅ FL = передняя левая снизу спереди, RL = задняя левая снизу сзади;
- ✅ у всех четырёх дверей `transform-origin` находится на левой кромке своей SVG-створки;
- ✅ FR/RR открываются наружу вверх, FL/RL — наружу вниз;
- ✅ отдельные door animations используют четыре существующих door binary sensors;
- ✅ багажник, двигатель и климат имеют отдельные animated layers;
- ✅ T-Box Online/Offline и GSM находятся справа сверху;
- ✅ статусы отделены от controls;
- 🟢 водительское окно использует `2210001`: `1=closed`, `3=partial`, `2=full open`.

## 0.1.0-alpha.19.4 — animated horizontal remote card

Исторический раздел. Его прежняя ориентация верх/низ была исправлена в `alpha.19.5`.

- ✅ первый крупный horizontal top-view redesign: капот слева, багажник справа;
- ✅ отдельные door animations, багажник, engine overlay, climate airflow, Online/GSM и status tiles;
- ✅ добавлен regression-test геометрии;
- ✅ locked/unlocked визуально различаются без выдачи центрального замка за отдельный alarm-status.

## 0.1.0-alpha.19.3 — полевые уточнения

- ✅ `2220001` / `2220002`: для обоих передних сидений принята шкала `0=off`, `1=low`, `2=medium`, `3=high`;
- ✅ `vehicleBasicsInfo.leftFrontSeat/rightFrontSeat` признаны preset/config значениями и больше не используются как live fallback;
- ✅ окна переведены на multistate decoder: `1=closed`, `2/3=not closed`, остальные значения unknown;
- ✅ `2210001` физически подтверждён как переднее левое / водительское окно: `1=closed`, `3=partial`, `2=full open`;
- ✅ позиции `2210002..2210004` физически закреплены recovered marker-тестом `alpha.19.5`;
- ✅ `custom:gwm-jolion-remote-card` переведена на SVG вид сверху и получила locked/unlocked glow, Online/GSM и анимации.

## 0. Базовая интеграция

- ✅ domain `gwm_jolion`;
- ✅ Config Flow;
- ✅ авторизация в российском GWM Cloud;
- ✅ подпись API-запросов;
- ✅ `getLastStatus` / `findStatus`;
- ✅ coordinator polling;
- ✅ T5 send + polling результата;
- ✅ PIN security check;
- ✅ настройки polling / remote controls / cooldown / PIN;
- ✅ автоматическая повторная авторизация после auth-ошибок GWM;
- ✅ Home Assistant reauth при недействительных учётных данных;
- ✅ сохранение существующего GWM device ID при reauth;
- ✅ ручная настройка опционального оборудования по комплектации;
- ✅ ручные capability-настройки имеют приоритет над универсальными полями `vehicleBasicsInfo`;
- ⏳ несколько автомобилей в одном аккаунте;
- ⏳ безопасное автоматическое определение опционального оборудования.

## 1. Телеметрия автомобиля

### Основная

- ✅ двигатель;
- ✅ центральный замок;
- ✅ 4 двери;
- ✅ багажник;
- ✅ 4 окна;
- ✅ пробег;
- ✅ топливо в литрах;
- ✅ расчёт топлива в процентах;
- ✅ запас хода;
- ✅ GPS;
- ✅ T-Box online;
- ✅ давление 4 шин;
- ✅ температура 4 шин;
- 🟢 уровень масла GWM `oilQty`.

### Расширенная диагностика

- 🟢 TPMS raw/status;
- 🟢 window learn raw;
- 🟢 seat heat raw;
- 🟢 light raw;
- 🟢 GPS authorization;
- 🟢 T-Box signal;
- 🧪 front defrost status;
- 🧪 rear defrost status;
- 🧪 steering wheel heat status;
- 🧪 front windscreen heat status;
- 🧪 air circulation status;
- ✅ история неизвестных GWM-кодов в diagnostics;
- ✅ bounded `signal_change_history` для важных raw-сигналов;
- ✅ опциональный JSONL Protocol Capture: полный raw snapshot + `previous → value` после каждого успешного опроса;
- ✅ различение источника capture-записи: `poll`, `manual_button`, `remote_command`, `remote_start_guard`;
- ✅ пользовательские маркеры этапов теста без изменения telemetry baseline;
- ✅ диагностический сенсор состояния Protocol Capture;
- ✅ экспорт текущей capture-сессии: первый baseline + до 5000 самых свежих корректных записей; полный JSONL не обрезается;
- ✅ Protocol Capture schema 2 сохраняет `items[].unit`, item keys и безопасные top-level значения `getLastStatus`;
- ✅ `status_structure`, `vehicle_basics_structure` и `tbox_structure` показывают неизвестные поля/типы без сохранения потенциально чувствительных значений;
- ✅ `status_meta_changes` и `tbox_meta_changes` позволяют сопоставлять изменения верхнеуровневых GWM/T-Box полей с физическими тестами;
- 🟢 `percentageOfOil` и `charge` собираются как raw top-level диагностические кандидаты без предположения об их физическом смысле.

### Нужно найти / подтвердить

- ⏳ напряжение 12V АКБ;
- ⏳ SOC 12V АКБ, если GWM Cloud его отдаёт;
- ⏳ наружная температура;
- ⏳ температура салона;
- ⏳ температура охлаждающей жидкости;
- ⏳ дополнительные предупреждения автомобиля;
- ⏳ точная расшифровка шкалы GSM;
- ⏳ точная физическая интерпретация делений `oilQty`;
- ⏳ физическая интерпретация `percentageOfOil`, если Jolion возвращает ненулевое значение;
- ⏳ физическая интерпретация top-level `charge`, если поле используется на Jolion.

## 2. Удалённое управление

### Подтверждено

- ✅ запуск двигателя;
- ✅ остановка двигателя;
- ✅ lock / unlock;
- ✅ открыть / закрыть багажник;
- ✅ закрыть окна;
- ✅ flash lights;
- ✅ horn;
- ✅ flash + horn.

> Примечание `alpha.19.3+`: физическое выполнение `close_windows` требует повторной проверки; успешный cloud response сам по себе не считается доказательством движения стекла.

### Реализовано в Alpha

- 🧪 открытие всех окон;
- 🧪 открыть / закрыть панораму;
- 🧪 открыть / закрыть шторку панорамы;
- 🟢 задний defrost ON/OFF;
- 🟢 обогрев руля ON/OFF;
- 🧪 передний defrost ON/OFF;
- 🧪 Cabin Clean / проветривание.

### Надёжность команд

- ✅ команды сериализованы: одновременно выполняется только одна T5-команда;
- ✅ повторная команда отклоняется, пока предыдущая выполняется;
- ✅ cooldown между командами;
- ✅ cooldown использует монотонный таймер;
- ✅ сенсор последней команды: `pending / success / error`;
- ✅ сохранение кода и сообщения результата GWM;
- ✅ отдельная обработка timeout;
- ✅ конечные T5-ошибки завершают polling сразу и освобождают очередь команд;
- ✅ `in_progress=false` публикуется после фактического освобождения command lock;
- ✅ перед remote start выполняется свежий cloud refresh;
- ✅ перед remote start проверяются двигатель, замок, двери и багажник;
- ✅ обе карточки блокируют другие remote-кнопки во время выполнения команды;
- ✅ команды опционального оборудования блокируются, если функция отключена пользователем;
- ⏳ расширенный справочник пользовательских сообщений для известных кодов ошибок GWM.

### Дальше

- ⏳ выбор отдельных окон;
- ⏳ tilt / промежуточные положения панорамы;
- ⏳ реальные telemetry-коды положения панорамы и шторки на автомобилях с панорамой.

## 3. Климат

- 🟢 Home Assistant `climate` entity;
- 🟢 target temperature 16–32 °C;
- 🟢 runtime 5–30 минут;
- 🟢 climate ON;
- 🧪 climate OFF;
- 🧪 сохранение настроек через `modifyVehicleRemoteCtlInfo`;
- 🟢 `vehicleBasicsInfo`;
- ✅ разбор российского ответа `vehicleBasicsInfo` с вложенностью `data → config`;
- ✅ безопасный whitelist snapshot полезных climate/comfort значений без VIN, user ID и других идентификаторов;
- ✅ `vehicleBasicsInfo` не используется как доказательство наличия оборудования;
- ⏳ реальное оставшееся время работы;
- ⏳ синхронизация настроек HA ↔ GWM App;
- ⏳ blowing mode / power gear, если поддерживаются Jolion.

## 4. Comfort-функции

### Стёкла / defrost

- 🧪 передний defrost;
- 🟢 задний defrost;
- ⏳ электрический обогрев лобового — управление после подтверждения payload;
- ⏳ `switch` entities для функций с достоверным readback.

### Сиденья

- ✅ чтение live raw водительского подогрева `2220001`;
- ✅ чтение live raw пассажирского подогрева `2220002`;
- ✅ уровни `0=off / 1=low / 2=medium / 3=high` приняты для обоих передних сидений;
- ✅ saved presets `leftFrontSeat/rightFrontSeat` не используются как live fallback;
- ⏳ подтверждение payload управления подогревом;
- ⏳ вентиляция сидений для поддерживаемых комплектаций;
- ⏳ `select` entities для уровней после подтверждения управляющего протокола.

### Руль / салон

- 🟢 команда обогрева руля;
- 🧪 реальный readback обогрева руля;
- 🧪 Cabin Clean;
- ⏳ air purifier, если поддерживается автомобилем.

## 5. TPMS

- ✅ давление 4 шин;
- ✅ температура 4 шин;
- 🟢 raw status-коды;
- ⏳ расшифровка enum status-кодов;
- ⏳ отдельные предупреждения Home Assistant;
- ⏳ визуальное выделение проблемного колеса в карточке.

## 6. Карточки GWM Jolion

### Основная `custom:gwm-jolion-card`

- ✅ автоматическая регистрация frontend;
- ✅ auto-discovery сущностей через Entity Registry;
- ✅ заголовок модель + имя автомобиля + `2WD / 4WD`;
- ✅ топливо / запас хода / пробег;
- ✅ engine / lock / trunk / windows controls;
- ✅ конкретные открытые окна;
- ✅ таймер remote start;
- ✅ climate / temperature / runtime;
- ✅ comfort-блок;
- ✅ панорама / шторка для комплектаций, где они включены в настройках;
- ✅ скрытие отсутствующего опционального оборудования по capability-настройкам;
- ✅ 4 шины;
- ✅ T-Box / GPS / GSM;
- ✅ сегментный индикатор масла;
- ✅ время последнего обновления;
- ✅ отображение результата последней команды;
- ✅ блокировка remote-кнопок во время выполняющейся команды;
- ✅ адаптация сетки для мобильного экрана;
- ✅ visual editor с выбором кнопок, датчиков и дополнительных панелей;
- ✅ регистрация visual editor не зависит от порядка загрузки frontend-ресурсов.

### Карточка-пульт `custom:gwm-jolion-remote-card`

- ✅ отдельная вторая встроенная карточка;
- ✅ собственная SVG-иллюстрация автомобиля без сторонних assets;
- ✅ `alpha.19.6`: широкий horizontal top-view SUV, капот слева / багажник справа;
- ✅ `alpha.19.6`: верх = правая сторона (FR/RR), низ = левая (FL/RL);
- ✅ `alpha.19.6`: левая ось петель каждой SVG-створки закреплена regression-тестом;
- ✅ изменяемый цвет кузова;
- ✅ locked/unlocked glow;
- ✅ Online/Offline + 4-сегментный GSM справа сверху;
- ✅ status tiles engine/climate/fuel/mileage/doors/windows/trunk/lock с видимыми текстовыми значениями;
- ✅ status layout 4×2 по умолчанию и 2 колонки только на очень маленькой ширине;
- ✅ optional status `Defrost` в visual editor;
- ✅ индивидуальные door animations;
- ✅ trunk / engine / climate animations;
- 🟢 driver-window animation по `2210001` на FL;
- ⏳ анимация остальных трёх окон после физической привязки `2210002..2210004`;
- ⏳ анимация фар после light marker-теста;
- ⏳ анимация капота после подтверждения hood telemetry;
- ✅ отдельный ряд кнопок управления;
- ✅ настраиваемые информационные плитки;
- ✅ visual editor Home Assistant;
- ✅ capability-фильтрация отсутствующего оборудования;
- ✅ защита от повторных remote-команд;
- ✅ неизвестные/недоступные состояния не отображаются как ложные `off / closed / offline`.

### План

- ⏳ выбор автомобиля при нескольких машинах;
- ⏳ более подробные состояния loading / unavailable / API error;
- ⏳ визуальные предупреждения TPMS;
- ⏳ отображение реального состояния панорамы/шторки после физических тестов на совместимой машине;
- ⏳ дополнительные варианты изображения кузова после проверки карточки на разных экранах.

## 7. Home Assistant architecture

- ✅ `sensor`;
- ✅ `binary_sensor`;
- ✅ `button`;
- ✅ `device_tracker`;
- ✅ GPS `device_tracker` совместим со стандартной карточкой Home Assistant `map`;
- ✅ GPS-координаты трекера приводятся к числам, трекер использует автомобильную иконку;
- ✅ `lock`;
- ✅ `climate`;
- ✅ `number`;
- ✅ diagnostics export с редактированием чувствительных данных;
- ✅ RU / EN translations;
- ✅ диагностический сенсор ручных capability-настроек;
- ✅ диагностический сенсор состояния Protocol Capture;
- ✅ сервис `gwm_jolion.add_capture_marker` для маркировки шагов физических тестов;
- ✅ опциональные button/sensor/binary_sensor не загружаются для отключённого оборудования;
- ⏳ `switch` для функций с подтверждённым readback;
- ⏳ `select` для подтверждённых многоуровневых функций;
- ⏳ Repairs для длительных cloud/API проблем;
- ⏳ автоматическое создание сущностей по достоверно определённым capabilities конкретной машины;
- ⏳ multi-vehicle architecture.

## 8. Надёжность и безопасность

- ✅ serialized remote commands;
- ✅ command cooldown;
- ✅ T5 result polling;
- ✅ защита remote start по свежей телеметрии;
- ✅ frontend-защита от повторных remote-команд;
- ✅ backend-защита от вызова команд отключённого оборудования;
- ✅ reauth;
- ✅ диагностическое скрытие VIN, номера автомобиля, токенов, IMSI/ICCID, координат и других чувствительных полей;
- ✅ bounded history изменений тестовых raw-сигналов без координат и идентификаторов;
- ✅ JSONL capture не пишет автоматические VIN, координаты, аккаунт, credentials и device identifiers;
- ✅ неизвестные поля `getLastStatus` / `findStatus` / `vehicleBasicsInfo` можно обнаружить по безопасной structure-инвентаризации без сохранения их значений;
- ✅ capture-ошибки не прерывают основной polling автомобиля;
- ✅ unit tests для protocol / capabilities / vehicle data / command safety;
- ✅ unit tests ручных capability-настроек и сопоставления команд/сущностей;
- ✅ unit tests JSONL baseline/diff/marker/diagnostics export, включая сохранение первого baseline + последних записей;
- ✅ unit tests Protocol Capture schema 2 для units, safe top-level metadata и structure inventory;
- ✅ `alpha.19.3`: unit tests multistate windows и запрета seat-preset fallback;
- ✅ `alpha.19.6`: regression-test wide-SUV геометрии, ориентации, петель, driver-window и видимых status values;
- ⏳ дополнительные тесты auth refresh / API outage;
- ⏳ расширенные тесты timeout и неожиданных ответов GWM.

## 9. GitHub / HACS

- ✅ публичный GitHub repository;
- ✅ MIT License;
- ✅ README / ROADMAP / CHANGELOG / THIRD_PARTY_NOTICES;
- ✅ branding assets;
- ✅ HACS metadata;
- ✅ GitHub repository topics;
- ✅ HACS validation;
- ✅ Hassfest;
- ✅ Python / JSON / YAML / JavaScript checks;
- ✅ unit tests в GitHub Actions;
- ✅ автоматические versioned GitHub Releases;
- ✅ HACS показывает версии релизов вместо SHA;
- ⏳ стабильный `1.0.0`;
- ⏳ заявка в default repositories HACS после стабилизации.

## 10. Версии

### `0.1.0-alpha.19.6` — Wide SUV remote-card / visible status values

Remote-card переработана после реального скриншота `alpha.19.5`: top-view кузов стал шире и выше, status tiles получили постоянную сетку 4×2 и всегда отображают текстовые значения топлива, пробега и других состояний. Ориентация FR/RR сверху, FL/RL снизу сохранена. Новых GWM remote payload и telemetry mappings нет.

### `0.1.0-alpha.19.5` — Corrected large remote-card layout

Remote-card скорректирована после проверки на реальном узком Lovelace-экране: автомобиль увеличен, пустое пространство сокращено, подписи дверей сделаны читаемее. Правильная ориентация сцены закреплена тестами: капот слева, багажник справа, FR/RR сверху, FL/RL снизу.

### `0.1.0-alpha.19.4` — Animated horizontal remote card (historical)

Первый крупный horizontal top-view redesign. Ориентация верх/низ этого релиза была скорректирована в `alpha.19.5`; animated layers doors/trunk/engine/climate, Online/GSM и statuses сохранены как база.

### `0.1.0-alpha.19.3` — Field mappings / animated top-view remote card

По результатам Protocol Capture исправлены live seat/window состояния. Remote-card переведена на вид сверху и получила locked/unlocked glow, Online/GSM, статусы и анимации дверей, багажника, двигателя, климата и подтверждённого водительского окна.

### `0.1.0-alpha.19.2` — Extended diagnostic capture / map-ready GPS

Protocol Capture расширен до schema 2: units, safe top-level metadata, structure inventory и GPS map-ready fixes. Новых GWM remote payload или telemetry mappings нет.

### `0.1.0-alpha.19.1` — Baseline-preserving diagnostics export

Стандартная диагностика всегда сохраняет первый telemetry baseline + до 5000 самых свежих корректных записей; полный JSONL не обрезается.

### `0.1.0-alpha.19` — Protocol capture tooling

Добавлен diagnostics export текущей JSONL-сессии, сенсор capture и сервис `gwm_jolion.add_capture_marker`.

### `0.1.0-alpha.18` — Protocol capture mode

Добавлен включаемый JSONL режим поиска GWM-кодов с raw snapshot/diff и безопасной фильтрацией персональных данных.

### `0.1.0-alpha.17` — Primary card editor registration fix

Visual editor основной карточки больше не зависит от порядка загрузки bundled frontend ресурсов.

### `0.1.0-alpha.16` — Primary card visual editor

Основная `custom:gwm-jolion-card` получила visual editor Home Assistant.

### `0.1.0-alpha.15` — Telemetry change history

Добавлена bounded история изменений важных raw-сигналов для физических тестов.

### `0.1.0-alpha.14` — Command lifecycle / state accuracy

Исправлено зависание управления после ошибочных remote-команд и ложное отображение неизвестных состояний.

### `0.1.0-alpha.13` — Second card / Remote UI

Добавлена вторая встроенная `custom:gwm-jolion-remote-card`.

### `0.1.0-alpha.12` — Equipment capabilities

Добавлены ручные настройки опционального оборудования и backend capability guards.

### `0.1.0-alpha.11` — vehicleBasicsInfo

Исправлен разбор `vehicleBasicsInfo → data → config` и безопасный diagnostic snapshot.

### `0.1.0-alpha.10` — Reliability

Надёжность удалённых команд, remote-start guard и reauth без добавления новых payload.

### Следующие `0.1.x`

Физическое подтверждение экспериментальных функций, дальнейшая расшифровка телеметрии и UX-полировка карточек.

### `0.2.x` — Comfort

Подогревы, defrost, сиденья и другие comfort-функции после подтверждения протокола.

### `0.3.x` — Card / UX

Расширенная настройка секций и поддержка нескольких автомобилей в карточках.

### `0.4.x` — Deep Telemetry

TPMS status, температуры, 12V и дополнительные диагностические сигналы.

### `0.5.x` — Multi-car / Capabilities

Несколько автомобилей и автоматическое создание только поддерживаемых сущностей.

### `1.0.0`

Стабильный релиз после физических проверок ключевых функций на нескольких Haval Jolion.
