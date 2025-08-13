#!/bin/bash

# 数据标注平台启动脚本

echo "🚀 数据标注平台启动脚本"
echo "================================="

# 检查Python版本
echo "📋 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ Python版本: $PYTHON_VERSION"

# 检查是否需要安装依赖
echo "📦 检查依赖包..."
if ! python3 -c "import streamlit" &> /dev/null; then
    echo "⚠️  未检测到Streamlit，正在安装依赖..."
    pip3 install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "✅ 依赖安装完成"
    else
        echo "❌ 依赖安装失败，请手动运行: pip3 install -r requirements.txt"
        exit 1
    fi
else
    echo "✅ 依赖包已安装"
fi

# 创建必要的目录
echo "📁 创建必要目录..."
mkdir -p data
mkdir -p test_data/reports
mkdir -p test_data/scores
mkdir -p test_data/rubrics
echo "✅ 目录创建完成"

# 启动应用
echo "🌟 启动Streamlit应用..."
echo "📍 应用将在 http://localhost:8501 启动"
echo "🔄 按 Ctrl+C 停止应用"
echo "================================="

streamlit run streamlit_app.py
