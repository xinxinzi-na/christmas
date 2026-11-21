# 霜夜星愿 · Merry Christmas

一棵可以送给某个人的冰晶圣诞树。开场时，蓝白粒子从四面八方聚拢，沿着枝条由下向上结成树冠。银色灯带绕树点亮，树顶的五角星向外送出一圈光波。最后，*Merry Christmas* 和你的专属署名渐渐浮现，树在极光和落雪中缓缓旋转。

[冰雪版](./christmas_tree.py) 用 Python、Pygame 和 NumPy 在独立桌面窗口绘制。默认画布为 **1080 × 1920**，适合竖屏录制。枝叶、水晶球、星空和辉光都由程序生成。

## 在 Ubuntu 上运行

准备好 Python 3 和图形桌面后，打开终端运行以下命令。

```bash
git clone https://github.com/xinxinzi-na/christmas.git
cd christmas
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "pygame>=2.5,<3" "numpy>=1.24"
python christmas_tree.py
```

如果创建虚拟环境时提示缺少 `venv`，先运行 `sudo apt install python3-venv`。下次启动时，在仓库目录执行 `source .venv/bin/activate` 和 `python christmas_tree.py` 即可。

## 写给谁

打开 [christmas_tree.py](./christmas_tree.py)，搜索 `class IceLettering`。在这个类里找到 `name = ...`，把引号里的文字换成自己的署名，例如：

```python
name = "小雪"
```

名字会出现在标题和五角星之间。默认署名是淡蓝色。想换成樱花粉，在同一处找到 `self.name = font.render(...)`，把这一行改为：

```python
self.name = font.render(name, True, (255, 182, 213))
```

保存脚本并重新启动后即可看到效果。如果中文名字显示为方框，可以在 Ubuntu 上安装中文字体包 `fonts-noto-cjk`，再重启程序。

## 播放与录制

| 按键 | 功能 |
| --- | --- |
| 空格 | 从头重播粒子汇聚、星顶光波和题字淡入的开场 |
| F11 | 切换全屏与窗口模式 |
| Esc | 退出 |

录制完整开场时，可以先按 **F11** 选好显示模式，开始录屏后再按**空格**。窗口会根据桌面大小等比预览；若要录下完整的 1080 × 1920 像素，可在同分辨率的竖屏桌面上全屏播放。

```bash
python christmas_tree.py --fullscreen           # 直接全屏启动
python christmas_tree.py --size 720x1280       # 以较低分辨率渲染
python christmas_tree.py --benchmark 15        # 播放 15 秒，输出平均 FPS 和 P95 帧间隔
```

## 另一种配色

仓库还附带一个使用红、绿、金色粒子的 [经典版](./tree.py)。激活同一个虚拟环境后，运行 `python tree.py` 即可打开。
