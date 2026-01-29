import cv2
import time
import argparse
import numpy as np
import json
import os
from insta360_processor import Insta360Processor
from rtmp_streamer import RTMPStreamer


def load_config(config_file='config.json'):
    """
    加载配置文件
    
    参数:
        config_file: 配置文件路径
        
    返回:
        配置字典
    """
    default_config = {
        "camera": {
            "index": 0,
            "width": 1920,
            "height": 960,
            "fps": 30
        },
        "rtmp": {
            "url": "rtmp://127.0.0.1:1935/live/livestream",
            "width": 3840,
            "height": 1920,
            "fps": 30,
            "bitrate": "4000k"
        },
        "processing": {
            "brightness_equalization": True,
            "color_balance": True,
            "overlap_width_percent": 10
        }
    }
    
    # 尝试加载配置文件
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                print(f"已从 {config_file} 加载配置")
                return config
        except Exception as e:
            print("加载配置文件失败: {}".format(e))
    
    # 如果无法加载，使用默认配置
    print("使用默认配置")
    return default_config


def main():
    # 加载配置
    config = load_config()
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Insta360 X4 WebCam处理和RTMP推流')
    parser.add_argument('--camera', type=int, default=config['camera']['index'], 
                       help='摄像头索引 (默认: {})'.format(config['camera']['index']))
    parser.add_argument('--rtmp_url', type=str, default=config['rtmp']['url'],
                       help='RTMP服务器URL (默认: {})'.format(config['rtmp']['url']))
    parser.add_argument('--width', type=int, default=config['rtmp']['width'], 
                       help='输出视频宽度 (默认: {})'.format(config['rtmp']['width']))
    parser.add_argument('--height', type=int, default=config['rtmp']['height'], 
                       help='输出视频高度 (默认: {})'.format(config['rtmp']['height']))
    parser.add_argument('--fps', type=int, default=config['rtmp']['fps'],
                       help='输出视频帧率 (默认: {})'.format(config['rtmp']['fps']))
    parser.add_argument('--show_preview', action='store_true',
                       help='显示预览窗口')
    parser.add_argument('--calibrate', action='store_true',
                       help='启用鱼眼镜头参数校准模式')
    parser.add_argument('--no_brightness_eq', action='store_false',
                       dest='brightness_eq', default=config['processing']['brightness_equalization'],
                       help='禁用亮度均衡')
    parser.add_argument('--no_color_balance', action='store_false',
                       dest='color_balance', default=config['processing']['color_balance'],
                       help='禁用色彩平衡')
    parser.add_argument('--overlap', type=int,
                       default=int(config['rtmp']['width'] * config['processing']['overlap_width_percent'] / 100),
                       help='重叠区域宽度 (默认: 输出宽度的{}%)'.format(config['processing']['overlap_width_percent']))
    parser.add_argument('--save_config', action='store_true',
                       help='保存当前参数为配置文件')
    args = parser.parse_args()
    
    # 如果需要保存配置
    if args.save_config:
        save_config = {
            "camera": {
                "index": args.camera,
                "width": config['camera']['width'],
                "height": config['camera']['height'],
                "fps": config['camera']['fps']
            },
            "rtmp": {
                "url": args.rtmp_url,
                "width": args.width,
                "height": args.height,
                "fps": args.fps,
                "bitrate": config['rtmp']['bitrate']
            },
            "processing": {
                "brightness_equalization": args.brightness_eq,
                "color_balance": args.color_balance,
                "overlap_width_percent": int(args.overlap * 100 / args.width)
            }
        }
        
        try:
            with open('config.json', 'w') as f:
                json.dump(save_config, f, indent=4)
            print("配置已保存至 config.json")
        except Exception as e:
            print("保存配置失败: {}".format(e))
    
    print("初始化Insta360处理器...")
    # 创建视频处理器
    processor = Insta360Processor(
        camera_index=args.camera,
        output_width=args.width,
        output_height=args.height
    )
    
    # 设置处理选项
    processor.set_processing_options(
        brightness_eq=args.brightness_eq,
        color_bal=args.color_balance,
        overlap_width=args.overlap
    )
    
    print("初始化RTMP推流器...")
    # 创建RTMP推流器
    streamer = RTMPStreamer(
        rtmp_url=args.rtmp_url,
        width=args.width,
        height=args.height,
        fps=args.fps
    )
    
    # 启动视频处理线程和推流线程
    try:
        processor.start()
        print("视频处理器已启动")
        
        time.sleep(2)  # 等待视频处理器初始化
        
        streamer.start()
        print("RTMP推流器已启动")
        print("推流地址: {}".format(args.rtmp_url))
        
        if args.calibrate:
            # 进入校准模式，调整鱼眼参数
            calibrate_fisheye_params(processor)
        
        # 主循环
        while True:
            # 获取处理后的帧
            processed_frame = processor.get_processed_frame()
            if processed_frame is None:
                time.sleep(0.01)
                continue
            
            # 推送到RTMP流
            streamer.push_frame(processed_frame)
            
            # 显示预览 (如果需要)
            if args.show_preview:
                # 调整大小以便显示
                preview_frame = cv2.resize(processed_frame, (1280, 640))
                cv2.imshow('Insta360 X4 全景预览', preview_frame)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
            
            time.sleep(1.0 / args.fps)
            
    except KeyboardInterrupt:
        print("接收到中断信号，正在停止...")
    except Exception as e:
        print("发生错误: {}".format(e))
    finally:
        # 停止处理和推流
        processor.stop()
        streamer.stop()
        
        if args.show_preview:
            cv2.destroyAllWindows()
            
        print("程序已退出")


