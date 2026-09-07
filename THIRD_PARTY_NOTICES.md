# Third-party notices

Parts of the GWM protocol client and Home Assistant integration structure are adapted from MIT-licensed projects.

## roblencheg/HAVAL_H3

MIT License — Copyright (c) 2026 roblencheg.

Source: [roblencheg/HAVAL_H3](https://github.com/roblencheg/HAVAL_H3).

## moryoav/ha-gwm-ev

MIT License — Copyright (c) 2026 Yoav Mor.

Source: [moryoav/ha-gwm-ev](https://github.com/moryoav/ha-gwm-ev).

## Anonym-tsk/lovelace-starline-card

Source: [Anonym-tsk/lovelace-starline-card](https://github.com/Anonym-tsk/lovelace-starline-card).

Reference revision: [bdf451f46d65863eae102b5b90ec4327bc4559a5](https://github.com/Anonym-tsk/lovelace-starline-card/tree/bdf451f46d65863eae102b5b90ec4327bc4559a5).

The `gwm-jolion-remote-card` adapts this project's vehicle artwork and layout, circular control styling, and smoke and blink animations. Original PNG assets for the light and dark themes are embedded losslessly in the remote card. The illustration is the upstream generic vehicle, not an independently drawn Jolion model.

GWM Jolion entity discovery, vehicle states and service calls are used in place of the StarLine integration. Climate indication, responsive status tiles and updates that preserve animation progress are part of the adaptation.

The upstream materials are licensed under GPL-3.0. The adapted [gwm-jolion-remote-card.js](custom_components/gwm_jolion/frontend/gwm-jolion-remote-card.js) is distributed under GPL-3.0-only. The full license is included in [LICENSE.starline](custom_components/gwm_jolion/frontend/LICENSE.starline); additional asset details are in the [frontend notices](custom_components/gwm_jolion/frontend/THIRD_PARTY_NOTICES.md).

Other integration files retain their existing licenses. The main integration's MIT license is available in [LICENSE](LICENSE); it does not replace the GPL license of the adapted remote card or the upstream materials.

## Acknowledgements / Благодарности

Спасибо **Anonym-tsk**, всем авторам и участникам **lovelace-starline-card** за исходную карточку, оформление, графику и анимации, которые легли в основу обновлённого пульта GWM Jolion.

Спасибо **roblencheg**, **Yoav Mor (moryoav)** и всем авторам и участникам **HAVAL_H3** и **ha-gwm-ev** за открытые реализации, использованные при разработке клиента протокола и структуры интеграции.

Благодарим всех участников этих проектов за код, документацию, тестирование, сообщения об ошибках и улучшения, а также сообщество Home Assistant за платформу и инструменты. Эта благодарность относится ко всем авторам и участникам, включая не перечисленных здесь поимённо; история вкладов сохраняется в исходных репозиториях.
