import cv2
import numpy as np


def optimize_seams(left_img, right_img, overlap_width):
    """
    优化两个重叠图像的接缝
    
    参数:
        left_img: 左侧图像
        right_img: 右侧图像
        overlap_width: 重叠区域宽度
        
    返回:
        融合后的图像
    """
    # 提取重叠区域
    h, w = left_img.shape[:2]
    left_overlap = left_img[:, -overlap_width:]
    right_overlap = right_img[:, :overlap_width]
    
    # 创建权重矩阵进行线性过渡
    weight = np.zeros((h, overlap_width), dtype=np.float32)
    for i in range(overlap_width):
        weight[:, i] = (overlap_width - i) / overlap_width
    
    # 应用权重进行融合
    blended_overlap = (left_overlap * weight[:, :, np.newaxis] + 
                       right_overlap * (1 - weight[:, :, np.newaxis]))
    
    # 合并左侧、融合区域和右侧
    result = np.zeros((h, w*2-overlap_width, 3), dtype=np.uint8)
    result[:, :w-overlap_width] = left_img[:, :w-overlap_width]
    result[:, w-overlap_width:w] = blended_overlap
    result[:, w:] = right_img[:, overlap_width:]
    
    return result


def equalize_brightness(img):
    """
    平衡图像亮度
    
    参数:
        img: 输入图像
        
    返回:
        亮度均衡后的图像
    """
    # 转换到LAB颜色空间
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # 对亮度通道应用自适应直方图均衡
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    
    # 合并通道
    limg = cv2.merge((cl, a, b))
    
    # 转换回BGR颜色空间
    equalized = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    
    return equalized


