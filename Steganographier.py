# -*- coding: utf-8 -*-
"""

pip install tkinterdnd2
pip install pyzipper
pip install hachoir
pip install natsort

"""

import os
import io
import re
import sys
import signal
import json
import random
import datetime
import tkinter as tk
from tkinter import  messagebox, ttk, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import pyzipper
import zipfile
import threading
import subprocess
import string
from hachoir.parser import createParser
from hachoir.metadata import extractMetadata
from natsort import ns, natsorted # windows风格的按名称排序专用包
import time
import argparse
import hashlib


def generate_random_filename(length=16):
    """生成指定长度的随机文件名, 不带扩展名"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m:{seconds:02d}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours}h:{minutes:02d}m:{seconds:02d}s"

def get_video_duration(filepath):
    parser = createParser(filepath)
    if not parser:
        return None
    try:
        metadata = extractMetadata(parser)
        if not metadata:
            return None
        duration = metadata.get('duration')
        return int(duration.seconds) if duration else None
    finally:
        if parser.stream:
            parser.stream._input.close()

def get_cover_video_files_info(folder_path, sort_by_duration=False):
    try:
        videos = []
        for filename in os.listdir(folder_path):
            if filename.endswith(".mp4"):
                filepath = os.path.join(folder_path, filename)
                duration_seconds = get_video_duration(filepath)
                if duration_seconds is None:
                    formatted_duration = "Unknown"
                else:
                    formatted_duration = format_duration(duration_seconds)
                size = get_file_or_folder_size(filepath)  # 获取文件/文件夹大小
                videos.append({
                    "filename": filename,
                    "duration": formatted_duration,
                    "duration_seconds": duration_seconds or 0,  # 时长未知则为0
                    "size": format_size(size)
                })

        # 先按Windows显示风格排序
        videos = list(natsorted(videos, key=lambda x: x['filename'], alg=ns.PATH)) 
        
        # 如果需要，再按总时长降序排列
        if sort_by_duration:
            videos.sort(key=lambda x: x['duration_seconds'], reverse=True)
        
        # 格式化显示
        formatted_videos = [f"{video['filename']} - {video['duration']} - {video['size']}" for video in videos]
        return formatted_videos
    
    except Exception as e:
        # 如果出现任何错误，返回空列表并可以打印错误信息进行调试
        print(f"An error occurred: {e}")
        return []

def get_file_or_folder_size(path):
    total_size = 0
    if os.path.isfile(path):
        total_size = os.path.getsize(path)
    elif os.path.isdir(path):
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
    return total_size

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024            

def check_size_and_duration(size, duration_seconds):
    duration_minutes = duration_seconds / 60
    # 根据参考标准判断
    if size <= 200 * 1024*1024 and duration_minutes < 1:
        return False
    elif 200 * 1024*1024 < size <= 400 * 1024*1024 and duration_minutes < 3:
        return False
    elif 400 * 1024*1024 < size <= 500 * 1024*1024 and duration_minutes < 15:
        return False
    elif 500 * 1024*1024 < size <= 1 * 1024*1024*1024 and duration_minutes < 30:
        return False
    elif 1 * 1024*1024*1024 < size <= 3 * 1024*1024*1024 and duration_minutes < 60:
        return False
    elif 3 * 1024*1024*1024 < size <= 4 * 1024*1024*1024 and duration_minutes < 120:
        return False
    elif size > 4 * 1024*1024*1024 and duration_minutes <= 120:
        return False
    return True

def add_empty_mdat_box(file):
    mdat_size = 8  # Minimum box size
    mdat_box = mdat_size.to_bytes(4, byteorder='big') + b'mdat'
    file.write(mdat_box)

class SteganographierGUI:
    '''GUI: 隐写者程序表示层'''
    def __init__(self):
        self.root = TkinterDnD.Tk()
        self.video_folder_path = os.path.join(application_path, "cover_video")  # 定义实例变量 默认外壳MP4文件存储路径
        self.output_option          = "外壳文件名"  # 设置输出模式的默认值
        self.type_option_var = tk.StringVar(value="mp4")
        self.output_cover_video_name_mode_var = tk.StringVar(value="")
        self.mkvmerge_exe           = os.path.join(application_path,'tools','mkvmerge.exe')
        self.mkvextract_exe         = os.path.join(application_path,'tools','mkvextract.exe')
        self.mkvinfo_exe            = os.path.join(application_path,'tools','mkvinfo.exe')
        self._7z_exe                = os.path.join(application_path,'tools','7z.exe')
        self.hash_modifier_exe      = os.path.join(application_path,'tools','hash_modifier.exe')
        self.captcha_generator_exe  = os.path.join(application_path,'tools','captcha_generator.exe')
        self.title = "隐写者GUI"
        self.total_file_size = None     # 被隐写文件总大小
        self.password = None            # 密码
        self.password_modified = False  # 追踪密码是否被用户修改过
        self.check_file_size_and_duration_warned = False # 追踪是否警告过文件大小-外壳时长匹配问题
        self.cover_video_options = []         # 外壳MP4文件列表
        
        self.hash_modifier_process = None
        self.hash_modifier_thread = None
        self.captcha_generator_process = None
        self.captcha_generator_thread = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.config_file = os.path.join(application_path, "config.json") # 设置配置文件路径
        self.load_config()  # 程序启动时加载配置文件
        print(f"Loaded password from config: '{self.password}'")  # Debug output

        self.steganographier = Steganographier(self.video_folder_path, gui_enabled=True)          # 创建一个Steganographier类的实例 传递self.video_folder_path  
        self.steganographier.set_progress_callback(self.update_progress)        # GUI进度条回调显示函数, 把GUI的进度条函数传给逻辑层, 从而把逻辑层的进度传回GUI
        self.steganographier.set_cover_video_duration_callback(self.on_cover_video_duration) # 外壳文件时长回调函数, 把当前外壳视频时长传回GUI
        self.steganographier.set_log_callback(self.log)     # log回调函数

        self.create_widgets()           # GUI实现部分

    # 1. 窗口控件初始化方法
    def create_widgets(self):
        # 1.1 参数设定部分
        params_frame = tk.Frame(self.root)
        params_frame.pack(pady=5)

        self.root.title(self.title)
        try:
            self.root.iconbitmap(os.path.join(application_path,'modules','favicon.ico'))  # 设置窗口图标
        except tk.TclError:
            print("无法找到图标文件, 继续运行程序...")

        # 密码输入框
        self.password_label = tk.Label(params_frame, text="密码:")
        self.password_label.pack(side=tk.LEFT, padx=5)
        self.password_entry = tk.Entry(params_frame, width=13, fg="grey")
        
        def clear_default_password(event):
            if self.password_entry.get() == "留空则无密码":
                self.password_entry.delete(0, tk.END)
            self.password_entry.configure(fg="black") #, show="*"
            self.password_modified = True

        def restore_default_password(event):
            if not self.password_entry.get():
                self.password_entry.insert(0, "留空则无密码")
                self.password_entry.configure(fg="grey", show="")
                self.password_modified = False
            else:
                self.password_modified = True

        if self.password:
            self.password_entry.insert(0, self.password)
            self.password_entry.configure(fg="black") # , show="*"
            self.password_modified = True
        else:
            self.password_entry.insert(0, "留空则无密码")
        
        self.password_entry.pack(side=tk.LEFT, padx=10)
        self.password_entry.bind("<FocusIn>", clear_default_password)
        self.password_entry.bind("<FocusOut>", restore_default_password)

        # 工作模式选择
        self.type_option_label = tk.Label(params_frame, text="工作模式:")
        self.type_option_label.pack(side=tk.LEFT, padx=5, pady=5)
        self.type_option_var = tk.StringVar(value=self.type_option_var.get())  # 使用加载的配置
        self.type_option = tk.OptionMenu(params_frame, self.type_option_var, "mp4")
        self.type_option.config(width=4)
        self.type_option.pack(side=tk.LEFT, padx=5, pady=5)

        # 输出选项
        self.output_option_label = tk.Label(params_frame, text="输出名:")
        self.output_option_label.pack(side=tk.LEFT, padx=5, pady=5)
        self.output_option_var = tk.StringVar(value=self.output_option)  # 使用加载的配置
        self.output_option = tk.OptionMenu(params_frame, self.output_option_var, "原文件名", "外壳文件名", "随机文件名")
        self.output_option.config(width=8)
        self.output_option.pack(side=tk.LEFT, padx=5, pady=5)
        
        # 1.2 隐写/解隐写文件拖入窗口
        self.hide_frame = tk.Frame(self.root, bd=2, relief=tk.GROOVE)
        self.hide_frame.pack(pady=10)
        self.hide_label = tk.Label(self.hide_frame, text="在此窗口中批量输入/拖入需要隐写的文件/文件夹:") 
        self.hide_label.pack()
        self.hide_text = tk.Text(self.hide_frame, width=65, height=5)
        self.hide_text.pack()
        self.hide_text.drop_target_register(DND_FILES)
        self.hide_text.dnd_bind("<<Drop>>", self.hide_files_dropped)
        
        self.reveal_frame = tk.Frame(self.root, bd=2, relief=tk.GROOVE)
        self.reveal_frame.pack(pady=10)
        self.reveal_label = tk.Label(self.reveal_frame, text="在此窗口中批量输入/拖入需要解除隐写的MP4/MKV文件:")
        self.reveal_label.pack()
        self.reveal_text = tk.Text(self.reveal_frame, width=65, height=5)
        self.reveal_text.pack()
        self.reveal_text.drop_target_register(DND_FILES)
        self.reveal_text.dnd_bind("<<Drop>>", self.reveal_files_dropped)
        
        # 1.3 外壳MP4文件选择相关逻辑
        video_folder_frame = tk.Frame(self.root)
        video_folder_frame.pack(pady=5)
        
        video_folder_label = tk.Label(video_folder_frame, text="外壳MP4文件存放:")
        video_folder_label.pack(side=tk.LEFT, padx=5)
        
        self.video_folder_entry = tk.Entry(video_folder_frame, width=35)
        self.video_folder_entry.insert(0, self.video_folder_path)
        self.video_folder_entry.pack(side=tk.LEFT, padx=5)
        
        self.video_folder_button = tk.Button(video_folder_frame, text="选择文件夹", command=self.select_video_folder)
        self.video_folder_button.pack(side=tk.LEFT, padx=5)
        
        if os.path.exists(self.video_folder_path):
            self.cover_video_options = get_cover_video_files_info(self.video_folder_path) # 获取外壳MP4视频文件列表和时长-大小信息
        else:
            self.cover_video_options = []  # 如果文件夹不存在, 提供一个默认的空列表
            
        self.output_cover_video_name_mode_var = tk.StringVar()
        if self.cover_video_options:
            self.output_cover_video_name_mode_var.set(self.cover_video_options[0])  # 默认选择菜单中的第一个视频文件
            # self.output_cover_video_name_mode_var.set('===============名称顺序模式===============')  # 默认选择模式
        else:
            self.output_cover_video_name_mode_var.set("No videos found")
        
        self.video_option_menu = tk.OptionMenu(self.root, 
                                               self.output_cover_video_name_mode_var,   # 默认选择
                                               *self.cover_video_options,               # 其余选择
                                                '===============随机选择模式===============', 
                                                '===============时长顺序模式===============',
                                                '===============名称顺序模式===============')
        self.video_option_menu.pack()
        
        # 1.4 log文本框和滚动条
        log_frame = tk.Frame(self.root)
        log_frame.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)  # 调整布局管理器为 pack，支持扩展

        log_scrollbar_y = tk.Scrollbar(log_frame)
        log_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)  # 垂直滚动条设置为填充Y方向

        log_scrollbar_x = tk.Scrollbar(log_frame, orient=tk.HORIZONTAL)
        log_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)  # 水平滚动条设置为填充X方向

        self.log_text = tk.Text(log_frame, wrap=tk.NONE, 
                                yscrollcommand=log_scrollbar_y.set,
                                xscrollcommand=log_scrollbar_x.set, 
                                width=65, height=10, state=tk.NORMAL)
        self.log_text.insert(tk.END, "请勿用于非法途径\n")
        self.log_text.configure(state=tk.DISABLED, fg="grey")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)  # 文本框设置为填充BOTH方向，并支持扩展

        log_scrollbar_y.config(command=self.log_text.yview)  # 设置垂直滚动条与文本框的联动
        log_scrollbar_x.config(command=self.log_text.xview)  # 设置水平滚动条与文本框的联动
        
        # 1.5 控制按钮部分
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.start_button = tk.Button(button_frame, text="开始执行", command=self.start_thread, width=12, height=2)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = tk.Button(button_frame, text="清除窗口", command=self.clear, width=12, height=2)
        self.clear_button.pack(side=tk.LEFT, padx=5)

        # self.start_hash_modifier_button = tk.Button(button_frame, text="哈希修改器", command=self.start_hash_modifier, width=12, height=2)
        # self.start_hash_modifier_button.pack(side=tk.LEFT, padx=5)
        #
        # self.start_captcha_generator_button = tk.Button(button_frame, text="验证码生成器", command=self.start_captcha_generator, width=12, height=2)
        # self.start_captcha_generator_button.pack(side=tk.LEFT, padx=5)
        
        # 1.6 进度条
        self.progress = ttk.Progressbar(self.root, length=500, mode='determinate')
        self.progress.pack(pady=10)
        
        self.root.mainloop()

    # 2. 被隐写文件的拖入方法
    def hide_files_dropped(self, event):
        file_paths = self.root.tk.splitlist(event.data)
        self.hide_text.insert(tk.END, "\n".join(file_paths) + "\n")
        for idx, file_path in enumerate(file_paths):
            size = get_file_or_folder_size(file_path)
            print(f"Target size: {size}")
            print(f"self.type_option_var.get(): {self.type_option_var.get()}")
            # 检查是否为 mkv 文件并且大小是否超过 2GB
            if self.type_option_var.get() == "mkv" and size > 2 * 1024 * 1024 * 1024:
                messagebox.showerror("文件大小错误", "mkv 文件不能隐写超过 2GB 的文件")
                self.clear()
                return
            # 2.1 由逻辑层传入当前正在使用的外壳MP4文件, 用来进行大小-时长检查
            cover_video_path = self.steganographier.choose_cover_video_file(
                processed_files=idx,
                output_cover_video_name_mode=self.output_cover_video_name_mode_var.get(),
                video_folder_path=self.video_folder_path,
            )
            duration_seconds = get_video_duration(cover_video_path)
            self.check_file_size_and_duration(file_path, duration_seconds, idx) 
            self.log(f"输入[{idx+1}]: {os.path.split(file_path)[1]}, 文件/文件夹大小 {format_size(size)}, 预定外壳时长 {format_duration(duration_seconds)}")

    # 2.a 检查输入大小-外壳时长, 并给出建议
    def check_file_size_and_duration(self, file_path, duration_seconds, idx=0):
        size = get_file_or_folder_size(file_path)
        if not check_size_and_duration(size, duration_seconds) and self.check_file_size_and_duration_warned == False:
            messagebox.showinfo("===========【文件隐写不合理提醒】===========", self.get_warning_text(size, duration_seconds, idx))
            self.check_file_size_and_duration_warned = True
    
    # 2.b 给出建议的text文本
    def get_warning_text(self, size, duration_seconds, idx):
        return f'''本弹窗仅为提醒, 并非报错

输入 [{idx+1}] 体积为 {format_size(size)}, 预定外壳 [{idx+1}] 时长: {format_duration(duration_seconds)}

【体积较大但时长较短】的文件容易【引起怀疑】, 建议【分卷压缩】后再进行隐写, 或者选取较长的外壳视频, 本警告程序重启前仅提醒 1 次, 可参照下列建议值检查其他文件是否存在问题. 

建议值：
文件大小		外壳视频时长
--------------------------------
0-200MB		1-3分钟
200-400MB	3-15分钟
400-500MB	15-30分钟
500MB-1GB	30分钟-1小时
1GB-3GB		1小时
3GB-4GB		2小时
>4GB		2小时以上

本弹窗仅为提醒, 并非报错, 可以坚持执行.
'''

    # 3. 解除隐写文件的拖入方法
    def reveal_files_dropped(self, event):
        file_paths = self.root.tk.splitlist(event.data)
        self.reveal_text.insert(tk.END, "\n".join(file_paths) + "\n")
        for idx, file_path in enumerate(file_paths):
            size = get_file_or_folder_size(file_path)
            self.log(f"输入[{idx+1}]: {os.path.split(file_path)[1]} 大小: {format_size(size)}")

    # 4. 外壳MP4文件路径传参更新函数
    def update_video_folder_path(self, new_path):
        self.video_folder_path = new_path
        self.steganographier.video_folder_path = new_path  # 更新Steganographier实例的video_folder_path

    # 4.a 选择外壳MP4文件夹函数
    def select_video_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.video_folder_path = folder_path
            self.video_folder_entry.delete(0, tk.END)
            self.video_folder_entry.insert(0, folder_path)
            self.update_video_folder_path(folder_path)  # 调用方法更新video_folder_path
            
            # 4.a.1 更新外壳MP4视频文件列表和信息
            self.cover_video_options = get_cover_video_files_info(self.video_folder_path)         
            self.cover_video_options +=  ['===============随机选择模式===============', 
                                            '===============时长顺序模式===============', 
                                            '===============名称顺序模式===============']
            if not [item for item in os.listdir(self.video_folder_path) if item.lower().endswith('.mp4')]:
                messagebox.showwarning("Warning", "文件夹下没有MP4文件, 请添加文件后继续.")
                self.output_cover_video_name_mode_var.set("No videos found")
                self.video_option_menu['menu'].delete(0, 'end')
                return

            self.output_cover_video_name_mode_var.set(self.cover_video_options[0]) # 默认选择第一个文件
            # self.output_cover_video_name_mode_var.set('===============名称顺序模式===============')
            self.video_option_menu['menu'].delete(0, 'end')
            for option in self.cover_video_options:
                self.video_option_menu['menu'].add_command(label=option, 
                                                            command=tk._setit(self.output_cover_video_name_mode_var, option))

    # 检查mkv工具是否缺失
    def check_mkvtools_existence(self):
        missing_tools = []
        for tool in [self.mkvmerge_exe, self.mkvinfo_exe, self.mkvextract_exe]:
            if not os.path.exists(tool):
                missing_tools.append(os.path.basename(tool))

        if missing_tools:
            messagebox.showwarning("Warning", "以下工具文件缺失, 请在tools文件夹中添加后继续: " + ", ".join(missing_tools))
            return False
        return True

    # 检查7zip工具是否缺失
    def check_7zip_existence(self):
        missing_tools = []
        for tool in [self._7z_exe]:
            if not os.path.exists(tool):
                missing_tools.append(os.path.basename(tool))

        if missing_tools:
            messagebox.showwarning("Warning", "以下工具文件缺失, 请在tools文件夹中添加后继续: " + ", ".join(missing_tools))
            return False
        return True

    def log(self, message):
        self.log_text.configure(state=tk.NORMAL, fg="grey")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.configure(state=tk.DISABLED, fg="grey")
        self.log_text.see(tk.END)
        self.log_text.update_idletasks()
        
    def start_thread(self):
        # 在启动线程前, 先将焦点转移到主窗口上, 触发密码输入框的FocusOut事件
        self.root.focus_set()
        threading.Thread(target=self.start).start()
    
    def start(self):
        # 1. 开始后禁用start和clear按钮
        self.start_button.configure(state=tk.DISABLED)
        self.clear_button.configure(state=tk.DISABLED)
        
        self.progress['value'] = 0 # 初始化进度条
        
        # 2. 获取密码的逻辑
        def get_password():
            if not self.password_modified:
                return ""  # 如果密码未修改过, 返回空字符串
            return self.password_entry.get()
        self.password = get_password()
        
        if self.type_option_var.get() == 'mkv': # MKV模式检查工具是否存在
            if not self.check_mkvtools_existence():
                # 结束后恢复按钮
                self.start_button.configure(state=tk.NORMAL)
                self.clear_button.configure(state=tk.NORMAL)
                return

        # 3. 输入文件检查
        hide_file_paths = self.hide_text.get("1.0", tk.END).strip().split("\n")
        reveal_file_paths = self.reveal_text.get("1.0", tk.END).strip().split("\n")
        if not any(hide_file_paths) and not any(reveal_file_paths):
            messagebox.showwarning("Warning", "请输入或拖入文件.")
            # 结束后恢复按钮
            self.start_button.configure(state=tk.NORMAL)
            self.clear_button.configure(state=tk.NORMAL)
            return

        # 4. 外壳MP4文件检查
        if not [item for item in os.listdir(self.video_folder_path) if item.lower().endswith('.mp4')]:
            messagebox.showwarning("Warning", "文件夹下没有MP4文件, 请添加文件后继续.")
            self.output_cover_video_name_mode_var.set("No videos found")
            self.video_option_menu['menu'].delete(0, 'end')
            # 结束后恢复按钮
            self.start_button.configure(state=tk.NORMAL)
            self.clear_button.configure(state=tk.NORMAL)
            return        
        
        total_files = len(hide_file_paths) + len(reveal_file_paths)
        
        # 5. 隐写流程
        processed_files = 0
        for input_file_path in hide_file_paths:
            if input_file_path:
                self.steganographier.hide_file(input_file_path=input_file_path, 
                                            password=self.password,
                                            processed_files=processed_files,
                                            output_option=self.output_option_var.get(),
                                            output_cover_video_name_mode=self.output_cover_video_name_mode_var.get(),
                                            type_option_var=self.type_option_var.get(),
                                            video_folder_path=self.video_folder_path)
                processed_files += 1
                self.update_progress(processed_files, total_files)
        
        # 6. 解除隐写流程
        processed_files = 0
        for input_file_path in reveal_file_paths:
            if input_file_path:
                self.steganographier.reveal_file(input_file_path=input_file_path, 
                                                 password=self.password, 
                                                 type_option_var=self.type_option_var.get())
                processed_files += 1
                self.update_progress(processed_files, total_files)
        
        messagebox.showinfo("Success", "所有操作已完成！")
        # 结束后恢复按钮
        self.start_button.configure(state=tk.NORMAL)
        self.clear_button.configure(state=tk.NORMAL)
        
    def update_progress(self, processed_size, total_size): # 进度条回调函数, 接收逻辑层的处理进度然后显示在GUI中
        progress = (processed_size+1) / total_size
        self.progress['value'] = progress * 100
        self.root.update_idletasks()

    def on_cover_video_duration(self, duration_seconds): # 回调函数, 用于接收来自逻辑层的外壳文件时长信息
        self.cover_video_duration = duration_seconds
    
    def clear(self):
        self.hide_text.delete("1.0", tk.END)
        self.reveal_text.delete("1.0", tk.END)
        
        self.log_text.configure(state=tk.NORMAL, fg="grey")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, "【免责声明】:\n--本程序仅用于保护个人信息安全, 请勿用于任何违法犯罪活动--\n--否则后果自负, 开发者对此不承担任何责任--\nConsole output goes here...\n\n")
        self.log_text.configure(state=tk.DISABLED, fg="grey")
        # self.check_file_size_and_duration_warned = False # 禁用此则程序重启前大小检测只提醒一次, 启用后每次程序复位都会恢复它

    def start_hash_modifier(self):
        self.start_hash_modifier_button.config(state=tk.DISABLED)

        def run_and_wait():
            try:
                # 使用 subprocess.DETACHED_PROCESS 标志启动进程
                self.hash_modifier_process = subprocess.Popen(
                    [self.hash_modifier_exe],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self.hash_modifier_process.wait()
            finally:
                self.start_hash_modifier_button.config(state=tk.NORMAL)
                self.hash_modifier_process = None
                self.hash_modifier_thread = None

        self.hash_modifier_thread = threading.Thread(target=run_and_wait)
        self.hash_modifier_thread.start()

    def start_captcha_generator(self):
        self.start_captcha_generator_button.config(state=tk.DISABLED)

        def run_and_wait():
            try:
                # 使用 subprocess.DETACHED_PROCESS 标志启动进程
                self.captcha_generator_process = subprocess.Popen(
                    [self.captcha_generator_exe],
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self.captcha_generator_process.wait()
            finally:
                self.start_captcha_generator_button.config(state=tk.NORMAL)
                self.captcha_generator_process = None
                self.captcha_generator_thread = None

        self.captcha_generator_thread = threading.Thread(target=run_and_wait)
        self.captcha_generator_thread.start()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                # 从配置文件获取 video_folder_path，若不存在则使用默认值
                self.video_folder_path = config.get('video_folder_path', self.video_folder_path) 
                # 如果 video_folder_path 不存在，使用默认路径
                if not os.path.exists(self.video_folder_path):
                    # 在这里设置默认的路径
                    self.video_folder_path = os.path.join(application_path, "cover_video")
                    
                self.password = config.get('password', '')
                self.output_option = config.get('output_option', self.output_option)
                self.type_option_var = tk.StringVar(value=config.get('type_option', 'mp4'))
                self.output_cover_video_name_mode_var = tk.StringVar(value=config.get('output_cover_video_name_mode', ''))

    def save_config(self):
        config = {
            'video_folder_path': self.video_folder_path,
            'password': self.password_entry.get() if self.password_modified else '',
            'output_option': self.output_option_var.get(),
            'type_option': self.type_option_var.get(),
            'output_cover_video_name_mode': self.output_cover_video_name_mode_var.get()
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=4)

    def on_closing(self):
        # 程序关闭时保存配置
        self.save_config()
        # 程序退出时关闭已打开的 hash_generator
        if self.hash_modifier_process:
            # 使用 taskkill 命令强制结束进程树
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.hash_modifier_process.pid)])
        
        if self.hash_modifier_thread and self.hash_modifier_thread.is_alive():
            self.hash_modifier_thread.join(timeout=1)
        
        # 程序退出时关闭已打开的 captcha_generator
        if self.captcha_generator_process:
            # 使用 taskkill 命令强制结束进程树
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.captcha_generator_process.pid)])
        
        if self.captcha_generator_thread and self.captcha_generator_thread.is_alive():
            self.captcha_generator_thread.join(timeout=1)

        self.root.destroy()
        # 强制结束整个 Python 进程
        os._exit(0)










class Steganographier:
    '''隐写的具体功能由此类实现'''
    def __init__(self, video_folder_path=None, gui_enabled=False, password_file=None):
        self.mkvmerge_exe   = os.path.join(application_path,'tools','mkvmerge.exe')
        self.mkvextract_exe = os.path.join(application_path,'tools','mkvextract.exe')
        self.mkvinfo_exe    = os.path.join(application_path,'tools','mkvinfo.exe')
        self._7z_exe        = os.path.join(application_path,'tools','7z.exe')
        self.password_file  = password_file or os.path.join(application_path,'modules',"PW.txt")
        self.passwords = self.load_passwords()
        if video_folder_path:
            self.video_folder_path = video_folder_path
        else:
            self.video_folder_path = os.path.join(application_path, "cover_video")  # 默认外壳文件存放路径
        print(f"外壳文件夹路径：{self.video_folder_path}")
        self.total_file_size                = None            # 被隐写文件/文件夹的总大小
        self.password                       = None            # 密码
        self.remaining_cover_video_files    = []              # 随机选择模式时的剩余外壳文件列表
        self.progress_callback              = None            # 进度条回调参数
        self.cover_video_path               = None            # 包含完整路径的外壳文件
        self.gui_enabled                    = gui_enabled     # 是否是GUI模式

    def initialize_cover_video_files(self):
        """随机选择模式-初始化剩余可用的外壳文件列表"""
        cover_video_files = [f for f in os.listdir(self.video_folder_path) if f.endswith(".mp4")]
        random.shuffle(cover_video_files)  # 随机排序
        self.remaining_cover_video_files = cover_video_files

    # GUI回调函数部分
    def set_progress_callback(self, callback):              # GUI进度条回调函数, callback代表自GUI传入的进度条函数
        self.progress_callback = callback

    def set_cover_video_duration_callback(self, callback):  # 外壳MP4文件回调函数
        self.cover_video_duration_callback = callback

    def set_log_callback(self, callback):   # GUI log方法回调函数, 把GUI的self.log方法(这里用callback指代)传给逻辑层, 逻辑层再借self.log_callback把log信息传回GUI
        self.log_callback = callback

    def read_in_chunks(self, file_object, chunk_size=1024*1024):
        while True:
            data = file_object.read(chunk_size)
            if not data:
                break
            yield data

    def log(self, message): 
        if self.gui_enabled == False: # CLI模式专属log方法
            print(message)
        else:
            self.log_callback(message)

    def choose_cover_video_file(self, cover_video_CLI=None, 
                                processed_files=None, 
                                output_cover_video_name_mode=None,
                                video_folder_path=None):
        # 外壳文件选择: CLI模式
        if cover_video_CLI:  # 如果指定了外壳文件名就使用之（CLI模式）绝对路径
            return cover_video_CLI

        # 外壳文件选择：GUI模式
        # 1. 检查cover_video中是否存在用来作为外壳的MP4文件（比如海绵宝宝之类, 数量任意, 每次随机选择）
        cover_video_files = [f for f in os.listdir(video_folder_path) if f.endswith(".mp4")]  # 按默认排序选择
        cover_video_files = natsorted(cover_video_files, alg=ns.PATH)
        if not cover_video_files:
            raise Exception(f"{video_folder_path} 文件夹下没有文件, 请添加文件后继续.")

        # 2. 否则在cover_video中选择
        if output_cover_video_name_mode == '===============随机选择模式===============':
            # 2-a. 随机选择一个外壳MP4文件用来隐写, 尽量不重复
            if not self.remaining_cover_video_files:
                self.initialize_cover_video_files()
            cover_video = self.remaining_cover_video_files.pop()
            print(output_cover_video_name_mode, cover_video)

        elif output_cover_video_name_mode == '===============时长顺序模式===============':
            # 2-b. 按时长顺序选择一个外壳MP4文件用来隐写
            cover_video_files = get_cover_video_files_info(video_folder_path, sort_by_duration=True)  # 按时长顺序选择
            cover_video = cover_video_files[processed_files % len(cover_video_files)]
            cover_video = cover_video[:cover_video.rfind('.mp4')] + '.mp4'  # 按最后一个.mp4切分, 以去除后续可能存在的时长大小等内容
            print(output_cover_video_name_mode, cover_video)

        elif output_cover_video_name_mode == '===============名称顺序模式===============':
            # 2-c. 按名称顺序选择一个外壳MP4文件用来隐写
            cover_video = cover_video_files[processed_files % len(cover_video_files)]
            print(output_cover_video_name_mode, cover_video)

        else:
            # 2-d. 根据下拉菜单选择外壳MP4文件
            cover_video = output_cover_video_name_mode
            cover_video = cover_video[:cover_video.rfind('.mp4')] + '.mp4'  # 按最后一个.mp4切分, 以去除后续可能存在的时长大小等内容
            print(f'下拉菜单模式, 视频信息: {output_cover_video_name_mode}')
        
        cover_video_path = os.path.join(video_folder_path, cover_video)
        print(f'cover_video_path: {cover_video_path}')
        return cover_video_path
        
    def compress_files(self, zip_file_path, input_file_path, processed_size=0, password=None):
        # 计算文件或文件夹的大小
        def get_file_or_folder_size(path):
            total_size = 0
            if os.path.isfile(path):
                total_size = os.path.getsize(path)
            elif os.path.isdir(path):
                for dirpath, dirnames, filenames in os.walk(path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        total_size += os.path.getsize(fp)
            return total_size

        # 计算文件或文件夹的 SHA-256 哈希值
        def compute_sha256(path):
            sha256_hash = hashlib.sha256()
            if os.path.isfile(path):
                with open(path, 'rb') as f:
                    for byte_block in iter(lambda: f.read(4096), b''):
                        sha256_hash.update(byte_block)
            elif os.path.isdir(path):
                # 对于文件夹，按照文件名排序，递归计算所有文件的哈希值并更新
                for root, dirs, files in os.walk(path):
                    for names in sorted(files):
                        filepath = os.path.join(root, names)
                        sha256_hash.update(names.encode())  # 更新文件名到哈希
                        with open(filepath, 'rb') as f:
                            for byte_block in iter(lambda: f.read(4096), b''):
                                sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()

        # 计算输入文件或文件夹的总大小
        self.total_file_size = get_file_or_folder_size(input_file_path)
        
        # 计算 SHA-256 哈希值
        sha256_value = compute_sha256(input_file_path)

        # 计算时间戳及其哈希值
        readable_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        time_hash =  hashlib.sha256(readable_time.encode()).hexdigest()
        
        # 准备要添加到 ZIP 注释中的信息
        zip_comment = f"SHA-256 Hash of '{os.path.basename(input_file_path)}':\n{sha256_value}\nTimestamp '{readable_time}'\nTimehash '{time_hash}'"

        if password:
            # 当设置了密码时，使用 pyzipper 进行 AES 加密
            zip_file = pyzipper.AESZipFile(zip_file_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES)
            zip_file.setpassword(password.encode())

            with zip_file:
                self.log(f"Compressing file with encryption: {input_file_path}\n较大的文件可能会花费较长时间...")

                # 收集所有需要压缩的文件
                file_list = []

                if os.path.isdir(input_file_path):
                    root_folder = os.path.basename(input_file_path)
                    for root, dirs, files in os.walk(input_file_path):
                        for file in files:
                            file_full_path = os.path.join(root, file)
                            arcname = os.path.join(root_folder, os.path.relpath(file_full_path, start=input_file_path))
                            file_list.append((file_full_path, arcname))
                else:
                    file_full_path = input_file_path
                    arcname = os.path.basename(input_file_path)
                    file_list.append((file_full_path, arcname))

                # 随机化文件列表顺序
                random.shuffle(file_list)

                for file_full_path, arcname in file_list:
                    # 随机选择压缩方法
                    compress_type = random.choice([pyzipper.ZIP_DEFLATED, pyzipper.ZIP_STORED])

                    # 将文件写入 ZIP 存档
                    zip_file.write(file_full_path, arcname=arcname, compress_type=compress_type)

                    # 更新已处理的大小并更新进度条
                    processed_size += os.path.getsize(file_full_path)
                    if self.progress_callback:
                        self.progress_callback(processed_size, self.total_file_size)

                # 设置 ZIP 文件的注释
                zip_file.comment = zip_comment.encode('utf-8')

        else:
            # 当未设置密码时，使用 zipfile 模块，这样可以设置 compresslevel 等
            zip_file = zipfile.ZipFile(zip_file_path, 'w')

            with zip_file:
                self.log(f"Compressing file without encryption: {input_file_path}\n较大的文件可能会花费较长时间...")

                # 收集所有需要压缩的文件
                file_list = []

                if os.path.isdir(input_file_path):
                    root_folder = os.path.basename(input_file_path)
                    for root, dirs, files in os.walk(input_file_path):
                        for file in files:
                            file_full_path = os.path.join(root, file)
                            arcname = os.path.join(root_folder, os.path.relpath(file_full_path, start=input_file_path))
                            file_list.append((file_full_path, arcname))
                else:
                    file_full_path = input_file_path
                    arcname = os.path.basename(input_file_path)
                    file_list.append((file_full_path, arcname))

                # 随机化文件列表顺序
                random.shuffle(file_list)

                for file_full_path, arcname in file_list:
                    # 随机选择压缩方法
                    compress_type = random.choice([zipfile.ZIP_DEFLATED, zipfile.ZIP_DEFLATED]) # , zipfile.ZIP_STORED

                    # 如果使用 ZIP_DEFLATED，随机选择压缩等级
                    if compress_type == zipfile.ZIP_DEFLATED:
                        compresslevel = random.randint(1, 9)  # 压缩等级 1-9
                    else:
                        compresslevel = None  # 对于 ZIP_STORED，压缩等级无效, 目前暂不启用

                    # 随机生成文件日期和时间
                    while True:
                        try:
                            date_time = (
                                random.randint(1980, 2099),  # 年
                                random.randint(1, 12),       # 月
                                random.randint(1, 28),       # 日
                                random.randint(0, 23),       # 时
                                random.randint(0, 59),       # 分
                                random.randint(0, 59)        # 秒
                            )
                            datetime.datetime(*date_time)
                            break
                        except ValueError:
                            continue

                    # 创建 ZipInfo 对象
                    zi = zipfile.ZipInfo(filename=arcname, date_time=date_time)
                    zi.compress_type = compress_type

                    # 将文件写入 ZIP 存档
                    if compresslevel is not None:
                        zip_file.write(file_full_path, arcname=arcname, compress_type=compress_type, compresslevel=compresslevel)
                    else:
                        zip_file.write(file_full_path, arcname=arcname, compress_type=compress_type)

                    # 更新已处理的大小并更新进度条
                    processed_size += os.path.getsize(file_full_path)
                    if self.progress_callback:
                        self.progress_callback(processed_size, self.total_file_size)

                # 设置 ZIP 文件的注释
                zip_file.comment = zip_comment.encode('utf-8')

    def hide_file(self, input_file_path, 
                  cover_video_CLI=None, 
                  password=None, 
                  processed_files=0, 
                  output_file_path=None, 
                  output_option=None, 
                  output_cover_video_name_mode=None,
                  type_option_var=None,
                  video_folder_path=None):

        self.type_option_var = type_option_var
        self.output_option = output_option
        self.output_cover_video_name_mode = output_cover_video_name_mode
        self.password = password
        self.video_folder_path = video_folder_path

        # 1. 隐写外壳文件选择
        cover_video_path = self.choose_cover_video_file(cover_video_CLI=cover_video_CLI, 
                                                        processed_files=processed_files, 
                                                        output_cover_video_name_mode=output_cover_video_name_mode,
                                                        video_folder_path=self.video_folder_path)
        print(f"实际隐写外壳文件：{cover_video_path}")
                
        # 2. 隐写的临时zip文件名
        zip_file_path = os.path.join(os.path.dirname(input_file_path), os.path.basename(input_file_path) + f"_hidden_{processed_files}.zip")
        
        # 3. 计算要压缩的文件总大小
        self.total_file_size = get_file_or_folder_size(input_file_path)
        print(f"要压缩的文件总大小: {self.total_file_size} bytes")
            
        processed_size = 0  # 初始化已处理的大小为0
        self.compress_files(zip_file_path, input_file_path, processed_size=processed_size, password=password)    # 创建隐写的临时zip文件

        try:        
            # 4.1. 隐写MP4文件的逻辑
            if self.type_option_var == 'mp4':
                # 指定输出文件名
                output_file = self.get_output_file_path(input_file_path, 
                                                        output_file_path, 
                                                        processed_files, 
                                                        self.output_option, 
                                                        self.output_cover_video_name_mode,
                                                        cover_video_path)

                self.log(f"Output file: {output_file}")
            
                try:
                    total_size_hidden = os.path.getsize(cover_video_path) + os.path.getsize(zip_file_path)
                    processed_size = 0
                    with open(cover_video_path, "rb") as file1:
                        with open(zip_file_path, "rb") as file2:
                            with open(output_file, "wb") as output:
                                self.log(f"Hiding file: {input_file_path}")

                                # 外壳 MP4 文件
                                self.log(f"Hiding cover video: {file1}")
                                for chunk in self.read_in_chunks(file1):
                                    output.write(chunk)
                                    processed_size += len(chunk)
                                    if self.progress_callback:
                                        self.progress_callback(processed_size, total_size_hidden)

                                # 生成 moov box 头部
                                moov_size = os.path.getsize(zip_file_path) + 8
                                if moov_size <= 4294967295: # 当zip文件大小小于4GB (2**32-1), 直接嵌入 moov box 中
                                    moov_header = b'moov' + moov_size.to_bytes(4, byteorder='big')
                                    output.write(moov_header)
                                else: # largesize
                                    moov_header = b'moov' + (1).to_bytes(4, byteorder='big')
                                    output.write(moov_header)
                                    output.write(moov_size.to_bytes(8, byteorder='big'))

                                # 压缩包 zip 文件
                                self.log(f"Hiding zip file: {file2}")
                                for chunk in self.read_in_chunks(file2):
                                    output.write(chunk)
                                    processed_size += len(chunk)
                                    if self.progress_callback:
                                        self.progress_callback(processed_size, total_size_hidden)

                                # 随机写入 2 种压缩文件特征码, 用来混淆网盘的检测系统
                                head_signatures = {
                                    "RAR4":  b'\x52\x61\x72\x21\x1A\x07\x00',
                                    "RAR5":  b'\x52\x61\x72\x21\x1A\x07\x01\x00',
                                    "7Z":    b'\x37\x7A\xBC\xAF\x27\x1C',
                                    "ZIP":   b'\x50\x4B\x03\x04',
                                    "GZIP":  b'\x1F\x8B',
                                    "BZIP2": b'\x42\x5A\x68',
                                    "XZ":    b'\xFD\x37\x7A\x58\x5A\x00',
                                }

                                # 添加随机压缩文件特征码
                                random_bytes = os.urandom(1024 * random.randint(5, 10))  # 20KB - 25KB 的随机字节
                                output.write(random.choice(list(head_signatures.values())))  # 随机压缩文件特征码
                                output.write(random_bytes)

                                output.write(random.choice(list(head_signatures.values())))  # 第二个压缩文件特征码
                                random_bytes = os.urandom(1024 * random.randint(5, 10))  # 20KB - 22KB 的随机字节
                                output.write(random_bytes)

                                # 添加 MP4 文件的结尾标记 (空的 "mdat" box)
                                add_empty_mdat_box(output)
                
                except Exception as e:
                    self.log(f"在写入MP4文件时发生未预料的错误: {str(e)}")
                    raise

            # 4.2. 隐写mkv文件的逻辑
            elif self.type_option_var == 'mkv':
                # 指定输出文件名
                output_file = self.get_output_file_path(input_file_path, 
                                                        output_file_path, 
                                                        processed_files, 
                                                        self.output_option, 
                                                        self.output_cover_video_name_mode,
                                                        cover_video_path)
                
                # 生成末尾随机字节
                random_data_path = f"temp_{generate_random_filename(length=16)}"
                try:
                    with open(random_data_path, "wb") as f:
                        random_bytes = os.urandom(1024*8)  # 8kb
                        f.write(random_bytes)

                    self.log(f"Output file: {output_file}")
                    cmd = [
                        self.mkvmerge_exe, '-o',
                        output_file, cover_video_path,
                        '--attach-file', zip_file_path,
                        '--attach-file', random_data_path,
                    ]
                    self.log(f"Hiding file: {input_file_path}")
                    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
                    
                    # 删除临时随机字节
                    os.remove(random_data_path)

                    if result.returncode != 0:
                        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)

                except subprocess.CalledProcessError as cpe:
                    self.log(f"隐写时发生错误: {str(cpe)}")
                    self.log(f'CalledProcessError output：{cpe.output}') if cpe.output else None
                    self.log(f'CalledProcessError stderr：{cpe.stderr}') if cpe.stderr else None
                    raise

                except Exception as e:
                    self.log(f"在执行mkvmerge时发生未预料的错误: {str(e)}")
                    raise

        except Exception as e:
            self.log(f"隐写时发生未预料的错误: {str(e)}")
            raise
        finally:
            # 5. 删除临时zip文件
            os.remove(zip_file_path)

        self.log(f"Output file created: {os.path.exists(output_file)}")

    # 隐写时指定输出文件名+路径的方法
    def get_output_file_path(self, input_file_path=None, 
                             output_file_path=None, 
                             processed_files=0, 
                             output_option=None, 
                             output_cover_video_name_mode=None,
                             cover_video_path=None,
                             ):

        # 输出文件名指定
        if output_file_path:
            return output_file_path # 如果指定了输出文件名就用输出文件名（CLI模式）

        print(f'type option: {self.type_option_var}')
        if self.type_option_var == 'mp4':
            print(f'input_file_path: {input_file_path}')
            print(f'cover_video_path: {cover_video_path}')

            # 输出文件名选择
            print(f'output_option: {output_option}')
            if output_option == '原文件名':
                if os.path.isdir(input_file_path):
                    output_file_path = input_file_path + f"_hidden_{processed_files+1}.mp4" # 当为文件夹时不存在扩展名
                else:
                    output_file_path = os.path.splitext(input_file_path)[0] + f"_hidden_{processed_files+1}.mp4"
            elif output_option == '外壳文件名':
                output_file_path = os.path.join(os.path.split(input_file_path)[0], 
                                                os.path.split(cover_video_path)[1].replace('.mp4', f'_{processed_files+1}.mp4')
                                                )
            elif output_option == '随机文件名':
                output_file_path = os.path.join(os.path.split(input_file_path)[0], 
                                        generate_random_filename(length=16) + f'_{processed_files+1}.mp4')
            print(f"output_file_path: {output_file_path}\n")    
        
        elif self.type_option_var == 'mkv':

            # 输出文件名选择
            print(f'output_option: {output_option}')
            if output_option == '原文件名':
                if os.path.isdir(input_file_path):
                    output_file_path = input_file_path + f"_hidden_{processed_files+1}.mkv" # 当为文件夹时不存在扩展名
                else:
                    output_file_path = os.path.splitext(input_file_path)[0] + f"_hidden_{processed_files+1}.mkv"
            elif output_option == '外壳文件名':
                output_file_path = os.path.join(os.path.split(input_file_path)[0], 
                                                os.path.split(cover_video_path)[1].replace('.mp4', f'_{processed_files+1}.mkv')
                                                )
            elif output_option == '随机文件名':
                output_file_path = os.path.join(os.path.split(input_file_path)[0], 
                                        generate_random_filename(length=16) + f'_{processed_files+1}.mkv')
            print(f"output_file_path: {output_file_path}\n")    
        
        return output_file_path    
    
    # 解除隐写部分

    ## 读取密码本
    def load_passwords(self):
        passwords = []
        if os.path.exists(self.password_file):
            with open(self.password_file, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if parts:
                        # 移除可能的 BOM 和其他不可打印字符
                        password = parts[0].strip().encode('ascii', 'ignore').decode('ascii')
                        if password:
                            passwords.append(password)
        return passwords
    
    def reveal_file(self, input_file_path, password=None, type_option_var=None):
        self.type_option_var = type_option_var

        # 添加调试信息
        self.log(f"Loaded passwords: {self.passwords}")
        self.log(f"User provided password: {password}")

        password_list = [password] if password else []
        password_list.extend(self.passwords)
        
        # 如果没有提供任何密码，添加空密码('')到列表中
        if not password_list:
            password_list.append('')

        if self.type_option_var == 'mp4':
            for test_password in password_list:
                try:
                    # 添加更多详细的调试信息
                    self.log(f"Attempting to reveal file with password: '{test_password}' (len: {len(test_password)})")

                    total_size_hidden = os.path.getsize(input_file_path)
                    processed_size = 0

                    with open(input_file_path, "rb") as file1:
                        with pyzipper.AESZipFile(file1) as zip_file:
                            # 仅当密码不为空时才设置密码
                            if test_password:
                                zip_file.setpassword(test_password.encode())
                            for name in zip_file.namelist():
                                output_file_path = os.path.join(os.path.dirname(input_file_path), name)
                                self.log(f"Attempting to create file: {output_file_path}")
                                os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
                                with zip_file.open(name) as source, open(output_file_path, 'wb') as output:
                                    for chunk in self.read_in_chunks(source):
                                        output.write(chunk)
                                        processed_size += len(chunk)
                                        if self.progress_callback:
                                            self.progress_callback(processed_size, total_size_hidden)

                    os.remove(input_file_path)
                    self.log(f"File extracted successfully with password: {test_password}")
                    return  # 成功解压后退出函数

                except (pyzipper.BadZipFile, ValueError, RuntimeError) as e:
                    self.log(f"无法解压文件 {input_file_path}, 使用密码 {test_password} 失败: {str(e)}")

            self.log("所有密码尝试失败，无法解压文件。")

        elif self.type_option_var == 'mkv':
            # 获取mkv附件id函数
            def get_attachment_name(input_file_path):
                cmd = [self.mkvinfo_exe, input_file_path]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding='utf-8')
                    lines = result.stdout.splitlines()
                    for idx, line in enumerate(lines):
                        if "MIME" in line:
                            parts = lines[idx-1].split(':')
                            attachments_name = parts[1].strip().split()[-1]
                            break
                except Exception as e:
                    self.log(f"获取附件时出错: {e}")
                    return None
                return attachments_name

            # 提取mkv附件
            def extract_attachment(input_file_path, output_path):
                cmd = [self.mkvextract_exe, 'attachments', input_file_path, f'1:{output_path}']
                try:
                    subprocess.run(cmd, check=True)
                except subprocess.CalledProcessError as e:
                    raise Exception(f"提取附件时出错: {e}")

            attachments_name = get_attachment_name(input_file_path)
            if attachments_name:
                output_path = os.path.join(os.path.dirname(input_file_path), attachments_name)
                self.log(f"Mkvextracting attachment file: {output_path}")
                try:
                    extract_attachment(input_file_path, output_path)

                    if attachments_name.endswith('.zip'):
                        zip_path = output_path
                        self.log(f"Extracting ZIP file: {zip_path}")

                        for test_password in password_list:
                            try:
                                with pyzipper.AESZipFile(zip_path, 'r', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zip_file:
                                    # 仅当密码不为空时才设置密码
                                    if test_password:
                                        zip_file.setpassword(test_password.encode())
                                    zip_file.extractall(os.path.dirname(input_file_path))
                                
                                os.remove(zip_path)
                                os.remove(input_file_path)
                                self.log(f"File extracted successfully with password: {test_password}")
                                return  # 成功解压后退出函数

                            except RuntimeError as e:
                                self.log(f"使用密码 {test_password} 解压失败: {e}")

                        self.log("所有密码尝试失败，无法解压文件。")

                    else:
                        self.log(f"提取附件 {attachments_name} 成功")
                        os.remove(input_file_path)

                except Exception as e:
                    self.log(f"提取附件 {attachments_name} 时出错: {e}")
            else:
                self.log("该 MKV 文件中没有可提取的附件。")

    def run_cli(self, args):
        # self.type_option_var = argparse.Namespace()
        # self.type_option_var.get = lambda: args.type # 模拟.get() 方法

        print(f"输入文件/文件夹路径: {args.input}")
        print(f"输出文件/文件夹路径: {args.output}")
        print(f"密码: {args.password}")
        print(f"输出文件类型: {args.type}")
        print(f"设定外壳MP4视频路径: {args.cover}")
        print(f"执行解除隐写: {args.reveal}")

        self.type_option_var = args.type
        
        if not args.reveal:
            if args.output:
                output_file = args.output
            else:
                input_file_name = os.path.splitext(os.path.basename(args.input))[0]
                output_file = f"{input_file_name}_hidden.{args.type}"
            
            self.hide_file(input_file_path=args.input, 
                           cover_video_CLI=args.cover, 
                           password=args.password, 
                           output_file_path=output_file, 
                           type_option_var=self.type_option_var)  # 调用hide_file方法
        else:
            self.reveal_file(input_file_path=args.input, 
                             password=args.password, 
                             type_option_var=self.type_option_var)  # 调用reveal_file方法

if __name__ == "__main__":
    # 修正CLI模式的编码问题
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8')
    else:
        print("sys.stdout is None")

    # 关于程序执行路径的问题
    if getattr(sys, 'frozen', False):  # 打包成exe的情况
        application_path = os.path.dirname(sys.executable)
    else:  # 在开发环境中运行
        application_path = os.path.dirname(__file__)

    parser = argparse.ArgumentParser(description='隐写者CLI')
    parser.add_argument('-i', '--input', default=None, help='指定输入文件或文件夹的路径')
    parser.add_argument('-o', '--output', default=None, help='1.指定输出文件名(包含后缀名) [或] 2.输出文件夹路径(默认为原文件名+"hidden")')
    parser.add_argument('-p', '--password', default='', help='设置密码 (默认无密码)')
    parser.add_argument('-t', '--type', default='mp4', choices=['mp4', 'mkv'], help='设置输出文件类型 (默认为mp4)')
    parser.add_argument('-c', '--cover', default=None, help='指定外壳MP4视频（默认在程序同路径下搜索）')
    parser.add_argument('-r', '--reveal', action='store_true', help='执行解除隐写')
    parser.add_argument('-pf', '--password-file', default=None, help='指定密码文件路径')

    args, unknown = parser.parse_known_args()

    if unknown:  # 假如没有指定参数标签, 那么默认第一个传入为 -i 参数
        args.input = unknown[0]

    if args.input:
        print('CLI')
        # 首先调整传入的参数
        # 1. 处理输出路径
        if args.output is None:
            # 1.1 如果没有指定输出文件路径, 则默认和输入文件同路径, 使用原文件名+"_hidden.mp4/mkv"
            input_dir = os.path.dirname(os.path.abspath(args.input))
            args.output = os.path.join(input_dir, f"{os.path.splitext(os.path.basename(args.input))[0]}_hidden.{args.type}")
        else:
            # 1.2. 如果指定了输出路径但不包含文件名, 仍使用原文件名+"_hidden.mp4/mkv"
            if os.path.splitext(args.output)[1] == '':
                input_filename = os.path.splitext(os.path.basename(args.input))[0]
                args.output = f"{os.path.join(args.output, input_filename)}_hidden.{args.type}"
            # 1.3. 其余情况则使用指定的输出文件名
            else:
                args.output = args.output

        # 2. 处理外壳MP4文件
        if args.cover is None:
            mp4list = []
            # 2.1 如果没有指定外壳视频路径, 则自动在程序同路径下的 cover_video 文件夹中寻找第一个文件
            cover_video_path = os.path.join(application_path, 'cover_video')
            if os.path.exists(cover_video_path):
                mp4list = [os.path.join(cover_video_path, item) for item in os.listdir(cover_video_path) if item.endswith('.mp4')]
            
            # 2.2 否则使用程序所在目录中的第一个mp4文件
            mp4list += [os.path.join(application_path, item) for item in os.listdir(application_path) if item.endswith('.mp4')]  # 程序所在目录
            
            # 2.3 假如以上都没找到,那么就在输入文件/目录所在目录下寻找
            if not mp4list:
                input_dir = os.path.dirname(os.path.abspath(args.input))  # 获取输入文件/文件夹的父目录
                mp4list += [os.path.join(input_dir, item) for item in os.listdir(input_dir) if item.endswith('.mp4')]  # 输入文件/目录所在目录

            if mp4list:
                args.cover = mp4list[0]
            else:
                print('请指定外壳MP4文件')
                exit(1)  # 退出程序

        # 3. 处理密码文件
        if args.password_file is None:
            args.password_file = os.path.join(application_path,"modules", "PW.txt")
        
        steganographier = Steganographier(password_file=args.password_file)
        steganographier.run_cli(args)
    else:
        print('GUI')
        SteganographierGUI()
