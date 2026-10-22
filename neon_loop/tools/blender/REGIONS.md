# 区域拆分规格（骨架锁定后的细节阶段）

外观设计以 `SPEC.md` 为准（现行定义）；历史与推理见 `HISTORY.md`（原 ROADSTER_DESIGN.md，其中的「用户更正」仍有约束力）。入门页：`AGENT_GUIDE.md`。本文件规定：谁拥有哪些文件、区域模块的接口、
并行开发时如何互不干扰、每个区域的内容/机位/验收，以及集成流程。

## 1. 所有权

| 归属 | 文件 / 代码 | 说明 |
|---|---|---|
| SHELL（冻结） | `shell2.py` `design2.py` `curves2.py` `shell_lock.json`；`build_game_car.py` 里的外壳后处理（`cut_arches` `add_floor` `mark_sharp` `glass_half_width` `Surf`） | R1e 验收后 18 块面片全部锁定；区域代理**只读**。每次构建都会做锁定校验，校验失败＝该轮不合格。 |
| FRONT | `regions/front.py` | 见 §4 |
| SIDE | `regions/side.py` | 见 §4 |
| REAR | `regions/rear.py`；运行时 `src/car/index.js` 中尾翼收放的部分、`src/car/jets.js` | 见 §4 |
| COMMON（只有协调者能改） | `build_game_car.py` 其余部分（材质表 `M`、轮子、内饰、贴花、LOD、导出、`car_meta.json` 组装）、`regions/ctx.py`、`regions/_base/`、`common.py`、`src/car/materials.js`、`render_ref_views.py` 的 VIEWS、`public/assets/car/*` | 区域代理需要改这里时，写进交付报告里的「请求」一节，由协调者决定 |

* 材质只用现有 23 种（Paint Glass Trim PanelGap HeadLens HeadDRL TailLamp BrakeLamp ReverseLamp SideMarker Tyre Rim BrakeDisc Caliper Reflector IntLeather IntPlastic IntScreen IntAccent Decal Carbon GlossBlack Nozzle）。新材质 = 请求。
* 运行时依赖的名字不能改：节点 `Wing`、`WingPlates*`、`Wheel_/Spin_/Brake_xx`、`Steering`；灯的发光按材质名驱动；`meta.decals` 的 doorL/doorR/hood/plate。
* 区域对象名加前缀：`F_` / `S_` / `R_`（运行时依赖的名字除外），避免 `.001` 冲突。

## 2. 区域模块接口（`regions/<r>.py`）

```python
NAME = 'front'                      # 'front' | 'side' | 'rear'
def shell_post(ctx): ...            # 可选：在 hi 外壳上做的切割/分色（front: 进气口; rear: 尾面分色 refine_tail + cut_boundary）
def build(ctx, level): -> [Object]  # 静态部件，合并进 Body；level 0 = hi, 1 = lod1, 2 = lod2
def nodes(ctx, level): -> {name: Object}   # 可选：单独导出的节点，按字典顺序挂到 Car 下（rear: Thrusters, Wing；lod2 为空）
def decals(ctx, level): -> [Object] # 可选：并入 Decals 节点的贴花片（rear: Decal_plate；lod2 没有 Decals 节点，返回 []）
def lod_post(ctx, level, body): ... # 可选：LOD 车身上的处理（rear: blacken_tail）
def meta(ctx): -> dict              # 可选：并入 car_meta.json（rear: wing，decals.plate；'decals' 逐键合并）
```

`shell_post` 的调用顺序：REAR →［轮拱切割］→ FRONT → SIDE →［地板］（REAR 必须在轮拱切割之前：后轮拱会细分同一块尾部）。
每个 level 内的调用顺序：FRONT → SIDE → REAR 的 `build`、`nodes`、`decals`。

`ctx`（`regions/ctx.py`，协调者维护）显式提供，**区域代码不得读 `build_game_car.py` 的全局变量**（纯函数和常量用 `import common`）：

