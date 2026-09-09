# 大模型編譯設定對照與移植

查核日期：2026-09-09。本次以 `hkg-enhanced` 最新的
`3ba3706000a47a5015855e23473c3b52525869ff` 為修改基礎，包含已合併的繁中介面更新。

## 固定的比較版本

| 專案 | 分支／commit | tinygrad |
|---|---|---|
| TonyBinheWu/sunnypilot（修改前） | hkg-enhanced / `3ba3706000a47a5015855e23473c3b52525869ff` | sunnypilot/tinygrad `e837e367aac9e1a66e689f4f32ce20ca9367df13` |
| sunnypilot/sunnypilot | master / `6135084c941d4d947dd90c78326a557c3c857f89` | 同上 |
| commaai/openpilot | master / `802a231bd20c6a0b0b88ebbb891970aee40cf1b5` | tinygrad/tinygrad `f6fc4e3f2c3db5fae1e19cbfbc3ad9fc579a12ae` |

主程式的 opendbc 子模組仍為 `03f4ba63901497df0fe4d6aa01cfd3504fe7aa69`。
本次沒有合併上游的整個分支，也沒有修改車輛控制、UI 功能或模型掉幀警示。

## 編譯設定差異

修改前，本分支以下三條編譯路徑的設定都與 sunnypilot 上述版本一致。

| 項目 | sunnypilot／本分支修改前 | openpilot master | 本次修改後 |
|---|---|---|---|
| 裝置端 Chestnut 編譯 | `TC_OCCUPANCY_OPT=1` | `TC_MIN_GLOBALS=32` | `TC_MIN_GLOBALS=32`，並移植實際優化邏輯 |
| 單一／Model Manager 模型建置 workflow | `TC_OCCUPANCY_OPT=1`，未列出 `FRAME_DEV` | 以其裝置端旗標為對齊基準 | 與裝置端使用相同 Chestnut 旗標 |
| 預設大模型建置 workflow | `DEBUG=2 WARP_DEV=QCOM`，沒有上述 TC 旗標 | `DEBUG=1 FRAME_DEV=CPU TC_MIN_GLOBALS=32` | 與裝置端使用相同 Chestnut 旗標 |
| comma 裝置端編譯的相機尺寸 | 只編譯建置主機的尺寸 | 同時包含 `1928x1208`、`1344x760` | 同上，包含駕駛監控 warp |
| 駕駛模型分塊容量估計 | 以一份 ONNX 大小估計 | 乘上相機配置數量後估計 | 同上 |
| QCOM 小模型旗標 | `DEV=QCOM IMAGE=1 FLOAT16=1 NOLOCALS=1 JIT_BATCH_SIZE=0 OPENPILOT_HACKS=1` | 相同 | 保留 |
| tinygrad 執行版本 | `e837e36` | `f6fc4e3` | 保留 `e837e36`；不是整套編譯器版本完全一致 |

統一後的 Chestnut 旗標：

```text
DEBUG=1 DEV=USB+AMD:LLVM FRAME_DEV=CPU FLOAT16=1 JIT_BATCH_SIZE=0 GMMU=0 TC_OPT=2 TC_MIN_GLOBALS=32
```

不能只由旗標名稱推斷效能：本次查核的 `e837e36` 沒有任何讀取
`TC_OCCUPANCY_OPT` 的程式，也沒有原生 `TC_MIN_GLOBALS`。
因此只換環境變數不會取得上游的優化。原本 workflow 的 `WARP_DEV`
也不能當成當前 stock compiler 實際在 QCOM 執行 warp 的證據。

