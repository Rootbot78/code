#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
骑缝章生成工具 - Contract Binder Seal Generator
Linux版本，使用tkinter GUI + PyMuPDF处理PDF
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import threading
import tempfile
from pathlib import Path

# 尝试导入需要的库
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class StampSealApp:
    def __init__(self, root):
        self.root = root
        self.root.title("骑缝章生成工具")
        self.root.geometry("600x450")

        # 变量
        self.seal_path = tk.StringVar()
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.width_var = tk.StringVar(value="100")
        self.height_var = tk.StringVar(value="100")
        self.position_var = tk.StringVar(value="2")
        self.seal_size_var = tk.StringVar(value="4.0")  # 印章大小，单位cm
        self.vertical_var = tk.BooleanVar(value=True)
        self.progress_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="就绪")

        self.setup_ui()

    def setup_ui(self):
        # 标题
        title_label = tk.Label(self.root, text="骑缝章生成工具",
                               font=("Microsoft YaHei UI", 14, "bold"))
        title_label.pack(pady=5)

        # 主框架
        frame = ttk.Frame(self.root, padding="8")
        frame.pack(fill=tk.BOTH, expand=True)

        # 印章图片
        ttk.Label(frame, text="印章图片:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(frame, textvariable=self.seal_path, width=35).grid(row=0, column=1, pady=3)
        ttk.Button(frame, text="浏览", command=self.select_seal).grid(row=0, column=2, padx=3, pady=3)

        # 合同文件
        ttk.Label(frame, text="合同文件:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(frame, textvariable=self.input_path, width=35).grid(row=1, column=1, pady=3)
        ttk.Button(frame, text="浏览", command=self.select_input).grid(row=1, column=2, padx=3, pady=3)

        # 输出文件
        ttk.Label(frame, text="输出文件:").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Entry(frame, textvariable=self.output_path, width=35).grid(row=2, column=1, pady=3)
        ttk.Button(frame, text="浏览", command=self.select_output).grid(row=2, column=2, padx=3, pady=3)

        # 提示
        ttk.Label(frame, text="支持PDF、图片(按Ctrl多选)", foreground="gray", font=("Arial", 8)).grid(row=3, column=1, sticky=tk.W)

        # 分隔线
        ttk.Separator(frame, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky='ew', pady=8)

        # 放置方式
        row = 5
        ttk.Radiobutton(frame, text="垂直骑缝章", variable=self.vertical_var, value=True).grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Radiobutton(frame, text="水平骑缝章", variable=self.vertical_var, value=False).grid(row=row, column=1, sticky=tk.W, pady=3)

        # 印章大小
        row = 6
        ttk.Label(frame, text="印章大小(cm):").grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(frame, textvariable=self.seal_size_var, width=8).grid(row=row, column=1, sticky=tk.W, pady=3)
        ttk.Label(frame, text="(宽度，程序会自动分割)").grid(row=row, column=2, sticky=tk.W, pady=3)

        # 进度条
        row = 7
        self.progress = ttk.Progressbar(frame, mode='determinate', length=350)
        self.progress.grid(row=row, column=0, columnspan=3, pady=10)

        # 状态
        row = 8
        ttk.Label(frame, textvariable=self.status_var).grid(row=row, column=0, columnspan=3, pady=3)

        # 开始按钮
        row = 9
        self.start_btn = ttk.Button(frame, text="开始处理", command=self.start_process)
        self.start_btn.grid(row=row, column=1, pady=8)

    def select_seal(self):
        path = filedialog.askopenfilename(
            title="选择印章图片",
            filetypes=[("PNG图片", "*.png"), ("所有文件", "*.*")]
        )
        if path:
            self.seal_path.set(path)

    def select_input(self):
        path = filedialog.askopenfilenames(
            title="选择合同文件",
            filetypes=[
                ("所有支持文件", "*.pdf *.png *.jpg *.jpeg *.bmp"),
                ("PDF文档", "*.pdf"),
                ("图片文件", "*.png *.jpg *.jpeg *.bmp"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            if len(path) == 1:
                self.input_path.set(path[0])
            else:
                self.input_path.set("; ".join(path))

    def select_output(self):
        path = filedialog.asksaveasfilename(
            title="指定输出文件",
            filetypes=[
                ("PDF文档", "*.pdf"),
                ("PNG图片", "*.png"),
                ("所有文件", "*.*")
            ]
        )
        if path:
            self.output_path.set(path)

    def validate_inputs(self):
        if not self.seal_path.get():
            messagebox.showerror("错误", "请选择印章图片！")
            return False
        if not self.input_path.get():
            messagebox.showerror("错误", "请选择合同文件！")
            return False
        if not self.output_path.get():
            messagebox.showerror("错误", "请指定输出文件！")
            return False
        if not os.path.exists(self.seal_path.get()):
            messagebox.showerror("错误", "印章文件不存在！")
            return False
        return True

    def validate_seal_size(self):
        """验证印章大小输入"""
        try:
            size = float(self.seal_size_var.get())
            if size <= 0 or size > 10:
                messagebox.showerror("错误", "印章大小需在0.1~10之间(cm)")
                return False
            return True
        except ValueError:
            messagebox.showerror("错误", "印章大小需为数字")
            return False

    def add_seal_to_image(self, src_img, seal_img, page_index, total_pages, config):
        """将印章叠加到图片上（骑缝章：印章垂直切成N条，每页放一条在右边）"""
        img_width, img_height = src_img.size

        # 创建带透明通道的输出图片
        if src_img.mode != 'RGBA':
            output = src_img.convert('RGBA')
        else:
            output = src_img.copy()

        if output.mode != 'RGBA':
            output = output.convert('RGBA')

        # 印章完整尺寸
        seal_full_w, seal_full_h = seal_img.size

        # 垂直切割：切成N条，每条宽度=印章宽度/N，高度不变
        slice_w = seal_full_w // total_pages

        # 缩放印章切片（先计算，以便确定位置）
        seal_size_cm = float(config.get('seal_size_cm', 4.0))
        seal_physical_width_mm = seal_size_cm * 10
        pdf_dpi = 150
        target_seal_width_px = int(seal_physical_width_mm / 25.4 * pdf_dpi)

        # 避免除零
        if seal_full_w == 0:
            seal_full_w = 1
        scale = target_seal_width_px / seal_full_w
        new_seal_w = max(1, int((seal_full_w / total_pages) * scale))
        new_seal_h = max(1, int(seal_full_h * scale))

        # 计算印章位置（右边）
        # 印章右边缘距离纸边约1mm（根据实际纸张尺寸按比例计算）
        # 1mm / 210mm ≈ 0.005 的比例
        edge_margin_ratio = 0.005  # 约0.5%的纸张宽度
        edge_margin_px = int(img_width * edge_margin_ratio)

        if page_index == total_pages - 1:
            # 最后一页，印章右边缘距纸边稍大（约2mm）
            x = img_width - edge_margin_px * 2 - new_seal_w
        else:
            # 前面几页，印章右边缘距纸边1mm
            x = img_width - edge_margin_px - new_seal_w

        # 裁剪印章切片（第page_index条）
        seal_slice = seal_img.crop((
            page_index * slice_w,
            0,
            (page_index + 1) * slice_w,
            seal_full_h
        ))

        seal_resized = seal_slice.resize((new_seal_w, new_seal_h), Image.LANCZOS)

        # y位置：页面垂直居中
        y = (img_height - new_seal_h) // 2

        output.paste(seal_resized, (x, y), seal_resized)

        return output.convert('RGB')

    def process_images(self, input_files, output_path, config):
        """处理图片并添加骑缝章"""
        total = len(input_files)
        success_count = 0

        for i, input_file in enumerate(input_files):
            self.status_var.set(f"正在处理: {os.path.basename(input_file)}")
            self.progress['value'] = (i / total) * 100
            self.root.update_idletasks()

            try:
                # 读取原图
                src_img = Image.open(input_file)

                # 读取印章
                seal_img = Image.open(config['seal_path'])

                # 添加骑缝章（传递总页数以便分割印章）
                result = self.add_seal_to_image(src_img, seal_img, i, total, config)

                # 生成输出文件名
                if total == 1:
                    output_file = output_path
                else:
                    name = Path(output_path).stem
                    ext = Path(output_path).suffix
                    dir_path = Path(output_path).parent
                    output_file = dir_path / f"{name}_{i+1:03d}{ext}"

                # 保存 - 输出为PNG
                output_ext = Path(output_file).suffix.lower()
                if output_ext == '.pdf':
                    # PDF输出时先保存为PNG，后面再转换
                    output_file = str(Path(output_file).with_suffix('.png'))
                result.save(output_file, quality=95)
                success_count += 1

            except Exception as e:
                import traceback
                print(f"处理失败 {input_file}: {e}")
                traceback.print_exc()

        return success_count, total

    def pdf_to_images(self, pdf_path, temp_dir):
        """将PDF转换为图片，返回图片路径列表和每页尺寸信息"""
        if not HAS_PYMUPDF:
            raise Exception("需要安装 PyMuPDF: pip install PyMuPDF")

        images = []
        page_sizes = []  # 每页的实际尺寸（点为单位，72点=1英寸）
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                # 获取页面实际尺寸（点）
                rect = page.mediabox
                page_width_pt = rect.width
                page_height_pt = rect.height
                page_sizes.append((page_width_pt, page_height_pt))

                # 设置较高的分辨率
                mat = fitz.Matrix(2, 2)  # 2x缩放，相当于150 DPI
                pix = page.get_pixmap(matrix=mat)
                output_path = os.path.join(temp_dir, f"page_{page_num+1:03d}.png")
                pix.save(output_path)
                images.append(output_path)
            doc.close()
        except Exception as e:
            raise Exception(f"PDF转换失败: {e}")

        return images

    def images_to_pdf(self, image_paths, output_pdf):
        """将多张图片合并为PDF"""
        if not HAS_PYMUPDF:
            raise Exception("需要安装 PyMuPDF: pip install PyMuPDF")

        try:
            doc = fitz.open()
            for img_path in image_paths:
                # 使用PIL获取图片尺寸
                with Image.open(img_path) as img:
                    width = img.width * 72 / 96  # 转换DPI
                    height = img.height * 72 / 96
                # 创建页面并插入图片
                page = doc.new_page(width=width, height=height)
                page.insert_image(page.rect, filename=img_path)
            doc.save(output_pdf)
            doc.close()
            return True
        except Exception as e:
            raise Exception(f"PDF生成失败: {e}")

    def process_thread(self):
        """处理线程"""
        try:
            input_text = self.input_path.get()
            output_path = self.output_path.get()

            # 解析输入文件
            if ';' in input_text:
                input_files = [f.strip() for f in input_text.split(';')]
            else:
                input_files = [input_text]

            # 过滤实际存在的文件
            input_files = [f for f in input_files if os.path.exists(f) and os.path.isfile(f)]

            # 分离PDF和图片
            pdf_files = [f for f in input_files if f.lower().endswith('.pdf')]
            image_files = [f for f in input_files if not f.lower().endswith('.pdf')]

            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="stamp_seal_")

            try:
                # 处理PDF文件
                if pdf_files:
                    self.status_var.set("正在转换PDF文件...")
                    self.root.update_idletasks()

                    for pdf in pdf_files:
                        pages = self.pdf_to_images(pdf, temp_dir)
                        image_files.extend(pages)

                if not image_files:
                    messagebox.showerror("错误", "没有找到支持的图片文件！")
                    return

                # 配置
                config = {
                    'seal_path': self.seal_path.get(),
                    'seal_width': int(self.width_var.get()) if self.width_var.get() else 100,
                    'seal_height': int(self.height_var.get()) if self.height_var.get() else 100,
                    'position_ratio': float(self.position_var.get()) / 100 if self.position_var.get() else 0.02,
                    'vertical': self.vertical_var.get(),
                    'seal_size_cm': float(self.seal_size_var.get()) if self.seal_size_var.get() else 4.0
                }

                # 处理图片
                success, total = self.process_images(image_files, output_path, config)

                # 如果输出是PDF
                output_ext = os.path.splitext(output_path)[1].lower()
                print(f"DEBUG: output_ext={output_ext}, success={success}")
                if output_ext == '.pdf' and success > 0:
                    self.status_var.set("正在生成PDF...")
                    self.root.update_idletasks()

                    # 收集处理后的图片
                    stamped_images = []
                    name = Path(output_path).stem
                    dir_path = Path(output_path).parent
                    for i in range(1, total + 1):
                        stamped_images.append(str(dir_path / f"{name}_{i:03d}.png"))

                    stamped_images = [f for f in stamped_images if os.path.exists(f)]

                    if stamped_images:
                        print(f"DEBUG: 生成PDF, 图片数量: {len(stamped_images)}")
                        print(f"DEBUG: 图片列表: {stamped_images}")
                        try:
                            self.images_to_pdf(stamped_images, output_path)
                            print(f"DEBUG: PDF已生成: {output_path}, 存在={os.path.exists(output_path)}")
                        except Exception as e:
                            print(f"DEBUG: images_to_pdf错误: {e}")
                        # 删除临时图片
                        for f in stamped_images:
                            if f != output_path:
                                try:
                                    os.remove(f)
                                except:
                                    pass

                self.progress['value'] = 100
                self.status_var.set("处理完成！")
                messagebox.showinfo("完成", f"处理完成！\n成功: {success}/{total}\n输出文件: {output_path}")

            finally:
                # 清理临时目录
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except:
                    pass

        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}"
            print(f"处理出错: {error_msg}")
            print(traceback.format_exc())
            messagebox.showerror("错误", error_msg)

        finally:
            self.start_btn['state'] = 'normal'
            self.progress['value'] = 0
            self.status_var.set("就绪")

    def start_process(self):
        if not self.validate_inputs():
            return

        if not self.validate_seal_size():
            return

        # 运行时检查PyMuPDF是否可用
        try:
            import fitz
        except ImportError:
            messagebox.showerror("错误", "缺少 PyMuPDF 库！\n请使用虚拟环境运行：\n~/venv/bin/python3 stamp_seal_gui.py")
            return

        self.start_btn['state'] = 'disabled'
        threading.Thread(target=self.process_thread, daemon=True).start()


def main():
    root = tk.Tk()
    app = StampSealApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
