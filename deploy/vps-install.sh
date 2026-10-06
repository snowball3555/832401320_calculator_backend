#!/usr/bin/env bash
# ============================================================================
# 前后端分离计算器 —— 云服务器一键安装脚本
# 支持 Ubuntu / Debian / CentOS / TencentOS / AlmaLinux（自动识别包管理器）
#
# 两种用法都支持：
#   A) 仓库布局（推荐，克隆两个仓库后执行）
#      git clone https://github.com/<用户名>/832401320_calculator_backend.git backend
#      git clone https://github.com/<用户名>/832401320_calculator_frontend.git frontend
#      sudo bash backend/deploy/vps-install.sh
#   B) 压缩包布局（install.sh 与 backend/ frontend/ 同级）
#      bash install.sh
#   也可以显式指定目录：bash vps-install.sh /path/to/backend /path/to/frontend
#
# 它会：装 Python3 → 复制代码到 /opt/calculator → 建虚拟环境 → 装依赖（清华镜像加速）
#      → 注册 systemd 开机自启 → 放行本机防火墙 → 自检并打印访问地址
# 数据库使用服务器磁盘上的 SQLite，重启不丢数据，无需外部数据库。
# ============================================================================
set -euo pipefail

APP_DIR=/opt/calculator
PORT="${PORT:-8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
BACKEND_DIR=""
FRONTEND_DIR_SRC=""

log() { printf '\n\033[36m== %s ==\033[0m\n' "$*"; }
die() { printf '\n\033[31m[错误] %s\033[0m\n' "$*" >&2; exit 1; }

is_frontend() { [ -f "$1/index.html" ] && [ -d "$1/js" ]; }
is_backend()  { [ -d "$1/app" ] && [ -f "$1/requirements.txt" ]; }

log "1/7 定位代码目录"
if [ "$#" -ge 2 ]; then
    BACKEND_DIR="$1"; FRONTEND_DIR_SRC="$2"
elif is_backend "$SCRIPT_DIR/backend" && is_frontend "$SCRIPT_DIR/frontend"; then
    BACKEND_DIR="$SCRIPT_DIR/backend"; FRONTEND_DIR_SRC="$SCRIPT_DIR/frontend"
else
    # 仓库布局：脚本位于后端仓库的 deploy/ 下
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    if is_backend "$REPO_ROOT"; then
        BACKEND_DIR="$REPO_ROOT"
        PARENT="$(cd "$REPO_ROOT/.." && pwd)"
        for CAND in "$PARENT/frontend" "$PARENT"/*_calculator_frontend "$PARENT"/*frontend; do
            if [ -d "$CAND" ] && is_frontend "$CAND"; then FRONTEND_DIR_SRC="$(cd "$CAND" && pwd)"; break; fi
        done
    fi
fi
[ -n "$BACKEND_DIR" ] && is_backend "$BACKEND_DIR" || die "找不到后端目录（应含 app/ 与 requirements.txt）。可用：bash $0 /路径/backend /路径/frontend"
[ -n "$FRONTEND_DIR_SRC" ] && is_frontend "$FRONTEND_DIR_SRC" || die "找不到前端目录（应含 index.html 与 js/）。可用：bash $0 /路径/backend /路径/frontend"
echo "  后端: $BACKEND_DIR"
echo "  前端: $FRONTEND_DIR_SRC"

log "2/7 检查运行环境"
[ "$(id -u)" -eq 0 ] || die "请用 sudo 执行：sudo bash $0"
if command -v apt-get >/dev/null 2>&1; then PKG=apt
elif command -v dnf >/dev/null 2>&1; then PKG=dnf
elif command -v yum >/dev/null 2>&1; then PKG=yum
else die "没识别出包管理器（只支持 apt / dnf / yum）"; fi
echo "  包管理器: $PKG"

log "3/7 安装 Python3 与 venv"
if [ "$PKG" = apt ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip curl
else
    $PKG install -y python3 python3-pip curl || true
fi
command -v python3 >/dev/null 2>&1 || die "Python3 安装失败，请检查网络或镜像源"
echo "  $(python3 -V)"

log "4/7 复制代码到 $APP_DIR"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/backend" "$APP_DIR/frontend"
cp -r "$BACKEND_DIR" "$APP_DIR/backend"
cp -r "$FRONTEND_DIR_SRC" "$APP_DIR/frontend"
find "$APP_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$APP_DIR" -name '.git' -maxdepth 3 -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "  后端文件: $(find "$APP_DIR/backend" -type f | wc -l) 个"
echo "  前端文件: $(find "$APP_DIR/frontend" -type f | wc -l) 个"

log "5/7 建虚拟环境并安装依赖"
python3 -m venv "$APP_DIR/.venv" || {
    echo "  venv 创建失败，补装组件后重试…"
    if [ "$PKG" = apt ]; then apt-get install -y python3-venv; else $PKG install -y python3-pip; fi
    python3 -m venv "$APP_DIR/.venv"
}
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip -q
if ! "$APP_DIR/.venv/bin/pip" install -q -i "$MIRROR" -r "$APP_DIR/backend/requirements.txt"; then
    echo "  清华镜像失败，改用官方 PyPI…"
    "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/backend/requirements.txt"
fi
"$APP_DIR/.venv/bin/python" -c "import fastapi, uvicorn, sqlalchemy, pydantic; print('  依赖就绪: fastapi', fastapi.__version__, '| sqlalchemy', sqlalchemy.__version__)"

log "6/7 注册 systemd 服务（开机自启）"
cat > /etc/systemd/system/calculator.service <<EOF
[Unit]
Description=Front-back separated calculator (FastAPI + static frontend)
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR/backend
Environment=HOST=0.0.0.0
Environment=PORT=$PORT
Environment=FRONTEND_DIR=$APP_DIR/frontend
Environment=DATABASE_URL=sqlite:///$APP_DIR/backend/calculator.db
Environment=TIMEZONE_OFFSET=8
Environment=CORS_ORIGINS=*
ExecStart=$APP_DIR/.venv/bin/python run.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable calculator >/dev/null 2>&1 || true
systemctl restart calculator
sleep 4

log "7/7 放行本机防火墙并自检"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "$PORT/tcp" >/dev/null 2>&1 || true
    echo "  已放行 ufw $PORT/tcp"
fi
if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-port="$PORT/tcp" >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
    echo "  已放行 firewalld $PORT/tcp"
fi

if curl -fsS "http://127.0.0.1:$PORT/api/health"; then
    echo
    echo "  服务自检通过 ✓"
else
    echo
    echo "  [警告] 本机自检失败，请看日志：journalctl -u calculator -n 50 --no-pager"
fi

PUBLIC_IP="$(curl -fsS --max-time 8 https://ifconfig.me 2>/dev/null || echo '<公网IP>')"
cat <<EOF

============================================================================
 安装完成

 访问地址：  http://${PUBLIC_IP}:${PORT}
 接口文档：  http://${PUBLIC_IP}:${PORT}/docs
 健康检查：  http://${PUBLIC_IP}:${PORT}/api/health

 常用命令：
   查看状态   systemctl status calculator
   查看日志   journalctl -u calculator -f
   重启服务   systemctl restart calculator

 浏览器打不开 → 多半是云厂商「安全组/防火墙」没放行 $PORT 端口：
   腾讯云控制台 → 服务器 → 防火墙/安全组 → 添加规则 → TCP $PORT 允许
============================================================================
EOF