來源：[openpilot SConscript](https://github.com/commaai/openpilot/blob/802a231bd20c6a0b0b88ebbb891970aee40cf1b5/openpilot/selfdrive/modeld/SConscript)、
[sunnypilot SConscript](https://github.com/sunnypilot/sunnypilot/blob/6135084c941d4d947dd90c78326a557c3c857f89/openpilot/selfdrive/modeld/SConscript)、
[單一模型 workflow](https://github.com/sunnypilot/sunnypilot/blob/6135084c941d4d947dd90c78326a557c3c857f89/.github/workflows/sunnypilot-build-model.yaml)、
[預設模型 workflow](https://github.com/sunnypilot/sunnypilot/blob/6135084c941d4d947dd90c78326a557c3c857f89/.github/workflows/build-default-models.yaml)。

## 為何保留 tinygrad 執行版本

[Model Manager 的 CTM catalog](https://github.com/sunnypilot/sunnypilot-models/blob/fdfa1c7357c9605db701f391cc392a66b926a03d/docs/driving_models_chestnut_v25.json)
指定 `e837e36`。直接更換整個 tinygrad 子模組會失去既有下載 PKL 的版本配對；
目前沒有完成所有 catalog 模型在 `f6fc4e3` 的相容性驗證或重建。

本次新增 `openpilot/sunnypilot/modeld_v2/compile_optimizations.py`，移植
[上游 TC_MIN_GLOBALS 變更](https://github.com/tinygrad/tinygrad/commit/f6fc4e3f2c3db5fae1e19cbfbc3ad9fc579a12ae)：

- 保持相同的 tensor-core 優化次序與全域工作量判斷，將新版 `SPLIT` 寫法轉為
  `e837e36` 的 `UPCAST`／`LOCAL` API。它會避免額外的 N upcast 使全域工作量太小；
  不表示每個 kernel 都能產生至少 32 組工作，也不保證延遲下降。
- 將 `TC_MIN_GLOBALS` 放進編譯快取鍵和 worker context，並在新啟動的編譯 worker
  安裝移植邏輯。新舊設定不共用同一編譯快取項目。
- 只在 stock 與 sunnypilot compiler 的執行入口啟用。modeld 匯入編譯器提供的
  queue helper 時不安裝此邏輯。`TC_MIN_GLOBALS=0` 沿用原有優化。
- 新 PKL 的頂層 `compiler_optimizer` 記錄實際設定、移植／原生實作及來源 commit；
  舊 PKL 不需要新增此欄位。沒有修改 tinygrad 的序列化類別或現有下載檔案。
- SCons 將優化程式與旗標納入相依項，避免 Chestnut 的 Python action 因旗標變更
  沒有重建。保留 sunnypilot 的 `SKIP_TINYGRAD_COMPILE` 路徑。

這是編譯旗標、指定優化與打包流程的對齊，不能宣稱產物與完整 `f6fc4e3`
編譯器逐位元一致。

## 何時生效

只有使用本分支修改後的 compiler **重新編譯**的模型會採用此優化。
既有 Model Manager CTM／CTMV2、遠端 catalog、下載 URL 和 HF 預編譯快取不會自動改寫。
重新下載同一個舊產物也不等於重編譯；啟用 `SKIP_TINYGRAD_COMPILE` 的套件建置
仍可使用已有的預編譯檔案。

需要新 CTM 時，使用本分支的 `sunnypilot-build-model.yaml`，選擇 `chestnut`，
並固定 CTM 的 ONNX 來源 ref，例如 `68b5f8e48602f4f88041efd7de6c99e97fda454e`。
建置需要可用的 Chestnut runner 和完整 ONNX，會同時產生兩種相機尺寸。
使用新名稱及新產物雜湊保存建置結果，驗證後再設定相應 catalog；本次沒有
啟動硬體 workflow、發布新的模型或自動替換使用中的模型。

編譯紀錄應包含 `Compiler optimizer:`、`tc_min_globals: 32` 和
`implementation: sunnypilot-e837e36-backport`。這能證明選中了編譯邏輯，
不能單獨證明 c3x 掉幀問題已解決。新舊模型需用同樣的硬體、輸入與設定比較，
參考 [CTM_C3X_MODEL_LAG.md](CTM_C3X_MODEL_LAG.md)。

## 驗證範圍

- RDNA4 Python 模擬後端：旗標確實改變編譯結果，且新舊設定的快取項目分開。
- 新啟動的平行 worker：兩種旗標值的結果分別與主程序一致。
- RDNA4 矩陣運算對照 NumPy，並在未安裝編譯移植的獨立程序載入／回放兩種 PKL。
- SCons 建置圖：comma、Linux PC、macOS 都包含兩種相機尺寸；分塊估計、編譯
  相依項、CPU 綁定與 skip 路徑符合預期。
- 原有 compiler 的 queue／metadata／時間取樣測試。

結果：37 項測試通過、3 個子案例通過；1 項原有測試因上游已移除舊 warp API 而跳過。
Ruff、workflow YAML 與 Python 語法檢查通過。

以上為離線驗證。此環境沒有 Chestnut，尚未重建或實際執行完整 CTM。
完整 modeld loader 測試也受限於此工作區缺少編譯完成的 `msgq.visionipc.visionipc_pyx`；
不把矩陣模擬測試當成完整模型或 c3x／c4 實機驗證。
