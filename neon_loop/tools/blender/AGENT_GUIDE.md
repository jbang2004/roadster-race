# 车身建模代理入门（FRONT / SIDE / REAR 区域代理先读这一页）

车：2026 Tesla Roadster 复刻（Blender 5.2 无头构建 → `public/assets/car/car_hi / car_lod1 / car_lod2.glb` + `car_meta.json`，three.js 游戏里加载）。
所有命令都在项目根 `neon_loop/` 下执行；Blender = `/Applications/Blender.app/Contents/MacOS/Blender`（脚本读 `$BLENDER`）；照片在 `../refs/`（只读）；备份在 `../backup/`（不准删）。
本页是命令和事实的集合；规则的权威是 `REGIONS.md`（所有权、接口、预算）和 `SPEC.md`（外观定义），历史推理在 `HISTORY.md`（不用读）。

## 1. 文件地图（`tools/blender/`）

| 文件 | 作用 |
|---|---|
| `build_game_car.py` | 入口：整车构建（外壳 → 区域钩子 → 轮子/内饰/贴花 → LOD → 导出 → `car_meta.json` → REPORT）。`--live <r>` `--out <dir>` `--only hi\|lod1\|lod2\|all` `--raw` `--check-lock` `--no-front`（P0 基准） |
| `regions/{front,side,rear}.py` | 区域模块（你改的就是这些，只改自己的）；`regions/ctx.py` 接口说明（协调者维护）；`regions/_base/` 分派时的快照 |
| `common.py` | 共享纯函数和常量（`HUBS` `W_DARK` `pchip` `Mesh/grid/prism`；锁定的 shell2.py 也从这里取 `HUBS` `cut_intake` 等） |
| `shell2.py` `design2.py` `curves2.py` `shell_lock.json` | **锁定外壳**，只读 |
| `shots.sh` | 出图总入口：构建 + 遮罩 + 叠图 + Cycles 对照表 + 反光 + 放大对 |
| `check.py <metric>` | 测量总入口，有目标值的打印 PASS/FAIL 表（nose rear roofline masks plan crease fold dihedral cam lock budget equiv panels） |
| `overlay.py <kind>` | 叠图总入口（views lines proj outline nose rear reading dump） |
| 引擎（上面两个分发到它们） | `render_ref_views.py`（Cycles/视角表 `VIEWS`）`mask_views.py` `overlay_views.py` `lines_overlay.py` `measure_*.py` `plan_report.py` `crease_report.py` `fold_report.py` `fold_fit.py` `dihedral_u.py` `cam.py` `cam_fit.py` `proj_overlay.py` `nose_overlay.py` `outline_overlay.py` `rear_overlay.py` `reading_overlay.py` `dump_lines.py` `dump_panels.py` `compare_panels.py` `glb_compare.py` `imgio.py` `shell2_view.py` |
| `_attic/` | 过期或一次性脚本（旧 `shots_r1*.sh`、`full_sheets.sh`、R1b 的 `front.py` / `shell_r1b.py`、`HANDOFF.md` …），不要用，需要时翻 |
| 文档 | `AGENT_GUIDE.md`（本页）`REGIONS.md` `SPEC.md` `REFS.md` `CALIB.md` `HISTORY.md` |

## 2. 坐标和固定值

* Blender 车身系：x 向**后**、y 横向（−y = 左）、z 向上，米。GLB / 游戏里是 −X 向前、+Z 向左、+Y 向上（`src/car/index.js` 再包一层，车头 −Z）。
* 轮心 x **−1.487**（前）/ **1.61**（后），|y| **0.885**，z **0.39**，轮胎半径 **0.39**（`ctx.HUBS` `HUB_Z` `R_TYRE` `R_ARCH` `WHEEL_Y`）。车头角 N 在 x −2.46（`design2.NOSE_XN`），尾翼后缘约 x 2.44。
* 外壳 18 块面片的缝、棱线和曲线名在 `ctx.A.D`（design2 的命名曲线 / 锚点：`bar_top` `face_black_bot` …）；用 `ctx.surf` / `ctx.surf_hi` 的 `cast()` 把部件贴到车身上，不要硬编码车身表面的数。
* 材质只用现有 23 种（REGIONS.md §1）；对象名前缀 `F_` `S_` `R_`；运行时依赖的名字（`Wing` `Wheel_*` …）不能改。
* 尾翼：默认**收起**（`ctx.cache` 里的收起位姿）；`high` 视角展开。`car_meta.json` 里的 `wing` 给游戏和出图工具用，只有 `--only all` 的构建才写它。

