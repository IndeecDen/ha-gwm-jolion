# Changelog

## 0.1.0-alpha.3

Backend/diagnostics release. Встроенная `gwm-jolion-card` не изменялась.

### Добавлено

- безопасная диагностика Home Assistant с автоматическим удалением VIN, телефона, PIN, пароля, token, IMSI/ICCID и координат;
- история неизвестных GWM telemetry codes;
- счётчик неизвестных кодов как diagnostic sensor;
- время последнего успешного обновления GWM как timestamp sensor;
- безопасный whitelist snapshot `vehicleBasicsInfo`;
- informational capability framework для комплектаций Jolion;
- dependency-free protocol registry;
- четыре диагностических binary sensor для окон `2210001–2210004` без неподтверждённой привязки к физической позиции;
- `services.yaml` для всех зарегистрированных действий;
- английские переводы config/services;
- `PROTOCOL.md`;
- unit tests для protocol/capabilities;
- GitHub Actions: HACS validation, hassfest, compile/JSON/YAML/tests.

### Изменено

- удалённые команды дополнительно защищены lock от одновременного выполнения;
- последняя команда сразу получает состояние `pending` во время ожидания результата;
- `vehicleBasicsInfo` по-прежнему необязателен и не ломает основной polling при ошибке.

### Не изменялось

- frontend-файл `gwm-jolion-card.js`;
- payload существующих подтверждённых команд;
- climate payload;
- существующие unique IDs основных сущностей.
