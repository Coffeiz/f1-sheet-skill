#!/usr/bin/env bash
# F1 Chart Toolkit — 一键安装依赖
# Python 依赖：pip
# 系统依赖：ffmpeg（librsvg 矢量栅格化，缺了 PNG 会失效但 SVG 仍可用）
set -e
echo "[1/2] 安装 Python 依赖..."
pip install -r requirements.txt
echo "[2/2] 检查 ffmpeg..."
if command -v ffmpeg &>/dev/null; then
    echo "  ffmpeg 已安装: $(ffmpeg -version | head -1)"
else
    echo "  警告：ffmpeg 未找到，PNG 无法生成（SVG 仍可用）"
    echo "  安装方式："
    echo "    macOS:  brew install ffmpeg"
    echo "    Ubuntu: sudo apt install ffmpeg"
    echo "    Windows: 下载 https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
fi
echo "安装完成 ✅"
