# OSM 路口形狀與方向燈意圖：離線資料準備

這次交付的是 **OSM 路口資料處理工具與模型輸入稽核**。尚未讓行車模型接收 OSM，也未完成「避免轉錯車道」功能。工具不會在裝置啟動時執行；更新此提交不會改變行車轉向行為。

## 本次確認的版本

2026-09-07 開始工作時，遠端 `TonyBinheWu/sunnypilot:hkg-enhanced` 指向
`6135084c941d4d947dd90c78326a557c3c857f89`，釘選的 opendbc 為
`sunnypilot/opendbc:f95f996f5917dcbbf2e32fe51b606a24cf836af6`。

這個基底沒有 `HkgLowSpeedTorque` 開關，也沒有先前的 Mapbox navigationd 或 `nav_features` 移植。
310 的低速動態扭力功能可在 `ev6-low-speed-torque:deafa7dff672a89cc7e4b0fabdd71bec695fa3b9` 的文件與自訂子模組版本找到。
不能把不同分支／提交的功能視為目前 `hkg-enhanced` 已有的功能。

本次基底的 CAN-FD controller `STEER_MAX` 與 `hyundai_canfd_tx_hook` 的 `max_torque` 都是 270。
這是 CAN 指令值，不是 Nm。本次未提高扭力、放寬安全檢查或更換子模組，**350 尚未實作**。
Experimental Mode 或功能名稱裡的 Experimental 不會讓車型轉向檢查失效。

