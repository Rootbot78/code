#!/usr/bin/env python3
"""
长截图分割工具
将长图片分割成适合A4纸打印的短图片
智能检测空白区域进行切割
"""

import os
import sys
import warnings
from pathlib import Path
from PIL import Image
import argparse
from tkinter import Tk, filedialog

# 抑制 Pillow 14 的 getdata 警告（兼容性处理）
warnings.filterwarnings("ignore", category=DeprecationWarning, module="PIL")


def select_file():
    """使用系统文件对话框选择文件"""
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    file_path = filedialog.askopenfilename(
        title="选择长截图文件",
        filetypes=[
            ("图片文件", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
            ("所有文件", "*.*")
        ]
    )
    root.destroy()
    return file_path if file_path else None


def get_a4_height_pixels(dpi=150):
    """获取A4纸在指定DPI下的高度像素"""
    a4_height_inches = 11.69
    return int(a4_height_inches * dpi)


def find_blank_regions(gray_img, min_blank_height=30, threshold=245):
    """
    查找图片中的所有空白区域
    
    Args:
        gray_img: 灰度图
        min_blank_height: 最小空白高度（像素）
        threshold: 空白判定阈值
    
    Returns:
        [(y_start, y_end), ...] 空白区域的起止坐标
    """
    width = gray_img.width
    height = gray_img.height
    
    blank_regions = []
    current_blank_start = None
    
    for y in range(height):
        row = gray_img.crop((0, y, width, y + 1))
        pixels = list(row.getdata())
        avg_brightness = sum(pixels) / width
        
        if avg_brightness > threshold:
            if current_blank_start is None:
                current_blank_start = y
        else:
            if current_blank_start is not None:
                blank_height = y - current_blank_start
                if blank_height >= min_blank_height:
                    blank_regions.append((current_blank_start, y))
                current_blank_start = None
    
    # 处理末尾的空白
    if current_blank_start is not None:
        blank_height = height - current_blank_start
        if blank_height >= min_blank_height:
            blank_regions.append((current_blank_start, height))
    
    return blank_regions


def find_all_blank_regions(gray_img, min_blank_height=15, threshold=245):
    """
    扫描整张图片，找出所有可用于切割的空白区域
    严格的空白判定：整行所有像素都必须是空白，哪怕一条黑线也不算

    Args:
        gray_img: 灰度图
        min_blank_height: 最小空白高度
        threshold: 像素亮度阈值（>此值算作空白）

    Returns:
        [(y_start, y_end), ...] 空白区域的起止坐标
    """
    width = gray_img.width
    height = gray_img.height

    blank_regions = []
    current_blank_start = None

    for y in range(height):
        row = gray_img.crop((0, y, width, y + 1))
        pixels = list(row.getdata())
        # 严格的空白判定：整行所有像素都必须 > threshold
        is_blank_row = all(p > threshold for p in pixels)

        if is_blank_row:
            if current_blank_start is None:
                current_blank_start = y
        else:
            if current_blank_start is not None:
                blank_height = y - current_blank_start
                if blank_height >= min_blank_height:
                    blank_regions.append((current_blank_start, y))
                current_blank_start = None

    # 处理末尾的空白
    if current_blank_start is not None:
        blank_height = height - current_blank_start
        if blank_height >= min_blank_height:
            blank_regions.append((current_blank_start, height))

    return blank_regions


def find_split_point(blank_regions, start_y, min_height, img_height):
    """
    在空白区域中查找切割点，确保切割位置 >= min_height
    宁可图片大一些，也绝不切割到内容
    切割点会在空白区域中间，确保下一张图片不会以空白开头

    Args:
        blank_regions: 所有空白区域列表 [(y_start, y_end), ...]
        start_y: 当前切割起始位置
        min_height: 最小切割高度（A4高度）
        img_height: 图片总高度

    Returns:
        (cut_y, next_start_y): 切割点y坐标和下一张图片的起始位置
    """
    target_y = start_y + min_height

    # 在目标位置之后，寻找第一个完整的空白区域
    for blank_start, blank_end in blank_regions:
        # 空白区域必须在目标位置之后（或相接）
        if blank_start >= target_y:
            # 切割点在空白区域中间
            cut_y = (blank_start + blank_end) // 2
            # 下一张图片从空白结束后开始（跳过空白）
            next_start = blank_end
            return (cut_y, next_start)

    # 没找到合适的空白区域，返回图片末尾（最后一张）
    return (img_height, img_height)


def split_long_image(image_path, output_dir=None, dpi=150, min_blank_height=20):
    """
    分割长图片，在空白处切割
    
    Args:
        image_path: 长图片路径
        output_dir: 输出目录
        dpi: 打印DPI
        min_blank_height: 最小空白高度阈值
    """
    img = Image.open(image_path)
    img_width, img_height = img.size
    
    # 转换为灰度图用于分析
    gray_img = img.convert('L')
    
    # A4高度
    a4_height = get_a4_height_pixels(dpi)
    
    # 缩放图片宽度到A4宽度
    a4_width = int(8.27 * dpi)
    if img_width != a4_width:
        new_height = int(img_height * (a4_width / img_width))
        img = img.resize((a4_width, new_height), Image.Resampling.LANCZOS)
        gray_img = img.convert('L')
        img_width = a4_width  # 更新宽度
        img_height = new_height
        print(f"图片已缩放至A4宽度: {a4_width}px, 高度: {img_height}px")
    
    # 创建输出目录
    if output_dir is None:
        input_path = Path(image_path)
        output_dir = input_path.parent / f"{input_path.stem}_split"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"A4目标高度: {a4_height}px")
    print(f"最小空白高度: {min_blank_height}px")
    print(f"输出目录: {output_dir}")

    # 预先扫描所有空白区域
    print("正在分析图片空白区域...")
    blank_regions = find_all_blank_regions(gray_img, min_blank_height=15)
    print(f"找到 {len(blank_regions)} 个空白区域")

    # 分割图片
    current_y = 0
    part_num = 0

    while current_y < img_height:
        part_num += 1

        # 如果剩余部分小于A4高度，直接切割到末尾
        remaining_height = img_height - current_y
        if remaining_height <= a4_height:
            start = current_y
            end_y = img_height
            current_y = img_height  # 最后一张，直接结束
        else:
            # 在空白区域中找切割点，确保每张 >= A4高度
            start = current_y
            end_y, current_y = find_split_point(blank_regions, current_y, a4_height, img_height)

        # 裁剪图片
        crop_box = (0, start, img_width, end_y)
        part_img = img.crop(crop_box)

        # 保存图片
        output_path = output_dir / f"part_{part_num:03d}.png"
        part_img.save(output_path, "PNG", dpi=(dpi, dpi))

        actual_height = end_y - current_y
        print(f"已保存: {output_path} (y={current_y}-{end_y}, 高度={actual_height}px)")

        # 移动到下一个位置
        current_y = end_y
    
    print(f"\n完成! 共生成 {part_num} 张图片")
    
    # 生成PDF
    pdf_path = output_dir.parent / f"{output_dir.name}.pdf"
    create_pdf_from_images(output_dir, pdf_path, dpi)
    
    return output_dir


