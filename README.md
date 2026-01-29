# Insta360 X4 无线传输（双鱼眼拼接 + RTMP 低延迟推流）

该方案面向 Insta360 X4 WebCam 模式的实时全景传输：通过本地 Python 处理双鱼眼图像，生成等距柱面投影全景图（Equirectangular），并以低延迟参数通过 FFmpeg 推送至 RTMP 服务器（例如 SRS）。

## 功能概览

- 实时采集 Insta360 X4 WebCam 模式视频流
- 双鱼眼到全景投影的实时重映射
- 接缝融合、亮度均衡、色彩平衡（可开关）
- 低延迟 RTMP 推流（FFmpeg 管道）
- 交互式鱼眼参数校准与持久化

## 技术方案与数据流

1. 摄像头采集（OpenCV）
2. 双鱼眼 -> 全景投影映射（预计算映射表）
3. 接缝融合 + 图像增强（亮度/色彩可选）
4. FFmpeg 低延迟编码并推送 RTMP

核心模块：
- `Insta360Processor`：负责采集、映射、融合与增强
- `RTMPStreamer`：负责 FFmpeg 推流与帧队列

## 环境要求

- Python 3.6+（建议 3.9+）
- OpenCV 4.x（包含 contrib 版本可选）
- NumPy
- FFmpeg 可执行文件（需在 PATH 中可直接调用 `ffmpeg`）

## 安装

1. 克隆仓库
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

3. 安装 FFmpeg
   - Windows：从 https://ffmpeg.org/download.html 下载并加入系统 PATH
   - Linux：`sudo apt-get install ffmpeg`
   - macOS：`brew install ffmpeg`

## 快速开始

1. 将 Insta360 X4 连接电脑并切换为 WebCam 模式
2. 运行主程序
   ```bash
   python main.py --camera 0 --rtmp_url rtmp://127.0.0.1:1935/live/livestream
   ```
3. 需要本地预览时添加 `--show_preview`
   ```bash
   python main.py --camera 0 --rtmp_url rtmp://127.0.0.1:1935/live/livestream --show_preview
   ```

## 交互式校准（鱼眼参数）

校准模式会实时显示预览并允许微调鱼眼参数，退出后保存为 fisheye_params.json。

```bash
python main.py --camera 0 --rtmp_url rtmp://127.0.0.1:1935/live/livestream --show_preview --calibrate
```

键位说明：
- `a/d`：左镜头 `cx`
- `w/s`：左镜头 `cy`
- `z/x`：左镜头 `radius`
- `j/l`：右镜头 `cx`
- `i/k`：右镜头 `cy`
- `n/m`：右镜头 `radius`
- `q`：保存并退出

## 命令行参数

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--camera` | 摄像头索引 | 0 |
| `--rtmp_url` | RTMP 地址 | rtmp://127.0.0.1:1935/live/livestream |
| `--width` | 输出全景宽度 | 3840 |
| `--height` | 输出全景高度 | 1920 |
| `--fps` | 输出帧率 | 30 |
| `--show_preview` | 显示本地预览 | false |
| `--calibrate` | 启用参数校准 | false |
| `--no_brightness_eq` | 关闭亮度均衡 | false |
| `--no_color_balance` | 关闭色彩平衡 | false |
| `--overlap` | 接缝重叠宽度（像素） | 输出宽度的 10% |
| `--save_config` | 保存配置到 config.json | false |

## 配置文件

config.json 支持持久化常用设置（见 [config.json](config.json)）：

```json
{
  "camera": {"index": 0, "width": 1920, "height": 960, "fps": 30},
  "rtmp": {"url": "rtmp://127.0.0.1:1935/live/livestream", "width": 3840, "height": 1920, "fps": 30, "bitrate": "4000k"},
  "processing": {"brightness_equalization": true, "color_balance": true, "overlap_width_percent": 10}
}
```

运行时可通过 `--save_config` 将当前参数写入配置文件。

## 一键示例脚本

- Windows：运行 [run_example.bat](run_example.bat)
- Linux/macOS：运行 [run_example.sh](run_example.sh)

## 使用 SRS 作为 RTMP 服务器（可选）

SRS 示例：
```bash
git clone https://github.com/ossrs/srs.git
cd srs/trunk
./configure && make
./objs/srs -c conf/srs.conf
```

常用播放地址：
- RTMP：`rtmp://<server-ip>:1935/live/livestream`
- HTTP-FLV：`http://<server-ip>:8080/live/stream.flv`
- HLS：`http://<server-ip>:8080/live/stream.m3u8`

## 项目结构

- 主入口：[main.py](main.py)
- 全景处理器：[insta360_processor.py](insta360_processor.py)
- 推流模块：[rtmp_streamer.py](rtmp_streamer.py)
- 高级图像处理：[advanced_processing.py](advanced_processing.py)

## 常见问题

1. 无法打开相机设备
   - 确认 X4 已进入 WebCam 模式
   - 尝试不同设备索引：`--camera 1`、`--camera 2`

2. 推流失败或黑屏
   - 确认系统可直接运行 `ffmpeg`
   - 检查 RTMP 地址与服务器端口
   - 防火墙需放行 1935/8080

3. 拼接接缝明显或亮度不均
   - 使用 `--calibrate` 调整鱼眼参数
   - 适当增大 `--overlap`
   - 关闭自动曝光或稳定相机位置

## 后续计划（可选）

- GUI 参数调节界面
- 更高阶拼接与融合策略
- 多种投影格式输出（立方体贴图等）
- 传输加密与鉴权

## 许可

MIT License