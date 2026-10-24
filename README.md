# Roadster Race · 霓虹环线 NEON LOOP

一个用 three.js 做的夜间街头赛车游戏。主角车是 2026 款 Roadster 的复刻模型，完全由 Blender 脚本程序化生成，每一处造型都对照官方照片逐项拟合。

## 目录

| 路径 | 内容 |
|---|---|
| `neon_loop/` | 游戏本体：three.js r186 + Vite |
| `neon_loop/src/` | 游戏、场景（含展厅模式 `?scene=showroom`）、车辆材质 |
| `neon_loop/public/assets/car/` | 构建好的车模：hi / lod1 / lod2，各有压缩版和 `.raw.glb` |
| `neon_loop/tools/blender/` | 车模生成管线：`build_game_car.py`、曲面 `design2.py` / `shell2.py` / `curves2.py`、检查 `check.py` |
| `neon_loop/tools/*.mjs` | 浏览器测试和截图（Playwright） |
| `refs/` | 参考照片。代号、机位和用途见 `neon_loop/tools/blender/REFS.md` |
| `wip/c11b-h5/` | 未合并的前轮肩部改动，见其中的 README |
| `cloud-setup.sh` | Linux / 云端环境一键安装 |

建模规则和历史记录：

- `neon_loop/tools/blender/SPEC.md`：造型规格，包括每条棱、每个面的读图结论和用户裁决；
- `HISTORY.md`：每轮改了什么、为什么；
- `AGENT_GUIDE.md`：建模代理的工作方式。

## 运行游戏

```bash
cd neon_loop
npm ci
npm run dev        # http://127.0.0.1:5180 ，展厅：/?scene=showroom
npm test
```

## 重建车模

需要 Blender 5.2，路径由 `$BLENDER` 指定。macOS 默认用 `/Applications/Blender.app/Contents/MacOS/Blender`。

```bash
cd neon_loop
$BLENDER -b --python tools/blender/build_game_car.py -- --only all
$BLENDER -b --python tools/blender/build_game_car.py -- --only all --raw
python3 tools/blender/check.py lock      # 还有 budget / plan / dihedral / nose / masks / fender
```

对照照片渲染：

```bash
$BLENDER -b --python tools/blender/render_ref_views.py -- --glb public/assets/car/car_hi.raw.glb --out <dir> --views p016,p005,p013,p014,p018,p003 --samples 64 --glass-dark
```

浏览器检查脚本都要先启动 dev server：

```bash
node tools/wingtest.mjs <out>
node tools/carshots.mjs <out>
node tools/shot_route.mjs --scene showroom ...
```

浏览器默认取 `$CHROME`。没设置时，macOS 用 Google Chrome，Linux 用 Playwright 自带的 Chromium（见 `tools/chrome.mjs`）。

## 云端 / Linux

```bash
bash cloud-setup.sh
export BLENDER="$HOME/blender/blender"
export LD_LIBRARY_PATH="$HOME/blender/lib"   # 压缩导出（meshopt）要用 Blender 自带的 libmeshoptimizer.so
```

这个脚本会安装 Blender 5.2、npm 依赖、Chromium 和 numpy。云环境的网络权限需要放行 download.blender.org、npm、Playwright CDN 和 PyPI。容器里没有 GPU，Cycles 用 CPU 渲染，会慢一些。

## 当前状态（2026-10-22）

- 主线车模是 c10b 车身加 q8 车头，外加 q12 / q12b 光顺：尾肩面、上面波纹、溜背、车顶边梁和玻璃边、窗下折带，以及合并后的 h5 前轮肩部（门缝前凹谷已处理）。细节见 `neon_loop/tools/blender/HISTORY.md`。
- `wip/c11b-h5/` 已合并进主线，只作存档。
