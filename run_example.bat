@echo off
echo Insta360 X4全景处理与RTMP推流示例

REM 显示帮助信息
echo.
echo 这个批处理文件展示了几种常见的运行方式:
echo.
echo 选项:
echo 1. 启动标准推流 (没有预览窗口)
echo 2. 启动推流并显示预览窗口
echo 3. 启动校准模式
echo 4. 自定义设置
echo 5. 退出
echo.

set /p choice=请选择操作 (1-5): 

if "%choice%"=="1" (
    echo 启动标准推流...
    python main.py --rtmp_url rtmp://127.0.0.1:1935/live/livestream
) else if "%choice%"=="2" (
    echo 启动推流并显示预览窗口...
    python main.py --rtmp_url rtmp://127.0.0.1:1935/live/livestream --show_preview
) else if "%choice%"=="3" (
    echo 启动校准模式...
    python main.py --rtmp_url rtmp://127.0.0.1:1935/live/livestream --show_preview --calibrate
) else if "%choice%"=="4" (
    echo 自定义设置...
    set /p camera=输入相机索引 (默认0): 
    set /p rtmp=输入RTMP地址 (默认 rtmp://127.0.0.1:1935/live/livestream): 
    set /p width=输入输出宽度 (默认 3840): 
    set /p height=输入输出高度 (默认 1920): 
    set /p fps=输入帧率 (默认 30): 
    
    if "%camera%"=="" set camera=0
    if "%rtmp%"=="" set rtmp=rtmp://127.0.0.1:1935/live/livestream
    if "%width%"=="" set width=3840
    if "%height%"=="" set height=1920
    if "%fps%"=="" set fps=30
    
    echo 启动自定义推流...
    python main.py --camera %camera% --rtmp_url %rtmp% --width %width% --height %height% --fps %fps% --show_preview
) else if "%choice%"=="5" (
    echo 退出程序...
    exit /b 0
) else (
    echo 无效的选择
    exit /b 1
)

pause 