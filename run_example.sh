#!/bin/bash

echo "Insta360 X4全景处理与RTMP推流示例"

# 显示帮助信息
echo
echo "这个脚本展示了几种常见的运行方式:"
echo
echo "选项:"
echo "1. 启动标准推流 (没有预览窗口)"
echo "2. 启动推流并显示预览窗口"
echo "3. 启动校准模式"
echo "4. 自定义设置"
echo "5. 退出"
echo

read -p "请选择操作 (1-5): " choice

if [ "$choice" = "1" ]; then
    echo "启动标准推流..."
    python3 main.py --rtmp_url rtmp://127.0.0.1:1935/live/livestream
elif [ "$choice" = "2" ]; then
    echo "启动推流并显示预览窗口..."
    python3 main.py --rtmp_url rtmp://127.0.0.1:1935/live/livestream --show_preview
elif [ "$choice" = "3" ]; then
    echo "启动校准模式..."
    python3 main.py --rtmp_url rtmp://127.0.0.1:1935/live/livestream --show_preview --calibrate
elif [ "$choice" = "4" ]; then
    echo "自定义设置..."
    read -p "输入相机索引 (默认0): " camera
    read -p "输入RTMP地址 (默认 rtmp://127.0.0.1:1935/live/livestream): " rtmp
    read -p "输入输出宽度 (默认 3840): " width
    read -p "输入输出高度 (默认 1920): " height
    read -p "输入帧率 (默认 30): " fps
    
    camera=${camera:-0}
    rtmp=${rtmp:-rtmp://127.0.0.1:1935/live/livestream}
    width=${width:-3840}
    height=${height:-1920}
    fps=${fps:-30}
    
    echo "启动自定义推流..."
    python3 main.py --camera $camera --rtmp_url $rtmp --width $width --height $height --fps $fps --show_preview
elif [ "$choice" = "5" ]; then
    echo "退出程序..."
    exit 0
else
    echo "无效的选择"
    exit 1
fi

read -p "按任意键继续..." -n 1 