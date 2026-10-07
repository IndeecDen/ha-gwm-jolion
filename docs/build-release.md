# Сборка и выпуск Jolion Locator

Этот документ предназначен сопровождающим проекта и описывает локальную сборку APK и архива интеграции. Пользовательская установка описана в [README](../README.md) и [руководстве Locator](golion-locator.md).

## Сборка и проверки

Нужны JDK 17, Android SDK Platform 35 с Build Tools 35.0.0 и Gradle 8.14.3. Задайте `JAVA_HOME` и `ANDROID_HOME` в своей среде. В `android/` выполните:

Для проверки изменений выполните:

```sh
gradle --no-daemon clean testDebugUnitTest lintDebug assembleRelease
```

Для публикации настройте `android/signing.properties` (поля `storeFile`,
`storePassword`, `keyAlias`, `keyPassword`), затем соберите `assembleRelease`.
Без этого файла release-APK остаётся неподписанным; debug-ключ автоматически
не подставляется. Пароли и keystore не храните в Git.
Проверьте APK через `apksigner verify --verbose --print-certs` и установите его
поверх предыдущей сборки на целевом ГУ перед публикацией.

В локальной настройке этого checkout используются `android/release-signing.jks`
и `android/signing.properties`; оба файла исключены из Git. Сделайте как минимум
две зашифрованные резервные копии keystore и пароля отдельно от компьютера.
Не отправляйте их в GitHub и не прикладывайте к APK. Если ключ будет утрачен,
обновление поверх установленной release-версии станет невозможно.

Первый переход с APK, подписанного debug-ключом, на release-ключ потребует
удалить приложение и установить release APK заново: Android не допускает
обновление с другой подписью. Перед удалением на ГУ передайте всю очередь GPS,
сохраните ID автомобиля и ключ Locator, а также OAuth-токен Диска, если он
используется. После перехода будущие APK, подписанные сохранённым release-ключом,
устанавливаются вручную поверх предыдущих версий.

Интеграция проверяется из корня репозитория:

```sh
python -m compileall -q custom_components/gwm_jolion
python -m pytest -q tests
```

Браузерные сценарии используют Playwright и установленный Chrome/Edge:

```sh
npm ci
npm run test:browser
```

CI выполняет Python- и Android-проверки независимо.

### Проверки настоящего HA

Зафиксированное окружение: Python 3.14, HA 2026.10.0b0, зависимости
`tests/ha/requirements.txt`. Это проверка совместимости с текущей beta HA;
Минимальная версия в HACS — HA 2026.7.
Для Linux:

```sh
python -m venv .venv-ha
.venv-ha/bin/pip install -r tests/ha/requirements.txt
GWM_HA_STRICT=1 .venv-ha/bin/python -m pytest -q tests/ha -o asyncio_mode=auto
```

Строгий режим завершает проверку ошибкой при пропущенных тестах. Windows:
`uv pip install --python .venv-ha-modern/Scripts/python.exe -r tests/ha/requirements.txt`,
затем `.venv-ha-modern\Scripts\python.exe tools/run_ha_tests.py`.
Этот вспомогательный запуск адаптирует только POSIX-импорты CLI и создание
локальной пары сокетов asyncio; вызовы POSIX-заглушек вызывают ошибку.
Эталонный запуск в CI использует Linux без этих адаптеров.

После успешной сборки создайте локальный комплект:

```sh
python scripts/package_release.py
```

Перед выпуском проверьте комплект офлайн (пример для следующей версии):

```sh
python scripts/check_release.py --tag 0.2.0 --previous-code 13
```

Проверяются тег, версии manifest/Gradle/APK, возрастание `versionCode`, пакет,
SDK, прежний сертификат, SHA-256 и CRC архивов. Номер прошлого APK нужно брать
из последнего опубликованного APK или распространённой тестовой сборки.
Стабильная 0.2.0 использует код 14 для обновления тестовых APK с кодом 13.

Workflow `Version release` запускается вручную. Он выполняет тесты, собирает и
публикует APK, ZIP и `SHA256SUMS.txt`; beta получает флаг prerelease.
Для него нужны GitHub secrets `ANDROID_KEYSTORE_BASE64` и
`ANDROID_SIGNING_PROPERTIES` (содержимое signing.properties, `storeFile=release-signing.jks`).
Локальные скрипты GitHub не изменяют. Подготовка workflow не означает его запуск.

В `dist/` появятся APK, архив HA, общий архив и `SHA256SUMS.txt`. Скрипт проверяет совпадение версий и берёт компонент из **этого** репозитория. Архив HA можно распаковать в каталог конфигурации HA; после установки перезапустите HA и обновите браузер. Детальная настройка — в [руководстве Locator](golion-locator.md) и [инструкции для Яндекс.Диска](golion-locator-yandex.md).

Release APK собирается с настроенным ключом подписи. APK с другой подписью не установится поверх прежнего APK без удаления старого приложения, поэтому сначала выгрузите очередь GPS и сохраните ID/ключ. Ключ подписи нельзя включать в репозиторий или архив релиза.

Проверки на настоящем Harman AOSP 8.1, в работающем Home Assistant и через SIM с белым списком остаются отдельным этапом: локальные тесты этого не подтверждают.
