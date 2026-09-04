# Roadmap — GWM Jolion для Home Assistant

Этот файл фиксирует план развития проекта `ha-gwm-jolion`.

Статусы:

- ✅ подтверждено / реализовано;
- 🟢 реализовано в Alpha и тестируется;
- 🧪 эксперимент;
- 🚧 в разработке;
- ⏳ запланировано.

## 0. Базовая интеграция

- ✅ отдельный domain `gwm_jolion`;
- ✅ Config Flow;
- ✅ авторизация в российском GWM Cloud;
- ✅ подпись API-запросов;
- ✅ `getLastStatus`;
- ✅ `findStatus`;
- ✅ coordinator polling;
- ✅ T5 send/poll result;
- ✅ PIN security check;
- ✅ общий cooldown удалённых команд;
- ✅ безопасное хранение PIN в options;
- ⏳ reauth и обработка дополнительных вариантов ошибок cloud;
- ⏳ multi-vehicle support;
- ⏳ capability detection по каждой машине.

## 1. Телеметрия автомобиля

### Подтверждено

- ✅ пробег;
- ✅ топливо;
- ✅ запас хода;
- ✅ GPS location;
- ✅ T-Box online;
- ✅ двигатель;
- ✅ центральный замок;
- ✅ 4 двери;
- ✅ багажник;
- ✅ 4 окна;
- ✅ давление 4 шин;
- ✅ температура 4 шин.

### Расширенная диагностика

- 🟢 TPMS pressure raw `2102001–2102004`;
- 🟢 TPMS temperature raw `2102007–2102010`;
- 🟢 window learn `2210010–2210013`;
- 🟢 seat heat raw `2220001`, `2220002`;
- 🟢 light raw `2204007–2204010`;
- 🟢 GPS authorization `2310001`;
- 🟢 T-Box signal `4105008`;
- 🧪 front defrost status `2222001`;
- 🧪 rear defrost status `2210032`;
- 🧪 steering wheel heat status `2060016`;
- 🧪 front windscreen heat status `2202111`;
- 🧪 air circulation status `2078020`.

### Нужно найти

- ⏳ реальное напряжение 12V АКБ;
- ⏳ SOC 12V АКБ, если cloud его отдаёт;
- ⏳ наружную температуру;
- ⏳ температуру салона;
- ⏳ температуру охлаждающей жидкости;
- ⏳ уровень/давление масла, если доступно;
- ⏳ дополнительные предупреждения автомобиля.

## 2. Удалённое управление

### Подтверждено

- ✅ запуск двигателя `0x03`;
- ✅ остановка двигателя `0x03`.

### Реализовано в Alpha

- 🟢 lock;
- 🟢 unlock;
- 🟢 открыть багажник;
- 🟢 закрыть багажник;
- 🟢 закрыть окна;
- 🟢 flash lights;
- 🟢 horn;
- 🟢 flash + horn;
- 🟢 задний defrost ON/OFF;
- 🟢 обогрев руля ON/OFF.

### План

- ⏳ открытие окон;
- ⏳ выбор отдельных окон;
- ⏳ открыть / закрыть люк;
- ⏳ tilt люка;
- ⏳ промежуточные положения люка;
- ⏳ шторка люка;
- ⏳ проверка условий перед командой;
- ⏳ подробный перевод ошибок T5;
- ⏳ статус pending/success/error для UI.

## 3. Климат

- 🟢 Home Assistant `climate` entity;
- 🟢 target temperature;
- 🟢 runtime 5–30 минут;
- 🟢 climate ON `0x04`;
- 🧪 climate OFF `0x04` / `switchOrder=0`;
- 🧪 `modifyVehicleRemoteCtlInfo`;
- 🧪 чтение сохранённой температуры GWM;
- 🧪 чтение сохранённого runtime GWM;
- 🧪 `vehicleBasicsInfo`;
- ⏳ реальное отображение оставшегося времени;
- ⏳ синхронизация HA ↔ GWM App;
- ⏳ blowing mode / power gear, если Jolion поддерживает remote control этих параметров.

## 4. Comfort-функции

### Defrost / стекло

- 🧪 передний defrost `0x0B`;
- 🟢 задний defrost `0x0B`;
- ⏳ электрический обогрев лобового `0x2A`;
- ⏳ реальные binary sensors для всех режимов.

### Сиденья