def calibrate_fisheye_params(processor):
    """
    交互式校准鱼眼参数
    
    参数:
        processor: Insta360Processor实例
    """
    print("\n---- 鱼眼参数校准模式 ----")
    print("使用键盘调整左右鱼眼镜头的参数:")
    print("a/d - 调整左镜头 cx")
    print("w/s - 调整左镜头 cy")
    print("z/x - 调整左镜头半径")
    print("j/l - 调整右镜头 cx")
    print("i/k - 调整右镜头 cy")
    print("n/m - 调整右镜头半径")
    print("q - 退出校准模式并保存")
    print("--------------------------")
    
    adjustment_step = 0.01
    
    while True:
        # 获取处理后的帧
        frame = processor.get_processed_frame()
        if frame is None:
            time.sleep(0.01)
            continue
        
        # 调整大小以便显示
        preview_frame = cv2.resize(frame, (1280, 640))
        
        # 显示当前参数
        params_text = "左镜头: cx={:.2f}, cy={:.2f}, r={:.2f} | 右镜头: cx={:.2f}, cy={:.2f}, r={:.2f}".format(
            processor.fisheye_params['left']['cx'],
            processor.fisheye_params['left']['cy'],
            processor.fisheye_params['left']['radius'],
            processor.fisheye_params['right']['cx'],
            processor.fisheye_params['right']['cy'],
            processor.fisheye_params['right']['radius']
        )
        
        cv2.putText(preview_frame, params_text, (10, 30), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow('鱼眼参数校准', preview_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        # 根据按键调整参数
        if key == ord('a'):  # 减少左镜头 cx
            processor.fisheye_params['left']['cx'] -= adjustment_step
            processor.map_x, processor.map_y = None, None  # 重新计算映射表
        elif key == ord('d'):  # 增加左镜头 cx
            processor.fisheye_params['left']['cx'] += adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('w'):  # 减少左镜头 cy
            processor.fisheye_params['left']['cy'] -= adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('s'):  # 增加左镜头 cy
            processor.fisheye_params['left']['cy'] += adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('z'):  # 减少左镜头半径
            processor.fisheye_params['left']['radius'] -= adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('x'):  # 增加左镜头半径
            processor.fisheye_params['left']['radius'] += adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('j'):  # 减少右镜头 cx
            processor.fisheye_params['right']['cx'] -= adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('l'):  # 增加右镜头 cx
            processor.fisheye_params['right']['cx'] += adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('i'):  # 减少右镜头 cy
            processor.fisheye_params['right']['cy'] -= adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('k'):  # 增加右镜头 cy
            processor.fisheye_params['right']['cy'] += adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('n'):  # 减少右镜头半径
            processor.fisheye_params['right']['radius'] -= adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('m'):  # 增加右镜头半径
            processor.fisheye_params['right']['radius'] += adjustment_step
            processor.map_x, processor.map_y = None, None
        elif key == ord('q'):  # 退出校准模式
            break
    
    cv2.destroyWindow('鱼眼参数校准')
    
    # 保存参数到文件
    try:
        import json
        with open('fisheye_params.json', 'w') as f:
            json.dump(processor.fisheye_params, f, indent=4)
        print("鱼眼参数已保存到 fisheye_params.json")
    except Exception as e:
        print("保存参数时出错: {}".format(e))


if __name__ == "__main__":
    main() 