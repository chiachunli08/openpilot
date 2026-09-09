# HKG Mapbox 導航與 taco2 導航模型整合

實作基礎：`TonyBinheWu/sunnypilot:hkg-enhanced` commit
`e7780940777fc2b82da051261cb6b2119b1065d9`（2026-09-09）。

| 相依項 | 本次固定版本 |
|---|---|
| `opendbc_repo` | `03f4ba63901497df0fe4d6aa01cfd3504fe7aa69` |
| `tinygrad_repo` | `e837e367aac9e1a66e689f4f32ce20ca9367df13` |
| taco2 參考 | `a8c957e9d98cb3c334ab60c09e731c262605ae56` |
| taco2 `navmodel.onnx` | SHA-256 `f851f19b0a9e2299639f18856e4879ee863918227b7cef6a07eb6b94a273a9aa`，12,259,173 bytes |

本次沒有修改 Hyundai/Kia 車輛控制、CAN 訊息、Panda safety 或 forwarding。
EV6 HDA2／Hyundai P 的轉向與縱向控制路徑保持原樣；導航意圖也不會控制實車方向燈。

## 實作結果與界線

| 層級 | 實作結果 | 可宣稱狀態 |
|---|---|---|
| Mapbox 路線與轉彎提示 | 修正缺少 banner 時沒有文字／動作的問題；發布路線、轉彎、距離、道路名稱、剩餘里程與 ETA | 已實作、離線測試完成 |
| C3X 顯示用地圖 | Mapbox 底圖、路線、本車位置／朝向、速度縮放、轉彎摘要及展開／收合 | 僅 `tizi`（comma 3X）建立面板；尚待 C3X 實機畫面驗證 |
| 導航意圖 | stock `modeld` 與 Model Selector／Chestnut 使用的 `modeld_v2` 共用同一套 desire 邏輯 | 已實作、離線測試完成 |
| taco2 模型用地圖 | 與顯示地圖分離，使用 LLK、taco2 樣式／比例、256×256 灰階輸入 | 已實作、合成圖資測試完成 |
| taco2 導航模型 | 停車時下載、驗證並預編譯；行駛時輸出路徑、不確定性、32 維 desire prediction 與 64 維 features | 已實作影子模式；尚待 Snapdragon 845 實機效能驗證 |
| 64 維特徵進入駕駛模型 | 僅允許帶有可追溯 taco2 特徵契約的模型 | 目前 stock 與 CTM 均不相容，保持停用；不能宣稱大模型已使用導航特徵 |

四個狀態彼此獨立：地圖顯示正常，不代表意圖已送入；意圖已送入，不代表
taco2 features 已產生；features 已產生，也不代表駕駛模型實際使用。

## 修正後的導航資料鏈

`NavDestination` → `navigationd` → Mapbox Directions → `navRoute`／
`navInstruction`／`navigationStateSP` → C3X 地圖與轉彎卡片。

- 優先使用 Mapbox banner instruction；若回應沒有 banner，使用 step 的
  `maneuver.instruction`、`type`、`modifier` 與道路名稱，避免有效路線沒有提示。
- 導航取消或抵達時，立即將路線與提示設為無效並刪除目的地綁定快取。
- 路線重算前先撤除舊轉彎卡片，發布 `recalculating`；重算失敗時分成
  `routeError` 與離線／離路的 `stale`。
- GPS、service 或定位失效時不發布有效轉彎提示。路線幾何可保留作為快取，
  但不會假裝目前指示仍有效。
- 快取包含目的地與 route ID；目的地不相符、取消或抵達後不得復活舊路線。
- Wi-Fi／行動網路只在初次取得或重算路線、下載尚未快取的 tile 時需要。
  斷線後可繼續使用相符的已載入路線及已快取圖資；缺少的 tile 會明確顯示為不完整。

支援一般轉彎、道路終點、靠左／右、分岔、合流、上／下匝道、換道、
迴轉、圓環／rotary、抵達及無法分類時的通用直行圖示。沒有來源文字時只顯示
通用提示，不生成道路名稱。