- 🟢 чтение raw водительского подогрева;
- 🟢 чтение raw пассажирского подогрева;
- ⏳ расшифровка уровней 0/1/2/3;
- ⏳ payload `0x0A` для подогрева;
- ⏳ вентиляция сидений для поддерживаемых комплектаций;
- ⏳ отдельные `select` / `number` entities.

### Руль

- 🟢 команда подогрева руля;
- 🧪 реальный status `2060016`;
- ⏳ switch entity с реальным readback.

### Салон

- 🧪 Cabin Clean / проветривание `0x11`;
- ⏳ air purifier `0x0C`, если поддерживается;
- ⏳ status и таймер очистителя.

## 5. TPMS

- ✅ фактическое давление 4 шин;
- ✅ фактическая температура 4 шин;
- 🟢 raw status-коды давления;
- 🟢 raw status-коды температуры;
- ⏳ расшифровка enum каждого status-кода;
- ⏳ отдельные binary sensors предупреждений;
- ⏳ визуальная подсветка проблемного колеса в карточке.

## 6. Карточка GWM Jolion

### Alpha

- 🧪 `custom:gwm-jolion-card`;
- 🧪 auto-discovery entities через Entity Registry;
- 🧪 engine / lock / climate controls;
- 🧪 fuel / range / mileage;
- 🧪 tyres;
- 🧪 body status;
- 🧪 T-Box / GPS / GSM.

### Следующая версия

- 🚧 исправить автоматическую регистрацию frontend;
- 🚧 гарантированная загрузка после HACS/manual update;
- 🚧 встроенный visual editor;
- 🚧 автоматический выбор автомобиля;
- 🚧 адаптивный desktop/mobile layout;
- 🚧 нормальные состояния loading/error/unavailable.

### Финальный дизайн

- ⏳ внешний вид уровня StarLine;
- ⏳ изображение Jolion;
- ⏳ динамические двери;
- ⏳ динамические окна;
- ⏳ багажник / люк;
- ⏳ климатический блок;
- ⏳ comfort-блок;
- ⏳ четыре колеса вокруг автомобиля;
- ⏳ GSM / GPS / T-Box diagnostics;
- ⏳ подтверждения опасных действий;
- ⏳ возможность скрывать ненужные секции.

## 7. Home Assistant architecture

- ✅ `sensor`;
- ✅ `binary_sensor`;
- ✅ `button`;
- ✅ `device_tracker`;
- ✅ `lock`;
- ✅ `climate`;
- ✅ `number`;
- ⏳ `switch` для функций с реальным readback;
- ⏳ `select` для seat levels / режимов;
- ⏳ diagnostics platform;
- ⏳ Repairs integration для проблем авторизации/API;
- ⏳ entity translations RU/EN;
- ⏳ device capabilities.

## 8. Надёжность и безопасность

- ✅ общий command cooldown;
- ✅ polling результата T5;
- ✅ experimental buttons disabled by default;
- ⏳ command queue;
- ⏳ блокировка конфликтующих T5-команд;
- ⏳ защита от повторного нажатия в frontend;
- ⏳ проверка lock state перед remote engine start;
- ⏳ понятные Home Assistant errors;
- ⏳ автоматическое удаление персональных данных из diagnostics;
- ⏳ тесты token refresh;
- ⏳ тесты timeout / GWM outage.

## 9. Публичный релиз и HACS

- ✅ структура HACS custom integration;
- ✅ MIT License;
- ✅ local Home Assistant brand assets;
- ✅ README;
- ✅ THIRD_PARTY_NOTICES;
- ⏳ GitHub Actions: HACS validation;
- ⏳ GitHub Actions: hassfest;
- ⏳ unit tests;
- ⏳ tagged pre-releases;
- ⏳ public repository;
- ⏳ публикация стабильного `v1.0.0`;
- ⏳ заявка в HACS default repositories после стабилизации.

## 10. План релизов

### `0.1.x` — Protocol Alpha

Телеметрия, основные команды, climate, сбор raw-кодов.

### `0.2.x` — Comfort Alpha

Defrost, сиденья, руль, Cabin Clean, расширенный `vehicleBasicsInfo`.

### `0.3.x` — Jolion Card

Стабильная встроенная карточка и visual editor.

### `0.4.x` — Deep Telemetry

TPMS statuses, свет, T-Box diagnostics, температуры и 12V.

### `0.5.x` — Multi-car / Capabilities

Несколько машин, разные комплектации, автоматическое создание только поддерживаемых entities.

### `1.0.0`

Стабильный релиз после физических проверок ключевых функций минимум на нескольких Haval Jolion.