* `ctx.level`、`ctx.body`、`ctx.surf`、`ctx.surf_hi`。`Surf`：`cast(origin, dir, off=0, maxd=6) -> (p, n) | (None, None)`、BVH。
  `ctx.surf_hi` 永远是 hi 车身；`ctx.surf` 是**当前 level 自己的车身**（level 0 = hi，lod1 / lod2 = 抽稀后的车身；只在 REAR 的钩子里设成 LOD 车身）。
  P0 保持拆分前的行为：FRONT 和 SIDE 在所有 level 都投射到 `ctx.surf_hi`；REAR 投射到 `ctx.surf`。要改是区域自己的几何决定，写进交付报告。
* `ctx.mk(bm, name, mat, smooth)`、`ctx.mat(name)`、`ctx.mat_of(level, name)`（某 level 不要的材质返回 None；规则表是 `build_game_car.py` 的 `LEVEL_MATS`）
* `ctx.A`：外壳接口（`A.D` = design2 的命名曲线/锚点，`A.S2` = shell2，`A.glass_half_width(x)`），`ctx.HUBS` `ctx.HUB_Z` `ctx.R_ARCH` `ctx.R_TYRE` `ctx.WHEEL_Y`
* 工具：`ctx.patch`（投射到 `ctx.surf`）`CB` `Builder` `W_DARK` `smooth` `mark_sharp` `cb_obj` `link` `join`
* `ctx.oldbody`、`ctx.front_r2`（`--oldbody` / `--front` 开关）、`ctx.flag(name)`、`ctx.arg(name, default)`、`ctx.cache`（一次构建内缓存常量）
* `ctx.report(key, value)`：写进构建报告里本区域的备注（`REGION NOTE` 行）

P0 之后 `common.py` 放共享的纯函数和常量（`pchip` `smooth` `HUBS` `W_DARK`、`Mesh/grid/prism`）；其中「R1b 解析前脸」那一块（`build_rows` `hood_z` `front_x` …）只是 `regions/front.py` 现在还在用的旧外壳公式，FRONT 移植到 `ctx.A` 后删除。

## 3. 并行开发的隔离

* `build_game_car.py -- --live front|side|rear|all`（默认 all，可逗号分隔）：`--live` 之外的区域从 `regions/_base/<r>.py`（分派时的快照）载入，
  所以别的代理改到一半的文件不会影响你的构建。非 `all` 时必须给 `--out`（否则拒绝运行，避免写到 `public/assets/car/`）。构建日志第一行 `REGIONS front=base side=base rear=live` 说明各区域用的是哪一份。
* 每个区域代理的构建一律 `--out shots/regions/<r>/build`（加 `--raw`），渲染/叠图都用 `--glb` 指向它、`--out` 指向 `shots/regions/<r>/rN/`。
  **不准写 `public/assets/car/`**（游戏和其他代理在用）——只有协调者在集成时写。
* `car_meta.json` 只在 `--only all` 时写（`--only hi|lod1|lod2` 会打印 `car_meta.json not written`）。
* 不准运行 `--write-lock` / `--unlock`（锁定只由协调者做）。
* 只改自己拥有的文件；别的文件需要改 → 报告里「请求」。
* 每轮交付后协调者验收；通过的版本复制到 `regions/_base/<r>.py`，别的代理下一次构建就会用上。

## 4. 各区域内容、机位与验收

通用验收：对应机位的 Cycles 对照表（照片 vs 渲染，全幅 + 放大）和 Workbench 叠图；涉及车漆面的改动做 `--reflect h|v`；
锁定校验通过；LOD 预算按 §5；全幅和放大都要看，**不准把看得见的差异说成“很小”**。