## 硬體判定

專案硬體表明 `tizi` 是 comma 3X，`tici` 是 comma 3。判定不使用兩者共用的
Snapdragon 平台、CPU 架構或 `COMMA_HARDWARE`：

| 功能 | `tizi` C3X | `tici` C3 | `mici` C4／其他 |
|---|---:|---:|---:|
| 駕駛可見 Mapbox 面板及其渲染資源 | 是 | 否 | 否 |
| 一般路線與轉彎提示 | 是 | 是 | 依既有 UI／導航資料可用性 |
| 導航 desire | 依模型 desire 介面 | 依模型 desire 介面 | 依模型 desire 介面 |
| taco2 模型地圖及導航模型 | 影子模式 | 影子模式 | 未驗證，停用 |

非 C3X 不建立 `MapboxNavigationRenderer`，也不因顯示開關啟動顯示專用渲染。
在 C3 上只有使用 taco2 影子模型時，才會啟動模型專用地圖渲染；兩種地圖輸出
檔案和有效性完全分開。

## 顯示用地圖

`mapbox_mapd` 使用 Mapbox `navigation-night-v1` raster tiles，將目前路線疊在
底圖上，再依外部 GPS 朝向旋轉。本車圖示固定在中心，車速增加時縮小比例。
輸出以原子更換方式寫入 `/dev/shm`；UI 只接受預期目錄內的檔案，避免載入任意路徑。

面板預設為收合尺寸，點擊可展開或收合。它保留 Mapbox／OpenStreetMap attribution，
並在頂部顯示下一步、距離，底部顯示剩餘里程與 ETA。`displayImageValid=false`
或資料超過 2.5 秒時，不沿用舊位置畫面。