## 3. 相机和参考照片

`REFS.md` 是照片索引：哪张照片可信、用来判断什么、冲突时谁说了算。相机在 `render_ref_views.py` 的 `VIEWS`：p001 p002 p003 p004 p011 p012 p013 p014 p016 p017 p018 p019 r81 thrust high 来自统一校准（`CALIB.md`、`calib/solve.py`，2026-10-25）；p005 和旧机位 `<名>_v1` 是手配的。`cam.py` 是同一组相机的 numpy 版（`Cam(view).project(P)`）。`CALIB.md` 还有 15 个校准地标的 3D 位置（σ 5–10 mm）。
规则：车头车尾的前后位置以能看到车轮的视角为准；p013 只给俯视形状；两张高可信度照片互相矛盾时不要自己选，写 3 行报告。精度目标：轮廓 / 线条残差 ≤ 图宽的 1 %（1800 px 宽 → 18 px），`check.py` 按这个出 PASS/FAIL。新匹配一个相机要在 ≥ 3 处不改动的部位上验证。

## 4. 锁定规则（违反 = 该轮不合格）

* `shell2.py` `design2.py` `curves2.py` `shell_lock.json` 只读。不准运行 `--write-lock`、`--unlock`（`SHELL_UNLOCK` 环境变量同理）。
* 每次构建都会做锁定校验（18 块），必须不带 `--unlock` 通过：`python3 tools/blender/check.py lock`（约 5 s）。
* 只改自己拥有的文件。别的文件需要改 → 写进交付报告「请求」。不准写 `public/assets/car/`（用 `--out`）；不准启动 / 重启开发服务器（5180 上有一个）。
* 改代码用小范围精确替换。不写一次性测量脚本：缺功能就给 `check.py` / `overlay.py` / `shots.sh` 加参数。
* R2 前端和侧标（FRONT 的 `build`、SIDE 的 `side_markers`）从区域阶段起**默认开启**；`--no-front` 关掉它们（＝ P0 的基准构建），`--front` 仍可写但已无作用。预算只按默认构建算。

## 5. 三条标准命令

`<r>` = front | side | rear。`--live <r>` 只让你的区域用工作文件，其他区域用 `regions/_base/` 的快照。

**① 快速循环**（~20 s：构建 ~15 s + 遮罩 ~3 s；迭代中**不渲染 Cycles**）

```
tools/blender/shots.sh --round r1 --out shots/regions/<r>/r1 --live <r> --build shots/regions/<r>/build --views p013,p016,p018 --masks --ov
```
`--live` 先构建到 `--build` 目录（不给则是 `<out>/build`；日志 `build.log`，REPORT 行带按区域明细），遮罩进 `r1/masks/`，叠图进 `r1/ov/`（Workbench，模型 55 % 叠在照片上）。
`--masks` 在视角同时含 p013、p016、p018 时自动跑 `check.py nose`（三张缺一不可）。已有 GLB 时用 `--glb <file>` 代替 `--live`。常用视角：FRONT p016,p014,p005,p013；SIDE p018,p017,p003；REAR r81,thrust,p017,high,p013。

**② 完整对照表**（候选通过快速循环之后；Cycles，比快速循环慢得多，每个视角各渲一张）

```
tools/blender/shots.sh --round r1 --out shots/regions/<r>/r1 --glb shots/regions/<r>/build/car_hi.raw.glb --views p016,p018 --sheets [--reflect] [--glass-dark] \
    [--zoom p018:900:300:1000:330:1.5:v]
```
`sheet_<view>.jpg`：p0xx 照片在上渲染在下，r81 / thrust / high 左右并排。`--reflect` = 涂装面的反射线检查（`reflect/` 水平带，`reflect_v/` 垂直带；涉及车漆面时必做）。
`--zoom view:w:h:x:y:scale[:h|v]` 出放大对（可重复）。`--renders <dir>` 复用已有渲染，不重跑 Cycles。看全幅**和**放大，看得见的差异如实写。