- [本次基底的控制器參數](https://github.com/sunnypilot/opendbc/blob/f95f996f5917dcbbf2e32fe51b606a24cf836af6/opendbc/car/hyundai/values.py)
- [本次基底的 CAN-FD 轉向檢查](https://github.com/sunnypilot/opendbc/blob/f95f996f5917dcbbf2e32fe51b606a24cf836af6/opendbc/safety/modes/hyundai_canfd.h)
- [先前 310 分支的說明](https://github.com/TonyBinheWu/sunnypilot/blob/deafa7dff672a89cc7e4b0fabdd71bec695fa3b9/docs/EV6_LOW_SPEED_TORQUE.md)

## 為何還不能接進現有模型

已重新讀取本機完整 ONNX 檔案，並將 SHA-256 與本次基底的 Git LFS 指標核對一致。
結果記錄在 [HKG_OSM_MODEL_AUDIT.json](HKG_OSM_MODEL_AUDIT.json)。

| 模型 | SHA-256 | 本次輸入稽核 |
| --- | --- | --- |
| driving_supercombo.onnx | `659727c4d4839adc4992a254409a54259a8756a743f2d567bf5fdc6579f8009b` | 影像、desire、交通方向、action delay、recurrent features；沒有導航輸入 |
| big_driving_supercombo.onnx | `1791d5940b2c048d0639813426dd2cf1d6f2a6727ed51e17c8bcea8bbe754123` | 影像、desire、交通方向、action delay、recurrent features；沒有導航輸入 |

輸入名、尺寸或宣告一個未被使用的 `nav_features` 都不足以建立導航能力。方向 desire 也無法表示出口形狀或目標車道。
路網經緯度不能直接覆蓋模型的視覺歷史特徵。這份稽核只適用於以上兩個固定模型；裝置另行下載的模型需要另行稽核。

要完成原需求，仍缺少配對訓練過的道路／導航編碼器與駕駛模型權重，以及其輸入契約。
其後還需要同步定位、地圖、路線、方向燈與相機時間，處理改道及資料失效，再做 replay、裝置延遲及封閉場地驗證。
本次沒有取得這些配對權重或實際車道對齊資料，因此未接入 modeld。

## 工具現在能做什麼

`openpilot/sunnypilot/navd/tools/osm_turn_context.py` 只讀取本機 JSON，輸出道路候選與原因：

- 輸入 OSM `elements`，以及回放中已確定的來向道路、路口 node、相鄰上一個 node、位置、航向及方向燈。
- 核對定位／CAN 有效、樣本時間、定位精度、來向道路方向、車輛相對於來向道路的位置。
- 保留出口折線形狀，轉成以車輛為原點的公尺座標：X 朝前、Y 朝左。
- 處理支援道路的雙向、單向、反向單向、一般小客車通行標籤，以及單一 via-node 的基本禁轉／僅能轉向關係。
- 同側多個出口時回報 `ambiguous`；無方向燈、雙黃燈、過期／未來樣本、資料缺漏或無法處理的規則時不選路。
- 每條幾何最多保留 80 公尺，遇下一個已映射的道路路口即停止，不自動延伸到下一個出口。

| 輸出狀態 | 意義 |
| --- | --- |
| `unique_road_candidate` | 支援的輸入範圍內只有一條相符道路，仍只是意圖假設 |
| `ambiguous` | 多條道路符合相同方向燈，沒有選定道路 |
| `withheld` | 資料、定位、訊號或規則不足以選定道路 |

所有結果的 `model_input_ready` 都為 false，`target_lane` 都為 null。
`lane_tags` 只保留原始標籤；車道數與 turn:lanes 無法單獨決定轉彎後落在哪一個車道。
路網中心線也可能位於雙向道路中央，**不是車輛應追蹤的車道中心線**。

限制：這不是完整 routing engine，也沒有自動定位匹配或下載地圖。
呼叫端必須提供完整路口節點、道路與相關 restriction 關係，並先證實定位匹配正確；本工具不能偵測被整條漏掉的道路或關係。
不解析 via-way、複雜／同一 way 的限制、條件式限制、迴轉、近直行分叉、環形道路或一般地區法規；相關情況會保留為未決或不產生候選。
工具不會從兩条鄰近道路推論它們相連，也不會建立跨越實體分隔島的轉向曲線。
其中 1 秒樣本、5 公尺精度、2～60 公尺路口距離及 30 度航向門檻只是離線工具的檢查設定，並非經實車驗證的行車安全參數。

OSM 標籤語意參考：[oneway](https://wiki.openstreetmap.org/wiki/Key:oneway)、[turn restriction](https://wiki.openstreetmap.org/wiki/Relation:restriction)、[turn:lanes](https://wiki.openstreetmap.org/wiki/Key:turn)。

## 重現

在儲存庫根目錄執行人工路口範例；不需要車輛、網路、模型或 token：

```bash
python -m openpilot.sunnypilot.navd.tools.osm_turn_context \
  openpilot/sunnypilot/navd/tests/fixtures/osm_turn_snapshot.json
```

fixture 是人工建立的測試路口，不是台灣道路。範例左轉結果保留出口後向左前方彎曲的幾何，且不選擇車道。
`observation.now_s`、`state_time_s`、`match_time_s` 必須使用同一個回放時鐘。
`match_time_s` 是定位匹配所使用的定位時間，不是檔案讀取時間；不能用「現在」掩蓋舊定位。
輸出附上輸入檔案 SHA-256 供回放比對。`node_ids` 只列實際節點；80 公尺截斷時最後一個幾何點可能是內插點。

稽核完整 ONNX 模型需要 Python 的 `onnx` 套件，不能將 LFS 指標文字檔當成模型：

```bash
python -m openpilot.sunnypilot.navd.tools.audit_route_model \
  /path/to/driving_supercombo.onnx /path/to/big_driving_supercombo.onnx
```

## 本次驗證

```bash
python -m unittest \
  openpilot.sunnypilot.navd.tests.test_osm_turn_context \
  openpilot.sunnypilot.navd.tests.test_audit_route_model -v
```

21 項測試通過，涵蓋左右轉、反向進路、道路形狀、同側多路歧義、訊號取消、定位／時間錯誤、
單向與通行權、禁轉／僅能轉向、未支援限制、缺漏與障礙、距離截斷，以及 ONNX 假導航輸入。
另執行本機範例 CLI、實際 ONNX 輸入稽核、Ruff 及 `git diff --check`。
未執行行車模型導航推論、完整裝置建置、Panda 韌體建置或實車測試；這些結果不能證明模型已會沿 OSM 轉彎。
