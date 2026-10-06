#!/usr/bin/env bash
# ============================================================================
# 前后端分离计算器 —— 云服务器一键安装脚本（Ubuntu / Debian / CentOS / TencentOS / Alma 通用）
#
# 用法（在服务器上执行）：
#   cd /root && python3 -m zipfile -e calculator-vps.zip vps && cd vps && bash install.sh
#
# 它会做这些事：
#   1. 识别发行版与包管理器（apt / dnf / yum）
#   2. 安装 Python3 + venv + pip
#   3. 把 backend / frontend 复制到 /opt/calculator
#   4. 建虚拟环境并安装依赖（优先用清华 PyPI 镜像，失败自动回退官方源）
#   5. 注册成 systemd 服务并设置开机自启
#   6. 放行本机防火墙端口（云厂商的"安全组"需要你在控制台单独放行）
#
# 设计说明：只用 SQLite（存在服务器磁盘上，重启不丢），因此不需要外部数据库。
# ============================================================================
set -euo pipefail

APP_DIR=/opt/calculator
PORT="${PORT:-8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

log() { printf '\n\033[36m== %s ==\033[0m\n' "$*"; }
die() { printf '\n\033[31m[错误] %s\033[0m\n' "$*" >&2; exit 1; }

log "1/7 检查运行环境"
[ "$(id -u)" -eq 0 ] || die "请用 root 用户执行（腾讯云控制台的默认登录用户就是 root）"
command -v python3 >/dev/null 2>&1 || NEED_PY=1
if command -v apt-get >/dev/null 2>&1; then PKG=apt
elif command -v dnf >/dev/null 2>&1; then PKG=dnf
elif command -v yum >/dev/null 2>&1; then PKG=yum
else die "没识别出包管理器（只支持 apt / dnf / yum）"; fi
echo "  包管理器: $PKG"
echo "  Python  : $(python3 -V 2>/dev/null || echo '未安装，稍后安装')"

log "2/7 安装 Python3 与 venv"
if [ "$PKG" = apt ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip curl
else
    $PKG install -y python3 python3-pip curl || true
fi
command -v python3 >/dev/null 2>&1 || die "Python3 安装失败，请检查网络或镜像源"

log "3/7 复制代码到 $APP_DIR"
[ -d "$SCRIPT_DIR/backend" ] || die "找不到 $SCRIPT_DIR/backend，请确认解压目录正确"
[ -d "$SCRIPT_DIR/frontend" ] || die "找不到 $SCRIPT_DIR/frontend"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/backend" "$APP_DIR/frontend"
cp -r "$SCRIPT_DIR/backend" "$APP_DIR/backend"
cp -r "$SCRIPT_DIR/frontend" "$APP_DIR/frontend"
find "$APP_DIR/backend" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "  后端文件: $(find "$APP_DIR/backend" -type f | wc -l) 个"
echo "  前端文件: $(find "$APP_DIR/frontend" -type f | wc -l) 个"

log "4/7 建虚拟环境"
python3 -m venv "$APP_DIR/.venv" || {
    echo "  venv 创建失败，尝试安装 ensurepip 后重试…"
    if [ "$PKG" = apt ]; then apt-get install -y python3-venv; else $PKG install -y python3-pip; fi
    python3 -m venv "$APP_DIR/.venv"
}
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip -q

log "5/7 安装依赖（先试清华镜像，失败回退官方源）"
if ! "$APP_DIR/.venv/bin/pip" install -q -i "$MIRROR" -r "$APP_DIR/backend/requirements.txt"; then
    echo "  镜像安装失败，改用官方 PyPI…"
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

 如果浏览器打不开，多半是云厂商的「安全组」没放行 $PORT 端口：
   腾讯云控制台 → 轻量应用服务器/云服务器 → 防火墙/安全组 → 添加规则 → TCP $PORT 允许
============================================================================
EOF
