import cv2
import time
import subprocess
import threading
import numpy as np
from queue import Queue


class RTMPStreamer:
    """
    将视频帧推送到RTMP服务器
    """
    
    def __init__(self, rtmp_url, width=3840, height=1920, fps=30, bitrate='4000k'):
        """
        初始化RTMP推流器
        
        参数:
            rtmp_url: RTMP服务器URL
            width: 视频宽度
            height: 视频高度
            fps: 帧率
            bitrate: 码率
        """
        self.rtmp_url = rtmp_url
        self.width = width
        self.height = height
        self.fps = fps
        self.bitrate = bitrate
        
        self.running = False
        self.frame_queue = Queue(maxsize=10)  # 保持小的队列以减少延迟
        self.process = None
        self.thread = None
        
    def start(self):
        """启动推流线程"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._stream_loop)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """停止推流"""
        self.running = False
        
        if self.thread is not None:
            self.thread.join(timeout=1.0)
            
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            
        # 清空帧队列
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                pass
                
    def push_frame(self, frame):
        """
        将视频帧添加到队列
        
        参数:
            frame: OpenCV/Numpy格式的视频帧
        """
        if not self.running:
            return False
        
        # 调整大小以匹配输出分辨率
        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            frame = cv2.resize(frame, (self.width, self.height))
            
        # 尝试添加到队列，如果队列已满则丢弃最旧的帧
        if self.frame_queue.full():
            try:
                self.frame_queue.get_nowait()
            except:
                pass
                
        try:
            self.frame_queue.put_nowait(frame)
            return True
        except:
            return False
    
    def _stream_loop(self):
        """推流处理循环"""
        # 创建FFMPEG命令
        command = [
            'ffmpeg',
            '-y',  # 覆盖输出文件
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',  # OpenCV使用BGR颜色空间
            '-s', '{}x{}'.format(self.width, self.height),
            '-r', str(self.fps),
            '-i', '-',  # 从标准输入读取
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',  # 兼容性好的像素格式
            '-preset', 'ultrafast', # 最快的编码速度
            '-tune', 'zerolatency', # 低延迟
            '-b:v', self.bitrate,
            '-f', 'flv',  # RTMP需要FLV格式
            self.rtmp_url
        ]
        
        # 启动FFMPEG进程
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        frame_time = 1.0 / self.fps
        next_frame_time = time.time()
        
        try:
            while self.running and self.process.poll() is None:
                if self.frame_queue.empty():
                    # 没有新的帧，等待一小段时间
                    time.sleep(0.001)
                    continue
                    
                # 获取下一帧
                frame = self.frame_queue.get()
                
                # 计算需要等待的时间，保持帧率稳定
                current_time = time.time()
                wait_time = max(0, next_frame_time - current_time)
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # 更新下一帧的时间戳
                next_frame_time = max(time.time(), next_frame_time + frame_time)
                
                # 将帧写入FFMPEG进程
                self.process.stdin.write(frame.tobytes())
                
        except (BrokenPipeError, IOError) as e:
            print("推流出错: {}".format(e))
        except Exception as e:
            print("推流过程中发生错误: {}".format(e))
        finally:
            # 关闭FFMPEG进程
            if self.process.poll() is None:
                try:
                    self.process.stdin.close()
                    self.process.wait(timeout=2.0)
                except:
                    self.process.kill()
            
            self.process = None