def multi_band_blending(img1, img2, mask, levels=4):
    """
    多频段融合算法
    
    参数:
        img1: 第一张图像
        img2: 第二张图像
        mask: 融合掩码 (0表示使用img1, 1表示使用img2)
        levels: 分解层数
        
    返回:
        融合后的图像
    """
    # 确保输入图像是浮点型
    img1 = img1.astype(np.float32) / 255.0
    img2 = img2.astype(np.float32) / 255.0
    
    # 创建拉普拉斯金字塔
    def build_laplacian_pyramid(img, levels):
        pyramid = [img]
        for i in range(levels):
            # 高斯滤波
            current = pyramid[0]
            blurred = cv2.GaussianBlur(current, (5, 5), 0)
            # 下采样
            downsampled = cv2.resize(blurred, (blurred.shape[1] // 2, blurred.shape[0] // 2))
            # 上采样
            upsampled = cv2.resize(downsampled, (current.shape[1], current.shape[0]))
            # 计算拉普拉斯差值
            laplacian = current - upsampled
            # 更新金字塔
            pyramid[0] = downsampled
            pyramid.append(laplacian)
        return pyramid
    
    # 构建拉普拉斯金字塔
    lap1 = build_laplacian_pyramid(img1, levels)
    lap2 = build_laplacian_pyramid(img2, levels)
    
    # 构建掩码的高斯金字塔
    mask_pyramid = [mask]
    mask_float = mask.astype(np.float32) / 255.0
    for i in range(levels):
        mask_float = cv2.resize(cv2.GaussianBlur(mask_float, (5, 5), 0), 
                               (mask_float.shape[1] // 2, mask_float.shape[0] // 2))
        mask_pyramid.append(mask_float)
    
    # 融合金字塔
    blended_pyramid = []
    for i, (l1, l2, m) in enumerate(zip(lap1, lap2, mask_pyramid)):
        if i == 0:  # 基础图像级别
            blended = l1 * (1.0 - m) + l2 * m
        else:  # 拉普拉斯级别
            m_expanded = np.expand_dims(m, axis=2) if m.ndim == 2 else m
            blended = l1 * (1.0 - m_expanded) + l2 * m_expanded
        blended_pyramid.append(blended)
    
    # 重建融合图像
    result = blended_pyramid[0]
    for i in range(levels):
        result = cv2.resize(result, (blended_pyramid[i+1].shape[1], blended_pyramid[i+1].shape[0]))
        result += blended_pyramid[i+1]
    
    # 剪裁并转换回8位
    result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
    return result


def detect_and_match_features(img1, img2, method='sift'):
    """
    检测并匹配两个图像中的特征点
    
    参数:
        img1: 第一张图像
        img2: 第二张图像
        method: 特征检测方法 ('sift', 'orb', 'akaze')
        
    返回:
        (good_matches, kp1, kp2): 匹配点和特征点
    """
    # 转换为灰度图像
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if len(img1.shape) == 3 else img1
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if len(img2.shape) == 3 else img2
    
    # 选择特征检测器和描述符
    if method.lower() == 'sift':
        detector = cv2.SIFT_create()
    elif method.lower() == 'orb':
        detector = cv2.ORB_create(nfeatures=5000)
    elif method.lower() == 'akaze':
        detector = cv2.AKAZE_create()
    else:
        raise ValueError("不支持的特征检测方法: {}".format(method))
    
    # 检测特征点和描述符
    kp1, des1 = detector.detectAndCompute(gray1, None)
    kp2, des2 = detector.detectAndCompute(gray2, None)
    
    if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
        return [], [], []
    
    # 特征匹配
    if method.lower() == 'sift' or method.lower() == 'akaze':
        matcher = cv2.BFMatcher(cv2.NORM_L2)
    else:  # ORB使用汉明距离
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    
    # 获取k个最佳匹配
    matches = matcher.knnMatch(des1, des2, k=2)
    
    # 应用Lowe过滤
    good_matches = []
    for m, n in matches:
        if m.distance < 0.75 * n.distance:
            good_matches.append(m)
    
    return good_matches, kp1, kp2


def find_homography(kp1, kp2, good_matches):
    """
    使用匹配的特征点计算两个图像之间的单应性变换
    
    参数:
        kp1, kp2: SIFT/ORB关键点
        good_matches: 关键点匹配
        
    返回:
        homography_matrix: 变换矩阵
    """
    if len(good_matches) < 4:
        return None
    
    # 提取匹配点的坐标
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    # 使用RANSAC算法计算单应性矩阵
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    
    return H


def color_balance(img):
    """
    自动白平衡算法
    
    参数:
        img: 输入图像
        
    返回:
        颜色平衡后的图像
    """
    # 将图像分割为BGR通道
    b, g, r = cv2.split(img)
    
    # 计算每个通道的累积直方图
    bins = 256
    b_hist = cv2.calcHist([b], [0], None, [bins], [0, 256])
    g_hist = cv2.calcHist([g], [0], None, [bins], [0, 256])
    r_hist = cv2.calcHist([r], [0], None, [bins], [0, 256])
    
    # 计算累积分布函数
    b_cdf = b_hist.cumsum()
    g_cdf = g_hist.cumsum()
    r_cdf = r_hist.cumsum()
    
    # 归一化累积分布函数
    b_cdf_normalized = b_cdf / b_cdf[-1]
    g_cdf_normalized = g_cdf / g_cdf[-1]
    r_cdf_normalized = r_cdf / r_cdf[-1]
    
    # 找到低截断点 (1%) 和高截断点 (99%)
    low_cut = 0.01
    high_cut = 0.99
    
    b_low = np.searchsorted(b_cdf_normalized, low_cut)
    b_high = np.searchsorted(b_cdf_normalized, high_cut)
    g_low = np.searchsorted(g_cdf_normalized, low_cut)
    g_high = np.searchsorted(g_cdf_normalized, high_cut)
    r_low = np.searchsorted(r_cdf_normalized, low_cut)
    r_high = np.searchsorted(r_cdf_normalized, high_cut)
    
    # 创建查找表
    b_lookup = np.zeros((256,1), dtype=np.uint8)
    g_lookup = np.zeros((256,1), dtype=np.uint8)
    r_lookup = np.zeros((256,1), dtype=np.uint8)
    
    # 线性拉伸
    for i in range(256):
        if i < b_low:
            b_lookup[i] = 0
        elif i > b_high:
            b_lookup[i] = 255
        else:
            b_lookup[i] = np.round(255.0 * (i - b_low) / (b_high - b_low))
        
        if i < g_low:
            g_lookup[i] = 0
        elif i > g_high:
            g_lookup[i] = 255
        else:
            g_lookup[i] = np.round(255.0 * (i - g_low) / (g_high - g_low))
        
        if i < r_low:
            r_lookup[i] = 0
        elif i > r_high:
            r_lookup[i] = 255
        else:
            r_lookup[i] = np.round(255.0 * (i - r_low) / (r_high - r_low))
    
    # 应用查找表
    b_balanced = cv2.LUT(b, b_lookup)
    g_balanced = cv2.LUT(g, g_lookup)
    r_balanced = cv2.LUT(r, r_lookup)
    
    # 合并通道
    balanced = cv2.merge([b_balanced, g_balanced, r_balanced])
    
    return balanced 