**③ 交付检查**

```
B=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}; mkdir -p shots/regions/<r>/build
$B -b --python tools/blender/build_game_car.py -- --live <r> --out shots/regions/<r>/build --only all --raw > shots/regions/<r>/build/build.log
python3 tools/blender/check.py lock
python3 tools/blender/check.py budget shots/regions/<r>/build/build.log          # LOD 预算 + 你的区域对照配额
python3 tools/blender/check.py nose shots/regions/<r>/r1/masks                    # 有目标值的表; rear / roofline 对外壳, 一般不会变
npm test                                                                          # = node src/game/test/run.mjs
```
改过 `--front` 相关输出的再用 `--front` 构建一次，`check.py budget` 看 lod1 draw call。要证明"别的部分没动"：先用同一条构建命令把 `--live <r>` 换成 `--live none`、`--out` 换成 `shots/regions/<r>/base` 建一份基准，再
`python3 tools/blender/check.py equiv shots/regions/<r>/base shots/regions/<r>/build`（逐对象 / 逐材质三角形数和包围盒，只有你的区域对象应该有差）。

## 6. 预算

* 总：lod1 ≤ 60k 三角形 / ≤ 20 draw call，lod2 ≤ 15k / ≤ 10，hi ≤ 450k。当前（默认）：hi 255.2k / 38，lod1 57.2k / 18，lod2 8.4k / 7；`--front`：lod1 58.4k / **20**（已顶满）。
* 区域配额和实测值在 `REGIONS.md` §5；构建日志里的 `REGION BUDGET` 表按区域列出 hi / lod1 / lod2 三角形和新增 draw call。超配额 = 不合格；lod1 draw call 没有余量，新增材质组合要先问协调者。
* 超过配额之前先想：LOD 的做法（`ctx.mat_of(level, name)` 返回 None = 该级不要这种材质；`build(ctx, level)` 里按 level 简化）。

## 7. 已知并接受的偏差（不要当成 bug 去修）

1. **p013 与 p016 / p018 的车头 x 差约 10 cm**：p016 + p018 决定位置，p013 只给形状。`check.py nose` 里 p013 的 "front edge" / "nose centre" 两行会 FAIL，标成 `FAIL (accepted)`，看 shape-only 行。U 平面曲线在 x ≈ −2.06 处的曲率凹陷（1.28 → 0.37 → 1.23 1/m）已接受。p016 远侧翼子板比照片窄 50–185 px（相机问题，p013 证明车宽是对的）。
2. **后部软弧线（fold）**：弧线路径误差最大 5.7 cm（x 1.2–1.3，玻璃条方向 29–38°）；x 0.874–0.935 的滚动半径 < 5 cm；这是外壳，已锁定。`check.py fold` 的这两行同样标 accepted。
3. 外壳 L 接缝理论上能后移到 x −1.60，未使用；`B2_RATE` / `LAM_RATE` 是调出来的，不是推导的。

## 8. 交付模板

1. **残差表**：每条 SPEC 条目、每个视角：照片与模型的差（px 和 % 图宽）、通过 / 不通过（用 `check.py` 的表；没有目标值的写目测并说明）。
2. **对照表**：每个指定视角一张 `sheet_<view>.jpg`（全幅 + 放大）；涉及车漆面的附 `reflect/` `reflect_v/`。
3. **检查结果**：锁定校验、本区域 hi / lod1 / lod2 的三角形和 draw call（对照配额）、`npm test`。
4. **5 行说明**：做了什么、怎么理解的、和计划的差别、已知缺点、下一步。
5. **请求**：要别人或协调者改的东西（共享文件、新材质、相机、`src/car/*`）。
6. **冲突**：两个要求不能同时满足时 3 行写清（两边各要求多少、差多少），然后继续其余部分。

首看检查点（开工约 20–30 分钟）：1 张叠图 + 1 张 Workbench / 简单渲染 + 5 行说明；协调者回复后再继续。