**FRONT**（p016、p014 夜间、p005、p013 机头）
* L4 灯带 HeadDRL：一条连续细白灯条，从一角到另一角；正视中间略拱，俯视中间略前凸，两端在角上略向下弯；挂在 R1e 的灯带边界曲线上。
* 黑色前脸（GlossBlack，约 0.10–0.12 m 高，略向后下倾）+ HeadLens 细投射灯条；黑色进气口（`shell_post` 切口）+ 向前伸出的黑色薄扰流板（z ≈ 0.27）。
* L7 引擎盖缝：x ≈ -1.81 的前备箱盖横缝、到挡风玻璃下沿（x ≈ -1.63）的 cowl 窄条、005 里角上的弧形缝（角三角面翻板的分缝）。
* 角三角面与 L6 斜面是外壳几何（R1e），FRONT 只做挂在上面的缝和细节。
* 现有 `regions/front.py` 是 R1b 外壳时代的生成器（只在 `--front` 时启用）：它用 `common.py` 里的旧解析公式（`hood_z` `front_x` `build_rows` …）摆部件；移植时改用 `ctx.A` 的锚点，然后删掉 `common.py` 里那一块。

**SIDE**（p018、p017、p003、p013 分缝）
* L13 车门缝：前门缝在前轮拱后（约 x -0.89，略前倾，两段式），后门缝约 x 0.35–0.46；在肩面上也可见（俯视两侧车身边缘各两处小切口）。剪刀门不需要能开。
* L8 玻璃分缝：车顶横缝约 x -0.29 与 x 0.64、中段纵缝、门玻璃里的 B 柱细缝（不是宽柱）。
* 侧标总成（P0 已移到 `regions/side.py` 的 `side_markers`，只在 `--front` 时启用）：L 上 x -1.22…-0.89 的亮黑刀片，前端琥珀 SideMarker，红色反光片，侧摄像头。
* 黑色轮拱内衬；碳纤门槛 / 侧裙（P0 已移到 `regions/side.py` 的 `build_skirt`，x 范围由 `ctx.HUBS` 推出：前轮心后 0.497 到后轮心前 0.510）。

**REAR**（r81、thrust、high、p017、p013 缝；展开参考 002 / 001 / 012 / 019）
* L11 尾翼：收起＝x 2.05→2.44 的整块车身色面板，与 R1d 的平尾板齐平，携带 L10 棱脊延续和尾唇顶面，俯视只见一条缝；
  展开＝在两根支柱上抬起并后移，翼尖外伸（比车身宽），端板下翻，原位露出黑色凹槽（GlossBlack）。
* 运行时：`src/car/index.js` 的收放（`meta.wing` 新格式）、去掉 `stow.dy = -0.130` 的临时补丁；lod2 没有单独的 `Wing` 节点 → lod2 固定为收起状态并在报告里说明。
* 尾灯带（TailLamp / BrakeLamp / ReverseLamp）、尾面分色、牌照、扩散器、喷口（与 `jets.js` 的坐标保持一致）、反光片、角鳍、摄像头座。

## 5. LOD 预算

总预算：lod1 ≤ 60k 三角形 / ≤ 20 draw call；lod2 ≤ 15k / ≤ 10；hi ≤ 450k。P0 后（默认参数）：lod1 57.2k / 18、lod2 8.4k / 7、hi 255.2k / 38；lod1 已经很紧。
构建日志的 `REGION BUDGET` 表和 `REPORT` 行里的 `regions` 给出按区域的明细（P0 的实测值，默认参数，不带 `--front`）。协调者据此给每个区域分配配额，写在「配额」列；超配额＝不合格。

* 三角形：区域自己的静态部件 + 它的节点（Wing、Thrusters）+ 它的贴花片。「SHELL」＝外壳车身（lod 为抽稀目标），「COMMON」＝其余所有（内饰 / 驾驶舱块、轮子、转向盘、门板和引擎盖贴花、旧的 `others`）。
* draw call：区域**新增**的 draw call ＝ 它的材质里没有被 Body 其余部分用到的那几种 ＋ 它自己节点的材质槽数。（碳纤、Trim 等被几个区域共用的材质不算新增。）所以各列不能直接相加；最后一行是真实总数。