Mapbox Static Tiles API 的格式及快取規則：
[Static Tiles API](https://docs.mapbox.com/api/maps/static-tiles/)。顯示 attribution 的要求：
[Mapbox attribution](https://docs.mapbox.com/help/dive-deeper/attribution/)。

## 導航意圖

`NavigationModelBridge` 同時用於：

- `openpilot/selfdrive/modeld/modeld.py`（stock runner）；
- `openpilot/sunnypilot/modeld_v2/modeld.py`（Model Selector／Chestnut runner）。

它以精確的 `maneuverType + maneuverModifier` 組合分類，不做任意 `left`／`right`
子字串搜尋：

| Mapbox 類別 | desire 類別 |
|---|---|
| `turn`、`end of road`、圓環／rotary 出口 | `turnLeft`／`turnRight` |
| `fork`、`merge`、`on ramp`、`off ramp`、`continue` | `keepLeft`／`keepRight` |
| 明確 `lane change` | `laneChangeLeft`／`laneChangeRight` |

觸發距離依車速與上述類別調整；同一 route／maneuver 只送一次 pulse。無效定位、
導航失效、資料超過 2.5 秒、無效距離或過近時不送。既有模型 desire、駕駛轉向介入
及相反方向燈具有優先權；相同方向的人工方向燈可以共存。程式只提供「可打哪一側燈」
的畫面提示，實車方向燈一直由駕駛操作。

desire 是模型提示，不是強制轉向、安全判定或導航完成保證。必須以同一模型、同一場景
比較無意圖／左轉／右轉輸出，才能判定所選權重是否學會合理回應。

## taco2 模型地圖與導航模型

來源：

- [taco2 map_renderer.cc](https://github.com/commaai/openpilot/blob/a8c957e9d98cb3c334ab60c09e731c262605ae56/selfdrive/navd/map_renderer.cc)
- [taco2 style.json](https://github.com/commaai/openpilot/blob/a8c957e9d98cb3c334ab60c09e731c262605ae56/selfdrive/navd/style.json)
- [taco2 nav.cc](https://github.com/commaai/openpilot/blob/a8c957e9d98cb3c334ab60c09e731c262605ae56/selfdrive/modeld/models/nav.cc)
- [taco2 navmodeld.cc](https://github.com/commaai/openpilot/blob/a8c957e9d98cb3c334ab60c09e731c262605ae56/selfdrive/modeld/navmodeld.cc)

實際下載並解析該 commit 的 `navmodel.onnx` 後確認：

- input：`input_img`，float `[1, 1, 256, 256]`；
- output：float `[1, 228]`；
- output 0–65：33 個 `(x, y)` mean；
- 66–131：對應 log standard deviation；
- 132–163：32 維 desire prediction；
- 164–227：64 維 learned navigation features。

另以 ONNX reference runtime 對真實權重執行 `[1,1,256,256]` 零輸入，取得有限值的
`[1,228]` 輸出，並成功拆成 33 點路徑及 64 維特徵；這驗證模型檔與輸出解析契約，
不代表 C3／C3X 的 QCOM 效能或實車導航行為已驗證。

模型地圖使用 `liveLocationKalman` 的有效地理位置與 calibrated NED yaw，保持 taco2
約 2 m/pixel 的連續比例、中心／朝向、512 來源裁切為 256、灰色 5-pixel 路線及
RGB888 第一通道（不是亮度混合）的單通道 `uint8 / 255` 前處理。歷史 private style 無法取得完整 3×3 tiles 時，
`modelImageValid` 為 false，不會拿彩色駕駛地圖代替。

private style 優先沿用 taco2 的 `maps.comma.ai` 裝置簽章 JWT 路徑；裝置未註冊、
金鑰不可用或服務不相容時，再嘗試使用者提供的 Mapbox token。JWT 不寫入 Params、
檔案或日誌。

啟用影子模型後，`navigation_model_manager` 只在 offroad：

1. 下載固定 URL；
2. 同時驗證大小與 SHA-256；
3. 使用本分支 tinygrad 與 stock QCOM 模型旗標（`DEV=QCOM`、`IMAGE=1`、
   `FLOAT16=1`、`NOLOCALS=1`、`JIT_BATCH_SIZE=0`、`OPENPILOT_HACKS=1`），並保留
   `TC_MIN_GLOBALS=32`、`GMMU=0`，預編譯 QCOM TinyJit；
4. 原子寫入 PKL 與包含 compiler/source 版本的 sidecar；
5. 設定 `NavigationModelInstallStatus=ready`。

onroad 的 `navigation_modeld` 只載入已驗證的預編譯檔案，不在開車開始時編譯。

## 為何目前不能把 64 維直接交給 CTM

本次重新解析此分支實際 ONNX：

| 模型 | 主要輸入 |
|---|---|
| stock | `img`、`big_img`、`features_buffer [1,24,512]`、`desire_pulse [1,25,8]`、`traffic_convention`、`action_t` |
| big／目前 CTM 介面 | `img`、`big_img`、`features_buffer [1,32,32,512]`、`desire_pulse [1,33,8]`、`traffic_convention`、`action_t` |

兩者都沒有 navigation feature input。`features_buffer` 是駕駛模型自身的歷史視覺
特徵，不能放 taco2 的 64 維資料。

即使未來 ONNX 出現一個大小為 64 的 `nav_features`，也不會自動融合。本次將
模型 SHA-256 和 ONNX metadata 中的 `navigation_feature_contract`、
`navigation_feature_source_sha256` 保留到編譯 metadata；runtime 只有在輸入形狀
正確，而且契約可追溯到固定 taco2 navmodel 時才設為 compatible。無有效 features
時會向該 optional input 明確寫入零，不能殘留上一條路線。

taco2 原始 `supercombo.onnx`（SHA-256
`f794d65ddfb3600e0b3f7d7e894d1dd278b88569de863aae41246eec43f035cf`）有
`nav_features [1,64]`，但也使用 2022 年的影像、100-frame desire/history、
`driving_style` 與 6108-output 契約。沒有完成現行 parser、控制、模型時序和車上安全
驗證前，不會用它取代目前駕駛模型。

## 設定與狀態

OSM 選單及 sunnylink schema 新增：

1. `NavigationEnabled`：路線處理；
2. `NavigationTurnPromptEnabled`：行車畫面轉彎卡片；
3. `MapboxMapDisplayEnabled`：僅 C3X 的地圖面板；
4. `NavigationIntentEnabled`：將有效 maneuver 轉為現有 desire；
5. `NavigationModelEnabled`：停車下載／編譯並以影子模式執行；
6. `NavigationModelFusionEnabled`：僅 runtime 證實契約相容時可操作。

裝置 OSM 選單另外顯示 route、map、intent、navigation model 四組 runtime 狀態。
主要 cereal 診斷訊息為 `navigationStateSP`、`mapboxNavigationStateSP`、
`navigationIntentStateSP`、`navigationModelStateSP`。

token 沿用 `MapboxPublicKey`／`MapboxSecretKey` 及既有 M0/M1/S0/S1／QR 解碼；
不可寫死 token，也不在失敗例外中輸出含 token URL。目的地沿用 `NavDestination`，
可直接輸入 `latitude, longitude`；地址透過現有 Mapbox geocoder／sunnylink 流程寫入
同一個參數。

## 驗證

離線測試涵蓋：

- 目的地取消、抵達、重啟快取、離線續航、離路重算失敗、GPS 失效；
- banner 缺失的轉彎提示 fallback 及 token 日誌遮蔽；
- turn／keep／ramp／lane-change／U-turn 分類、速度距離窗、去重、駕駛優先權；
- stock 與 modeld_v2 共用 bridge、route mismatch、特徵過期／清零及契約 gate；
- C3X 精確硬體 gate、LLK pose、Mapbox 與 taco2 分離地圖、256×256 灰階輸入；
- 228-output 拆解、模型檔 hash／size、編譯 sidecar；
- local OSM、sunnylink schema、QR／token 與翻譯完整性；
- Cap'n Proto、service header 與 Params C++ 建置。

本次結果：導航／UI／sunnylink 組合測試 `227 passed, 2 skipped, 4 subtests passed`；
完整 `modeld_v2` 測試 `119 passed, 1 skipped, 3 subtests passed`。另外成功建置
`libcereal.a`、`libparams_c.so`、`services.h` 與測試所需的 `visionipc_pyx.so`。

此開發環境不是 C3X／EV6，以下項目尚未完成，不能列為實車驗證：

1. C3X 上 Mapbox 畫面位置、觸控展開／收合、文字可讀性；
2. 真實路線的下一步、道路名稱、取消、抵達、重算與離線影片；
3. C3／C3X 上導航模型下載、QCOM 預編譯、冷啟動及 onroad 載入；
4. `navigation_modeld.executionTime`、CPU、記憶體、溫度及 driving model 掉幀；
5. 所選 stock／CTM 對 turn desire 的無意圖／左／右同場景輸出比較；
6. 任何新訓練、明確相容的 64 維導航駕駛模型。

實機第一輪應停車啟用並等待 `NavigationModelInstallStatus=ready`，再設定短距離目的地。
拍攝 C3X 畫面，同步保存上述四個 SP message、`modelV2`、`deviceState` 與 modeld log。
依序測試正常網路、路線載入後斷網、GPS 暫失、重算、取消、抵達；若出現 model lag，
先停用 taco2 影子模型重跑同一路段做 A/B，不調整 Panda 或車輛控制。

## Mapbox 授權提醒

Mapbox 的公開條款會變更。查核時的
[Mapbox Terms of Service](https://www.mapbox.com/legal/tos) 對 vehicle-related applications
要求另外的 development/commercial license。部署到 EV6 前，帳號擁有者必須自行確認
token scope、計費、tile cache 與車載用途授權；本程式實作不代表取得 Mapbox 授權。
