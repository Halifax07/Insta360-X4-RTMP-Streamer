import cv2
import numpy as np
import time
import threading
import json
import os
from advanced_processing import equalize_brightness, color_balance


class Insta360Processor:
    """
    处理Insta360 X4相机的WebCam模式视频流
    将双鱼眼图像拼接为全景图像
    """
    def __init__(self, camera_index=0, output_width=3840, output_height=1920):
        """
        初始化处理器
        
        参数:
            camera_index: 相机设备索引，默认为0
            output_width: 输出全景图宽度
            output_height: 输出全景图高度
        """
        self.camera_index = camera_index
        self.output_width = output_width
        self.output_height = output_height
        self.cap = None
        self.running = False
        self.frame = None
        self.processed_frame = None
        self.lock = threading.Lock()
        
        # 尝试从文件加载鱼眼镜头参数
        self.fisheye_params = self._load_fisheye_params()
        if self.fisheye_params is None:
            # 鱼眼镜头参数，可能需要根据实际情况调整
            self.fisheye_params = {
                'left': {
                    'cx': 0.0,  # 中心点x坐标（归一化）
                    'cy': 0.5,  # 中心点y坐标（归一化）
                    'radius': 0.48,  # 半径（归一化）
                    'offset_angle': 0.0,  # 角度偏移（弧度）
                },
                'right': {
                    'cx': 1.0,  # 中心点x坐标（归一化）
                    'cy': 0.5,  # 中心点y坐标（归一化）
                    'radius': 0.48,  # 半径（归一化）
                    'offset_angle': 0.0,  # 角度偏移（弧度）
                }
            }
        
        # 计算映射表（在第一帧时初始化）
        self.map_x = None
        self.map_y = None
        
        # 高级处理选项
        self.use_brightness_equalization = True
        self.use_color_balance = True
        self.overlap_width = int(self.output_width * 0.1)  # 重叠区域宽度，默认为总宽度的10%
    
    def _load_fisheye_params(self):
        """从文件加载鱼眼参数"""
        try:
            if os.path.exists('fisheye_params.json'):
                with open('fisheye_params.json', 'r') as f:
                    params = json.load(f)
                print("已从文件加载鱼眼参数")
                return params
        except Exception as e:
            print("加载鱼眼参数失败: {}".format(e))
        return None
    
    def start(self):
        """启动视频捕获线程"""
        if self.running:
            return
            
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            raise ValueError("无法打开相机设备 {}".format(self.camera_index))
        
        # 设置捕获分辨率（根据Insta360 X4的WebCam模式实际输出调整）
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # 实际可能不同
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 960)  # 实际可能不同
        
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        """停止视频捕获线程"""
        self.running = False
        if self.thread is not None:
            self.thread.join()
        if self.cap is not None:
            self.cap.release()
    
    def _capture_loop(self):
        """视频捕获循环"""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("无法读取视频帧")
                time.sleep(0.1)
                continue
                
            # 处理帧
            processed = self.process_frame(frame)
            
            # 更新当前帧
            with self.lock:
                self.frame = frame
                self.processed_frame = processed
    
    def _init_mapping_table(self, frame_shape):
        """
        初始化从双鱼眼图像到等距柱面投影的映射表
        """
        height, width = frame_shape[:2]
        print("原始帧尺寸: {}x{}".format(width, height))
        
        # 创建等距柱面投影的映射表
        map_x = np.zeros((self.output_height, self.output_width), dtype=np.float32)
        map_y = np.zeros((self.output_height, self.output_width), dtype=np.float32)
        
        # 计算每个像素的映射关系
        for y in range(self.output_height):
            for x in range(self.output_width):
                # 等距柱面投影中的角度
                theta = 2 * np.pi * x / self.output_width - np.pi  # 水平角度：-pi到pi
                phi = np.pi * y / self.output_height - np.pi/2     # 垂直角度：-pi/2到pi/2
                
                # 3D球面坐标
                x_3d = np.cos(phi) * np.cos(theta)
                y_3d = np.cos(phi) * np.sin(theta)
                z_3d = np.sin(phi)
                
                # 确定使用哪个鱼眼镜头
                if -np.pi/2 <= theta <= np.pi/2:  # 使用右镜头 (-90° 到 90°)
                    params = self.fisheye_params['right']
                else:  # 使用左镜头 (90° 到 270°)
                    params = self.fisheye_params['left']
                
                # 将3D点投影到鱼眼镜头平面
                r = np.sqrt(x_3d*x_3d + z_3d*z_3d)
                if r == 0:  # 避免除以零
                    continue
                    
                # 鱼眼投影：与视角成正比的径向距离
                theta_fisheye = np.arctan2(y_3d, x_3d)
                rho_fisheye = np.arccos(z_3d / np.sqrt(x_3d*x_3d + y_3d*y_3d + z_3d*z_3d)) / np.pi
                
                # 加上角度偏移
                theta_fisheye += params['offset_angle']
                
                # 转换到图像坐标
                x_fisheye = params['cx'] * width + params['radius'] * width * rho_fisheye * np.cos(theta_fisheye)
                y_fisheye = params['cy'] * height + params['radius'] * height * rho_fisheye * np.sin(theta_fisheye)
                
                # 确保坐标在图像内
                if 0 <= x_fisheye < width and 0 <= y_fisheye < height:
                    map_x[y, x] = x_fisheye
                    map_y[y, x] = y_fisheye
        
        return map_x, map_y
    
    def _blend_seam(self, panorama):
        """
        使用高级融合技术处理接缝区域
        
        参数:
            panorama: 初步拼接的全景图
            
        返回:
            处理后的全景图
        """
        half_width = self.output_width // 2
        
        # 接缝区域的中心位置
        left_seam_center = 0  # 0度(左边缘)
        right_seam_center = half_width  # 180度
        
        # 处理左侧接缝 (0度)
        left_overlap = self.overlap_width // 2
        left_region1 = panorama[:, -left_overlap:].copy()
        left_region2 = panorama[:, :left_overlap].copy()
        
        # 创建渐变权重
        h, w = left_region1.shape[:2]
        weight = np.zeros((h, left_overlap*2), dtype=np.float32)
        for i in range(left_overlap*2):
            weight[:, i] = i / (left_overlap*2)
        
        # 将权重扩展到3通道
        weight = np.expand_dims(weight, axis=2)
        weight = np.repeat(weight, 3, axis=2)
        
        # 融合左侧接缝
        combined_left = np.concatenate((left_region1, left_region2), axis=1)
        blended_left = left_region1 * (1 - weight[:, :left_overlap]) + left_region2 * weight[:, left_overlap:]
        
        # 处理右侧接缝 (180度)
        right_overlap = self.overlap_width // 2
        right_seam_start = right_seam_center - right_overlap
        right_seam_end = right_seam_center + right_overlap
        
        right_region1 = panorama[:, right_seam_start:right_seam_center].copy()
        right_region2 = panorama[:, right_seam_center:right_seam_end].copy()
        
        # 创建渐变权重
        h, w = right_region1.shape[:2]
        weight = np.zeros((h, right_overlap*2), dtype=np.float32)
        for i in range(right_overlap*2):
            weight[:, i] = i / (right_overlap*2)
        
        # 将权重扩展到3通道
        weight = np.expand_dims(weight, axis=2)
        weight = np.repeat(weight, 3, axis=2)
        
        # 融合右侧接缝
        blended_right = right_region1 * (1 - weight[:, :right_overlap]) + right_region2 * weight[:, right_overlap:]
        
        # 应用融合结果到全景图
        result = panorama.copy()
        result[:, -left_overlap:] = blended_left[:, :left_overlap]
        result[:, :left_overlap] = blended_left[:, left_overlap:]
        result[:, right_seam_start:right_seam_end] = np.concatenate((blended_right[:, :right_overlap], blended_right[:, right_overlap:]), axis=1)
        
        return result
        
    def process_frame(self, frame):
        """
        处理视频帧：将双鱼眼图像转换为等距柱面投影的全景图
        """
        if frame is None:
            return None
            
        # 首次处理帧时初始化映射表
        if self.map_x is None or self.map_y is None:
            print("初始化映射表...")
            self.map_x, self.map_y = self._init_mapping_table(frame.shape)
        
        # 使用OpenCV的重映射函数进行投影变换
        panorama = cv2.remap(frame, self.map_x, self.map_y, 
                           interpolation=cv2.INTER_LINEAR, 
                           borderMode=cv2.BORDER_CONSTANT)
        
        # 处理接缝，提高拼接质量
        panorama = self._blend_seam(panorama)
        
        # 亮度均衡处理（可选）
        if self.use_brightness_equalization:
            panorama = equalize_brightness(panorama)
            
        # 色彩平衡（可选）
        if self.use_color_balance:
            panorama = color_balance(panorama)
        
        return panorama
    
    def get_processed_frame(self):
        """获取处理后的帧"""
        with self.lock:
            if self.processed_frame is None:
                return None
            return self.processed_frame.copy()
    
    def get_original_frame(self):
        """获取原始帧"""
        with self.lock:
            if self.frame is None:
                return None
            return self.frame.copy()
            
    def set_processing_options(self, brightness_eq=True, color_bal=True, overlap_width=None):
        """设置处理选项
        
        参数:
            brightness_eq: 是否启用亮度均衡
            color_bal: 是否启用色彩平衡
            overlap_width: 重叠区域宽度（像素）
        """
        self.use_brightness_equalization = brightness_eq
        self.use_color_balance = color_bal
        
        if overlap_width is not None:
            self.overlap_width = overlap_width 