| 区域 | hi 三角形 | lod1 三角形 | lod1 新增 draw call | lod1 配额 | lod2 三角形 | lod2 新增 draw call | lod2 配额 |
|---|---|---|---|---|---|---|---|
| SHELL（外壳车身） | 164,960 | 31,000 | （Paint Glass Trim） | | 5,196 | （同左） | |
| COMMON（内饰、轮子、转向盘、贴花…） | 77,994 | 19,698 | 10（含上面三种） | | 1,396 | 5（含上面三种） | |
| FRONT | 0 | 0 | 0 | | 0 | 0 | |
| SIDE | 1,652 | 300 | 0 | | 140 | 0 | |
| REAR | 10,634 | 6,194 | 8 | | 1,654 | 2 | |
| **合计（实测）** | **255,240 / 38 calls** | **57,192 / 18 calls** | | **≤ 60,000 / ≤ 20** | **8,386 / 7 calls** | | **≤ 15,000 / ≤ 10** |

加 `--front`（R2 前端 + 侧标，之前停在 R1c，默认关）时同一张表变成：FRONT hi 2,524 / lod1 1,080（+2 call）/ lod2 132（+1 call），SIDE hi 1,988 / lod1 380 / lod2 220，
合计 hi 258,866 / 42 calls、**lod1 58,350 / 20 calls（draw call 已顶满）**、lod2 8,600 / 8 calls。

**区域阶段起 R2 前端和侧标默认开启**（`--no-front` 为 P0 基准），所以默认构建就是上面这组数字。

**配额（2026-10-19，协调者；超配额＝不合格）**

| 区域 | hi 三角形 | lod1 三角形 | lod1 新增 draw call | lod2 三角形 | lod2 新增 draw call |
|---|---|---|---|---|---|
| FRONT | ≤ 40,000 | ≤ 1,800 | ≤ 2（HeadDRL、GlossBlack；HeadLens 在 lod1 并入其中之一或去掉） | ≤ 600 | ≤ 1 |
| SIDE | ≤ 30,000 | ≤ 800 | **0**（只能用 lod1 里已有的材质；新颜色在 lod1 用 `mat_of` 去掉或换成已有材质） | ≤ 400 | 0 |
| REAR | ≤ 80,000 | ≤ 6,600 | ≤ 8（不比现在多） | ≤ 2,500 | ≤ 2 |

合计上限：lod1 31,000 + 19,698 + 1,800 + 800 + 6,600 = 59,898 ≤ 60k，draw call 10 + 2 + 0 + 8 = 20；lod2 ≤ 10,092 / ≤ 8 call；hi ≤ 393k。
三个区域并行时，lod1 draw call 由协调者在集成时统一核算；区域代理只要不超过自己的「新增」配额。

## 6. 流程

1. **P0 拆分准备**（已完成 2026-10-19；一个代理，R1e 验收之后）：建 `regions/`（ctx、front/side/rear、`_base/` 快照），把 `front_parts`、`front.py` 的侧标部分、`build_skirt`、尾部整段（1924–2378 及尾面分色）原样迁进模块，
   去掉对全局 `SURF` 的隐式依赖（尾部常量 `FAS_LEAN`、`WING_STOW` 改为在 `build`/`meta` 里由 `ctx.surf` 计算），加 `--live`、`--out`、`car_meta` 只在 all 时写、按区域的预算明细。
   **验收＝等价性**：默认参数和 `--front` 两种构建，拆分前后每个对象、每种材质的三角形数和包围盒一致（`glb_compare.py`），锁定校验通过，npm test 通过。
   结果：默认、`--front`、`--oldbody` 三种构建拆分前后的每个对象 / 每种材质三角形数差 0、包围盒差 0.0000 mm、顶点质心差 0.0000 mm；`car_meta.json` 逐字节相同；锁定校验 18 块通过；npm test 通过。
   与原计划的两处差别：(a) `FAS_LEAN` 和 `WING_STOW` 由 `ctx.surf_hi`（hi 车身）算出，不是 `ctx.surf`——拆分前它们在模块加载时按 hi 车身算好，LOD 也用同样的值，这样才等价；(b) 增加了可选钩子 `decals`（车牌贴花片并入 Decals 节点）。
2. **并行**：FRONT / SIDE / REAR 三个新代理同时开工，各自小步快跑，按 §4 交付。
3. **集成**：协调者 `--live all` 构建到 `public/assets/car`，检查区域交界处的反射、全车对照表、预算、npm test、游戏内截图。
