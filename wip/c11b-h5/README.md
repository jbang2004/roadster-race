# c11b / h5：前轮上方肩部（未合并）

主线（`neon_loop/tools/blender`）仍是 c10b + q8 车头。这里存的是 2026-10-22 那一轮做到一半的工作，没有合并。

## 用户确认的读法

"上棱越过前轮保持利棱，只把下面做微凸、去掉轮拱边折角。以 h5 为准，修掉门缝前的软影后再合并。"

规格见 `neon_loop/tools/blender/SPEC.md` U-1 的 2026-10-22 条目。

## 文件

- 这些文件是 c11b 树的 `tools/blender/` 下的同名文件：`design2.py`、`shell2.py`、`curves2.py`、`shell_lock.json`、`check.py`（带 smooth 指标）、`crease_smooth.py`、`fitlib.py`。`regions/front.py` 与主线相同，没有放进来。
- `report_c11b.txt`：c11b 的完整报告，包括全部数字和回滚开关。
- 三张对比图，每张从左到右是 c10b / h5 / c11b：正面右翼子板、斜前方前轮上方、门缝前放大。

## 构建 h5

把上面这些文件复制进 `neon_loop/tools/blender/`，然后在 `neon_loop/` 下运行：

```bash
env QF_C11_SOFT=0 QF_C11_FX=-1.82,-1.35,-1.25,-0.45 QF_C11_FP=1 \
  $BLENDER -b --python tools/blender/build_game_car.py -- \
  --live none --unlock fender_top,shoulder,wall,wall_black --out <dir> --only hi --raw
```

## 还没做完（c11c）

1. **门缝前的软影。** 侧标上方 x −1.44…−1.04、z .78–.84 处有一层软影。原因：填充在 z .84/.80 外扩 24/35 mm，再在 −1.25…−0.45 收回到没动的车门，面向后倾 3–4.8°。
   - 目标：看起来和 c10b 一样干净；x −1.3 到门缝之间的后倾不超过 c10b + 1°。
   - 正面 R_min 保持 ≥ 5 cm，曲率不变号。
   - 车门不许加宽：p013 显示模型车门已比照片宽约 1.9 cm/侧。
2. **翻板附近的倾角变化率。** h5 上升方向是 3.29 / 3.97 / 2.30，限值 2.66。这个指标用来防翻板扭曲。
3. **复查。** 改完后重跑 smooth（STEP_REL 0.45）、轮胎间隙、p013、锁、预算、反光闭环检测和测试。
