# Roadmap — GWM Jolion для Home Assistant

План развития `ha-gwm-jolion`.

Статусы:

- ✅ реализовано / подтверждено;
- 🟢 реализовано в Alpha и требует дальнейшей проверки;
- 🧪 экспериментальная функция;
- ⏳ запланировано.

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
- 🟢 уровень масла GWM `oilQty`;

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
- ✅ bounded `signal_change_history` для важных raw-сигналов: первое значение + последующие изменения с временем;
- ✅ опциональный JSONL Protocol Capture: полный raw snapshot + `previous → value` после каждого успешного опроса;
- ✅ различение источника capture-записи: `poll`, `manual_button`, `remote_command`, `remote_start_guard`;
- ✅ пользовательские маркеры этапов теста без изменения telemetry baseline;
- ✅ диагностический сенсор состояния Protocol Capture;
- ✅ экспорт текущей capture-сессии внутри стандартной диагностики Home Assistant: первый baseline + до 5000 самых свежих корректных записей; полный JSONL не обрезается;
- ✅ Protocol Capture schema 2 сохраняет `items[].unit`, набор реально увиденных item-ключей и безопасные top-level значения `getLastStatus`;
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

- 🟢 чтение raw водительского подогрева;
- 🟢 чтение raw пассажирского подогрева;
- ⏳ подтверждение значений уровней;
- ⏳ подтверждение payload управления подогревом;
- ⏳ вентиляция сидений для поддерживаемых комплектаций;
- ⏳ `select` entities для уровней после подтверждения протокола.

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
- ✅ собственная Jolion-подобная SVG-иллюстрация автомобиля без сторонних assets;
- ✅ изменяемый цвет кузова;
- ✅ статусы вокруг изображения автомобиля;
- ✅ круглые кнопки управления в компоновке автомобильного пульта;
- ✅ настраиваемые информационные плитки;
- ✅ visual editor Home Assistant;
- ✅ выбор кнопок управления из редактора;
- ✅ выбор информационных показателей из редактора;
- ✅ выбор отображаемых статусов из редактора;
- ✅ capability-фильтрация отсутствующего оборудования;
- ✅ mobile layout;
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

### `0.1.0-alpha.19.2` — Extended diagnostic capture / map-ready GPS

Перед физическими тестами Protocol Capture расширен до schema 2: сохраняются единицы измерения `items[].unit`, безопасные top-level поля `getLastStatus` (`percentageOfOil`, `oilQty`, `charge`, времена обновления и др.), их изменения, а также безопасные structure-инвентаризации `getLastStatus`, `vehicleBasicsInfo` и `findStatus`. Неизвестные потенциально чувствительные значения не сохраняются. GPS `device_tracker` приведён к числовым координатам и готов для стандартной карты Home Assistant. Новых GWM remote payload или telemetry mappings нет.

### `0.1.0-alpha.19.1` — Baseline-preserving diagnostics export

Диагностический hotfix Protocol Capture: стандартная диагностика Home Assistant теперь всегда сохраняет первый telemetry baseline отдельно и добавляет до 5000 самых свежих корректных записей. Baseline не входит в лимит, поэтому максимальный `session_export.records` — 5001 запись. Полный JSONL-журнал не обрезается. Добавлены явные поля `baseline_preserved`, `valid_records_in_file`, `recent_records_limit` и `selection`. Новых GWM remote payload или telemetry mappings нет.

### `0.1.0-alpha.19` — Protocol capture tooling

Protocol Capture подготовлен к полевой сессии: текущий JSONL-журнал вкладывается в стандартную диагностику Home Assistant, добавлен диагностический сенсор состояния записи и сервис `gwm_jolion.add_capture_marker` для меток этапов. Маркеры не меняют telemetry baseline. Экспорт был ограничен 2000 записями; политика экспорта улучшена в `0.1.0-alpha.19.1`. Новых GWM remote payload нет.

### `0.1.0-alpha.18` — Protocol capture mode

Добавлен включаемый режим поиска GWM-кодов. Каждый успешный cloud refresh дописывает в отдельный JSONL-файл полный raw snapshot, diff `previous → value`, неизвестные сигналы и безопасный `vehicleBasicsInfo`; ручные, автоматические и post-command refresh получают разные source-маркеры. Автоматические capture-записи не содержат VIN, координаты, аккаунт, токены и device identifiers. Новых GWM remote payload нет.

### `0.1.0-alpha.17` — Primary card editor registration fix

Исправлена регистрация visual editor основной карточки: editor-модуль теперь использует `customElements.whenDefined()` и загружается перед основной карточкой, поэтому поддержка редактора больше не зависит от порядка исполнения bundled frontend-ресурсов Home Assistant. Remote-команды и GWM payload не менялись.

### `0.1.0-alpha.16` — Primary card visual editor

Основная `custom:gwm-jolion-card` получила visual editor Home Assistant. Пользователь может выбирать кнопки управления, датчики/информацию и дополнительные панели без ручного YAML. Старые карточки сохраняют прежний полный набор элементов, а capability-настройки комплектации по-прежнему имеют приоритет. Новых GWM payload нет.

### `0.1.0-alpha.15` — Telemetry change history

Добавлена ограниченная история изменений важных raw-сигналов для физических тестов. Диагностика фиксирует первое наблюдение и каждое последующее изменение значения с временем для двигателя, замка, дверей, окон, климата, сидений, руля, defrost, световых кодов и неизвестных сигналов. Шумные показатели вроде топлива, пробега, TPMS pressure и GSM в историю не добавляются.

### `0.1.0-alpha.14` — Command lifecycle / state accuracy

Исправлено зависание управления после ошибочных remote-команд: явные T5-ошибки больше не ждут общий timeout, состояние `in_progress` сбрасывается после освобождения lock, а обе карточки не выдают отсутствие телеметрии за реальное `выключено / закрыто / offline`. Новых GWM payload нет.

### `0.1.0-alpha.13` — Second card / Remote UI

Добавлена вторая встроенная карточка `custom:gwm-jolion-remote-card`: изображение Jolion-подобного SUV, статусы вокруг автомобиля, круглые кнопки управления, информационные плитки и visual editor с выбором отображаемых функций. Код и SVG выполнены независимо от `lovelace-starline-card`, использованного только как визуальный референс.

### `0.1.0-alpha.12` — Equipment capabilities

Добавлены ручные настройки опционального оборудования. Отключённые функции скрываются из карточек, связанные optional-сущности не загружаются, а соответствующие remote-команды блокируются на backend. Универсальные поля `vehicleBasicsInfo` не используются как признак физического наличия оборудования.

### `0.1.0-alpha.11` — vehicleBasicsInfo

Исправлен разбор `vehicleBasicsInfo → data → config`. Диагностика теперь сохраняет только разрешённые climate/comfort значения, включая параметры сидений, defrost, `skyLight` и `shadeScreen`, без чувствительных идентификаторов. Новых remote payload автомобиля нет.

### `0.1.0-alpha.10` — Reliability

Надёжность удалённых команд, remote-start guard, reauth и понятные состояния выполнения без добавления новых payload автомобиля.

### Следующие `0.1.x`

Физическое подтверждение уже реализованных экспериментальных функций, дальнейшая расшифровка телеметрии и UX-полировка двух карточек.

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
