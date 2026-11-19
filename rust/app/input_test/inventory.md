# Clickable controls in the .slint files

Generated from `rust/app/ui` (one row per handler). The real-input test (`drive.py`) is checked against it.

| file:line | event | words | does |
|---|---|---|---|
| ui/dialogs/frame.slint:118 | clicked |  | `root.clicked()` |
| ui/dialogs/frame.slint:149 | clicked | close | `root.close()` |
| ui/dialogs/frame.slint:212 | clicked |  | `input.focus()` |
| ui/dialogs/frame.slint:234 | accepted |  | `root.accepted()` |
| ui/dialogs/frame.slint:235 | edited |  | `root.edited(self.text)` |
| ui/dialogs/frame.slint:266 | clicked |  | `root.toggled(root.text)` |
| ui/dialogs/info.slint:27 | close |  | `root.closed()` |
| ui/dialogs/info.slint:38 | clicked | 不同意 | `root.answered(false)` |
| ui/dialogs/info.slint:39 | clicked | 不同意 | `root.answered(true)` |
| ui/dialogs/info.slint:77 | close |  | `root.closed()` |
| ui/dialogs/info.slint:87 | clicked | 开始使用 | `root.start()` |
| ui/dialogs/info.slint:138 | close |  | `root.closed()` |
| ui/dialogs/info.slint:183 | clicked | 知道了 | `root.done()` |
| ui/dialogs/info.slint:224 | close |  | `root.closed()` |
| ui/dialogs/info.slint:234 | clicked | 导出日志 | `root.export-log()` |
| ui/dialogs/info.slint:235 | clicked | 知道了 | `root.done()` |
| ui/dialogs/names.slint:92 | clicked |  | `root.toggled(index)` |
| ui/dialogs/names.slint:124 | close |  | `root.closed()` |
| ui/dialogs/names.slint:137 | accepted |  | `root.save()` |
| ui/dialogs/names.slint:138 | edited |  | `root.name-edited(text)` |
| ui/dialogs/names.slint:144 | clicked | eye | `root.reveal()` |
| ui/dialogs/names.slint:162 | toggled |  | `root.toggled(tag)` |
| ui/dialogs/names.slint:175 | clicked | 删除 | `root.delete()` |
| ui/dialogs/names.slint:177 | clicked | 删除 | `root.save()` |
| ui/dialogs/names.slint:202 | close |  | `root.closed()` |
| ui/dialogs/names.slint:211 | edited |  | `root.edited(text)` |
| ui/dialogs/names.slint:222 | toggled |  | `root.toggled(index)` |
| ui/dialogs/names.slint:235 | clicked |  | `root.import()` |
| ui/dialogs/names.slint:261 | toggled |  | `root.toggled(tag)` |
| ui/dialogs/names.slint:286 | close |  | `root.closed()` |
| ui/dialogs/names.slint:291 | toggled | 点标签可以取消 | `root.toggled(tag)` |
| ui/dialogs/names.slint:292 | toggled | 点标签可以取消 | `root.toggled(tag)` |
| ui/dialogs/names.slint:307 | clicked | 返回 | `root.back()` |
| ui/dialogs/names.slint:308 | clicked | 导入 | `root.import()` |
| ui/dialogs/names.slint:332 | close |  | `root.closed()` |
| ui/dialogs/names.slint:339 | clicked |  | `root.answered(false)` |
| ui/dialogs/names.slint:340 | clicked |  | `root.answered(true)` |
| ui/dialogs/sound.slint:120 | close |  | `root.closed()` |
| ui/dialogs/sound.slint:133 | pressed |  | `root.pressed(x)` |
| ui/dialogs/sound.slint:145 | clicked |  | `root.toggle-song()` |
| ui/dialogs/sound.slint:147 | clicked |  | `root.cut()` |
| ui/dialogs/sound.slint:154 | clicked |  | `root.nudge(-1)` |
| ui/dialogs/sound.slint:155 | clicked |  | `root.nudge(1)` |
| ui/dialogs/sound.slint:164 | clicked |  | `root.toggle-preview()` |
| ui/dialogs/sound.slint:171 | clicked | 确定 | `root.ok()` |
| ui/guestedit/combo_dialog.slint:41 | close |  | `root.dismiss()` |
| ui/guestedit/combo_dialog.slint:74 | toggled |  | `root.person-toggled(index)` |
| ui/guestedit/combo_dialog.slint:91 | toggled |  | `root.play-toggled()` |
| ui/guestedit/combo_dialog.slint:92 | picked |  | `root.picked(key)` |
| ui/guestedit/combo_dialog.slint:98 | clicked | 删除 | `root.remove()` |
| ui/guestedit/combo_dialog.slint:100 | clicked | 删除 | `root.save()` |
| ui/guestedit/guest_dialog.slint:43 | close |  | `root.dismiss()` |
| ui/guestedit/guest_dialog.slint:89 | toggled |  | `root.play-toggled()` |
| ui/guestedit/guest_dialog.slint:90 | picked |  | `root.picked(key)` |
| ui/guestedit/guest_dialog.slint:96 | clicked | 删除 | `root.remove()` |
| ui/guestedit/guest_dialog.slint:98 | clicked | 删除 | `root.save()` |
| ui/guestedit/parts.slint:70 | clicked |  | `toggled()` |
| ui/guestedit/parts.slint:95 | clicked |  | `picked()` |
| ui/guestedit/parts.slint:118 | clicked |  | `ticked()` |
| ui/guestedit/parts.slint:129 | clicked |  | `ticked()` |
| ui/guestedit/parts.slint:156 | clicked |  | `replay()` |
| ui/guestedit/parts.slint:192 | toggled | 播放场景 | `play-toggled()` |
| ui/guestedit/parts.slint:206 | picked |  | `root.picked(item.key)` |
| ui/guestedit/parts.slint:232 | clicked |  | `root.clicked()` |
| ui/guestedit/parts.slint:309 | clicked |  | `close()` |
| ui/guestedit/scene_manager.slint:46 | close |  | `root.dismiss()` |
| ui/guestedit/scene_manager.slint:84 | picked |  | `root.picked(item.key)` |
| ui/guestedit/scene_manager.slint:122 | clicked |  | `root.play()` |
| ui/guestedit/scene_manager.slint:136 | clicked |  | `root.choose-song(index)` |
| ui/guestedit/scene_manager.slint:147 | clicked |  | `root.listen(index)` |
| ui/guestedit/scene_manager.slint:150 | clicked | 上传 | `root.upload()` |
| ui/guests/page.slint:90 | edited | 搜索名字、昵称或原因 | `GuestsBridge.search-edited(self.text)` |
| ui/guests/page.slint:93 | clicked | 场景管理 | `GuestsBridge.manage-scenes()` |
| ui/guests/page.slint:99 | clicked | 添加组合 | `GuestsBridge.add-combo()` |
| ui/guests/page.slint:101 | clicked | 添加嘉宾 | `GuestsBridge.add-guest()` |
| ui/guests/page.slint:110 | clicked | more | `more-menu.show()` |
| ui/guests/page.slint:125 | chosen | 复制名单 | `GuestsBridge.more-chosen(0)` |
| ui/guests/page.slint:127 | chosen | 清空嘉宾列表 | `GuestsBridge.more-chosen(1)` |
| ui/guests/page.slint:163 | pressed |  | `` |
| ui/guests/page.slint:314 | chosen |  | `GuestsBridge.row-menu(menu-row, i)` |
| ui/guests/page.slint:332 | clicked | 场景管理 | `GuestsBridge.manage-scenes()` |
| ui/guests/page.slint:333 | clicked | 添加嘉宾 | `GuestsBridge.add-guest()` |
| ui/guests/parts.slint:79 | clicked |  | `clicked()` |
| ui/guests/parts.slint:146 | clicked |  | `chosen()` |
| ui/history/page.slint:61 | clicked |  | `root.clicked()` |
| ui/history/page.slint:84 | clicked | warning | `root.clicked()` |
| ui/history/page.slint:126 | clicked |  | `root.clicked()` |
| ui/history/page.slint:160 | clicked |  | `HistoryData.day-toggled(item.day)` |
| ui/history/page.slint:166 | clicked |  | `HistoryData.picked-scan(item.scan)` |
| ui/history/page.slint:201 | clicked |  | `menu-open = !menu-open` |
| ui/history/page.slint:212 | clicked |  | `HistoryData.seat-clicked(index)` |
| ui/history/page.slint:217 | clicked |  | `menu-open = false` |
| ui/history/page.slint:244 | clicked |  | `` |
| ui/kit/buttons.slint:57 | clicked |  | `root.clicked()` |
| ui/kit/buttons.slint:79 | clicked |  | `root.clicked()` |
| ui/kit/buttons.slint:121 | clicked |  | `` |
| ui/kit/buttons.slint:158 | clicked |  | `` |
| ui/kit/fields.slint:50 | edited |  | `root.edited(self.text)` |
| ui/kit/fields.slint:51 | accepted |  | `root.accepted()` |
| ui/kit/fields.slint:68 | edited |  | `root.edited(t)` |
| ui/kit/fields.slint:77 | clicked |  | `` |
| ui/kit/frames.slint:64 | clicked |  | `root.close()` |
| ui/kit/frames.slint:91 | clicked |  | `root.clicked(left-button)` |
| ui/kit/frames.slint:98 | clicked |  | `root.clicked(label)` |
| ui/kit/frames.slint:138 | clicked |  | `root.act()` |
| ui/kit/frames.slint:171 | clicked |  | `root.act()` |
| ui/kit/rows.slint:87 | clicked |  | `root.clicked()` |
| ui/kit.slint:72 | clicked |  | `list.show()` |
| ui/kit.slint:93 | clicked | ✓ | `value = choice` |
| ui/list/cells.slint:59 | clicked |  | `` |
| ui/list/cells.slint:62 | clicked |  | `if tag-row.tag != "" { root.edit()` |
| ui/list/cells.slint:90 | clicked |  | `root.clicked()` |
| ui/list/cells.slint:101 | clicked |  | `root.eye-clicked()` |
| ui/list/page.slint:125 | clicked |  | `new-tag = true` |
| ui/list/page.slint:133 | accepted |  | `new-tag = false` |
| ui/list/page.slint:150 | picked |  | `picked-tag = i` |
| ui/list/page.slint:152 | menu |  | `` |
| ui/list/page.slint:169 | accepted |  | `editing-tag = ""` |
| ui/list/page.slint:188 | edited |  | `ListData.search-edited(text)` |
| ui/list/page.slint:192 | clicked | 批量导入 | `ListData.add-many()` |
| ui/list/page.slint:193 | clicked | 添加 | `ListData.add()` |
| ui/list/page.slint:197 | clicked |  | `more-menu.show()` |
| ui/list/page.slint:222 | clicked |  | `ListData.sort(column)` |
| ui/list/page.slint:223 | eye-clicked |  | `ListData.eye(!names-hidden)` |
| ui/list/page.slint:259 | clicked |  | `keys.focus()` |
| ui/list/page.slint:286 | clicked | 批量导入 | `ListData.add-many()` |
| ui/list/page.slint:287 | clicked | 添加 | `ListData.add()` |
| ui/list/page.slint:298 | pressed |  | `` |
| ui/list/page.slint:332 | clicked |  | `ListData.undo()` |
| ui/list/page.slint:343 | clicked | 复制名单 | `ListData.share()` |
| ui/list/page.slint:344 | clicked | 按原因补标签 | `ListData.recheck()` |
| ui/list/page.slint:346 | clicked | 清空黑名单 | `ListData.clear()` |
| ui/list/page.slint:355 | clicked | 编辑 | `ListData.edit(menu-index)` |
| ui/list/page.slint:356 | clicked | 复制名字 | `ListData.copy-name(menu-index)` |
| ui/list/page.slint:358 | clicked | 删除 | `ListData.delete(menu-index)` |
| ui/list/page.slint:367 | clicked | 编辑 | `editing-tag = menu-tag` |
| ui/list/page.slint:369 | clicked | 删除 | `ListData.remove-tag(menu-tag)` |
| ui/list/parts.slint:100 | clicked |  | `root.clicked()` |
| ui/list/parts.slint:117 | clicked |  | `root.clicked()` |
| ui/list/parts.slint:151 | edited |  | `root.edited(self.text)` |
| ui/list/parts.slint:152 | accepted |  | `root.accepted(self.text)` |
| ui/list/parts.slint:153 | pressed |  | `` |
| ui/list/parts.slint:183 | clicked |  | `root.clicked()` |
| ui/notices/notice.slint:254 | clicked |  | `root.clicked()` |
| ui/notices/notice.slint:290 | clicked |  | `root.clicked()` |
| ui/notices/toast.slint:31 | clicked |  | `root.act()` |
| ui/notices/update.slint:17 | clicked |  | `root.clicked()` |
| ui/notices/update.slint:39 | clicked |  | `root.clicked()` |
| ui/notices/update.slint:85 | clicked |  | `root.close-clicked()` |
| ui/notices/update.slint:121 | clicked | 跳过 | `root.skip()` |
| ui/notices/update.slint:122 | clicked | 跳过 | `root.act()` |
| ui/notices/update.slint:150 | clicked |  | `root.click-outside()` |
| ui/notices/update.slint:167 | clicked |  | `root.close-clicked()` |
| ui/notices/update.slint:201 | clicked | 稍后 | `root.later()` |
| ui/notices/update.slint:202 | clicked | 立即更新 | `root.now()` |
| ui/notices/update.slint:225 | later |  | `root.later()` |
| ui/notices/update.slint:226 | now |  | `root.now()` |
| ui/settings/page.slint:26 | chosen |  | `root.chosen(key, value)` |
| ui/settings/page.slint:27 | pressed |  | `root.pressed(key)` |
| ui/settings/page.slint:56 | clicked |  | `` |
| ui/settings/page.slint:68 | chosen |  | `root.chosen(key, value)` |
| ui/settings/page.slint:70 | chosen |  | `root.chosen(key, value)` |
| ui/settings/page.slint:72 | chosen |  | `root.chosen(key, value)` |
| ui/settings/page.slint:101 | chosen |  | `root.chosen(key, value)` |
| ui/settings/page.slint:102 | pressed |  | `root.pressed(key)` |
| ui/settings/rows.slint:45 | clicked |  | `root.clicked()` |
| ui/settings/rows.slint:61 | clicked |  | `root.clicked()` |
| ui/settings/rows.slint:94 | chosen |  | `root.chosen(data.key, v)` |
| ui/settings/rows.slint:101 | clicked |  | `root.pressed(data.key)` |
| ui/settings/setup.slint:122 | clicked |  | `root.dismiss()` |
| ui/settings/setup.slint:129 | clicked |  | `root.retry()` |
| ui/settings.slint:71 | clicked |  | `root.clicked()` |
| ui/settings.slint:128 | clicked | 常规 | `section = "general"` |
| ui/settings.slint:129 | clicked | 帮助 | `section = "help"` |
| ui/settings.slint:130 | clicked | 关于 | `section = "about"` |
| ui/settings.slint:165 | chosen |  | `dark = v == "深色"` |
| ui/shell/check_panel.slint:27 | clicked |  | `info-clicked()` |
| ui/shell/check_panel.slint:87 | changed | 显示 | `display-changed(key == "safe")` |
| ui/shell/check_panel.slint:89 | clicked | 显示说明 | `display-guide()` |
| ui/shell/check_panel.slint:103 | changed | 方式 | `auto-changed(key == "auto")` |
| ui/shell/check_panel.slint:110 | clicked |  | `hotkey-clicked()` |
| ui/shell/check_panel.slint:111 | pressed |  | `hotkey-key(text, ctrl, alt, shift, win)` |
| ui/shell/check_panel.slint:125 | clicked | 直播模式 | `stream-guide()` |
| ui/shell/check_panel.slint:133 | changed |  | `stream-changed(on)` |
| ui/shell/header.slint:49 | clicked |  | `root.clicked()` |
| ui/shell/header.slint:109 | clicked | ·   | `root.clicked()` |
| ui/shell/header.slint:124 | clicked | 有更新 | `root.clicked()` |
| ui/shell/header.slint:176 | clicked | pencil | `` |
| ui/shell/header.slint:197 | accepted |  | `editing = false` |
| ui/shell/header.slint:198 | pressed |  | `` |
| ui/shell/main.slint:107 | pressed |  | `` |
| ui/shell/main.slint:128 | clicked |  | `show-page(index)` |
| ui/shell/main.slint:138 | clicked |  | `update-clicked()` |
| ui/shell/main.slint:147 | clicked |  | `panel-open = !panel-open` |
| ui/shell/main.slint:203 | chosen |  | `settings-chosen(key, value)` |
| ui/shell/main.slint:204 | pressed |  | `settings-pressed(key)` |
| ui/shell/main.slint:208 | clicked |  | `panel-open = false` |
| ui/shell/main.slint:225 | changed |  | `display-changed(safe)` |
| ui/shell/main.slint:226 | changed |  | `auto-changed(on)` |
| ui/shell/main.slint:227 | clicked |  | `hotkey-clicked()` |
| ui/shell/main.slint:229 | changed |  | `stream-changed(on)` |
| ui/shell/parts.slint:41 | clicked |  | `if !chosen { changed(option.key)` |
| ui/shell/parts.slint:59 | clicked | info | `root.clicked()` |
| ui/shell/parts.slint:98 | pressed |  | `` |
| ui/shell/parts.slint:111 | clicked |  | `root.clicked()` |
| ui/stream/guide.slint:68 | clicked | ✕ | `done()` |
| ui/stream/guide.slint:106 | clicked | 知道了 | `done()` |
| ui/stream/panel.slint:29 | changed | 开启 | `` |
| ui/stream/parts.slint:34 | clicked |  | `` |
| ui/stream/parts.slint:55 | clicked |  | `root.clicked()` |