def create_pdf_from_images(images_dir, pdf_path, dpi=150):
    """将图片合并成PDF"""
    image_files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff'))
    ])
    
    if not image_files:
        print("警告: 没有找到图片文件，跳过PDF生成")
        return
    
    print(f"\n正在生成PDF: {pdf_path}")
    
    images = []
    for img_file in image_files:
        img_path = os.path.join(images_dir, img_file)
        img = Image.open(img_path)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        images.append(img)
    
    first_img = images[0]
    other_imgs = images[1:]
    
    first_img.save(
        pdf_path,
        "PDF",
        save_all=True,
        append_images=other_imgs,
        resolution=dpi,
        quality=95
    )
    
    print(f"PDF生成完成! 共 {len(images)} 页")


def main():
    parser = argparse.ArgumentParser(
        description="将长截图分割成适合A4纸打印的短图片（智能空白切割）"
    )
    
    parser.add_argument("image", nargs='?', help="长图片路径（不指定则弹出选择对话框）")
    parser.add_argument("-o", "--output", help="输出目录")
    parser.add_argument("--dpi", type=int, default=150, help="打印DPI（默认150）")
    parser.add_argument("--min-blank", type=int, default=20, help="最小空白高度（像素，默认20）")
    
    args = parser.parse_args()
    
    if args.image is None:
        image_path = select_file()
        if image_path is None:
            print("未选择文件")
            sys.exit(0)
    else:
        image_path = args.image
    
    if not os.path.exists(image_path):
        print(f"错误: 文件不存在 - {image_path}")
        sys.exit(1)
    
    output_dir = split_long_image(image_path, args.output, args.dpi, args.min_blank)
    
    print("\n打印建议:")
    print("- 纸张设置为A4")
    print("- 选择'实际大小'打印")


if __name__ == "__main__":
    main()
