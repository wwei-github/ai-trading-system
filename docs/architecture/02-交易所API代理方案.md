# 02 交易所 API 代理方案

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-08-14 |
| 状态 | 待实现 |

---

## 目录

1. [背景与问题](#1-背景与问题)
2. [整体架构](#2-整体架构)
3. [代理方案对比](#3-代理方案对比)
4. [技术方案：Docker Proxy 容器](#4-技术方案docker-proxy-容器)
5. [配置说明](#5-配置说明)
6. [部署验证](#6-部署验证)
7. [风险与应对](#7-风险与应对)

---

## 1. 背景与问题

### 1.1 现状

系统依赖 Binance 等境外交易所 API 获取行情数据。当前代码已支持通过 `EXCHANGE_PROXY` 环境变量配置代理：

- [backend/app/core/config.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/core/config.py#L103-L106) — 定义 `EXCHANGE_PROXY` 配置项
- [backend/app/exchange/ccxt_client.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/exchange/ccxt_client.py#L72-L75) — CCXT 客户端使用代理
- [backend/app/exchange/ccxt_base.py](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/exchange/ccxt_base.py#L54-L56) — 交易所适配器基类使用代理

### 1.2 问题

| 问题 | 说明 |
|------|------|
| 大陆网络限制 | Binance API 域名被 DNS 污染 / SNI 阻断，无法直接访问 |
| Docker 网络隔离 | 容器内 `127.0.0.1:7890` 指向容器自身，而非宿主机的本地代理 |
| 依赖外部代理 | 用户需自行搭建 Shadowsocks / V2Ray / Clash 等代理服务 |
| 缺乏统一入口 | 后端、Celery Worker、Celery Beat 都需要配置代理，分散管理 |

### 1.3 目标

- 统一代理入口，Docker 部署自动生效
- 本地开发保持向后兼容
- 用户只需提供代理地址，无需修改代码
- 支持所有 CCXT 交易所（Binance、OKX、Bybit 等）

---

## 2. 整体架构

### 2.1 数据流

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐     ┌─────────────┐
│   Backend   │────▶│  tinyproxy   │────▶│  Upstream     │────▶│  Binance    │
│  (CCXT)     │     │  :8888       │     │  Proxy (用户) │     │  API        │
│  Celery     │     │  (容器内)     │     │  Shadowsocks  │     │  api.binance│
│  Worker     │     │              │     │  / V2Ray /    │     │  .com       │
└─────────────┘     └──────────────┘     │  Clash 等     │     └─────────────┘
                                         └───────────────┘
```

### 2.2 两种部署模式

```
┌─────────────────────────────────────────────────────────────────────┐
│  本地开发 (RUN_MODE=local)                                           │
│                                                                     │
│  Backend ──▶ EXCHANGE_PROXY=http://127.0.0.1:7890 ──▶ 用户本地代理  │
│             (用户自行启动 Clash/V2Ray 等)                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Docker 部署 (RUN_MODE=docker)                                      │
│                                                                     │
│  Backend ──▶ http://proxy:8888 ──▶ tinyproxy ──▶ 用户配置的上游代理  │
│              (容器内自动路由)               (PROXY_UPSTREAM)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 代理方案对比

| 方案 | 复杂度 | 灵活性 | 维护成本 | 适用场景 |
|------|--------|--------|----------|----------|
| **A: Docker Proxy 容器** | 低 | 高 | 低 | **推荐**：统一管理，Docker 原生 |
| B: 后端内置反向代理 | 中 | 中 | 中 | 需自定义逻辑时 |
| C: 宿主机端口转发 | 低 | 低 | 低 | 临时方案 |
| D: 环境变量直连 | 无 | 低 | 无 | 已有外部代理 |

### 3.1 方案 A：Docker Proxy 容器（推荐）

在 Docker 栈中新增 `tinyproxy` 容器，所有后端流量通过该容器转发。

**优点：**
- 统一管理，无需修改后端代码
- 支持上游代理链（用户可配置自有代理）
- 容器化部署，无需额外运维
- 对 CCXT 透明（只需改 `EXCHANGE_PROXY` 地址）

### 3.2 方案 B：后端内置反向代理

在后端新增 `/api/v1/proxy/binance/*` 路由，转发到 Binance API。

**优点：**
- 可添加缓存、限流、熔断等逻辑
- 对前端透明

**缺点：**
- 增加后端复杂度
- 需自行实现 WebSocket 代理
- 只适用于 Binance，其他交易所需重复实现

### 3.3 方案选择

**选择方案 A**，理由：
1. 当前 CCXT 代码已支持代理配置，无需修改
2. 透明代理，所有交易所（Binance、OKX、Bybit 等）统一生效
3. 支持 WebSocket 代理（通过 HTTP CONNECT 隧道）
4. 容器化部署，与现有 Docker 栈无缝集成

---

## 4. 技术方案：Docker Proxy 容器

### 4.1 容器选择：tinyproxy

**tinyproxy** 是一个轻量级 HTTP/HTTPS 代理服务器，特点：
- 资源占用极小（~2MB 内存）
- 支持 HTTP CONNECT 隧道（用于 HTTPS/WebSocket）
- 支持上游代理链
- 配置简单，单文件

### 4.2 Docker Compose 配置

在 [docker-compose.yml](file:///Users/wangwei/Documents/个人项目/ai-trading-system/docker-compose.yml) 中新增 `proxy` 服务：

```yaml
  # 交易所 API 代理（tinyproxy）
  # 用于在大陆等受限网络环境下访问境外交易所 API
  proxy:
    image: vimagick/tinyproxy:latest
    ports:
      - "18888:8888"
    volumes:
      - ./docker/tinyproxy.conf:/etc/tinyproxy/tinyproxy.conf
    environment:
      # 上游代理（可选，用户自有的 Shadowsocks/V2Ray/Clash 等代理地址）
      # 格式: http://user:pass@host:port 或 socks5://host:port
      # 留空则 tinyproxy 直连目标服务器
      UPSTREAM_PROXY: ${PROXY_UPSTREAM:-}
    restart: unless-stopped
```

### 4.3 tinyproxy 配置文件

**新增文件：** [docker/tinyproxy.conf](file:///Users/wangwei/Documents/个人项目/ai-trading-system/docker/tinyproxy.conf)

```conf
# tinyproxy 配置
User tinyproxy
Group tinyproxy

# 监听端口
Port 8888

# 允许所有容器内网访问
Allow 0.0.0.0/0

# 超时设置
Timeout 60
ConnectTimeout 30
ReadTimeout 60

# 连接数限制
MaxClients 100
MaxRequestsPerChild 0

# 日志级别
LogLevel Info
Syslog On

# 隐藏代理头
ViaProxyName "no"

# 上游代理配置（通过环境变量注入）
# 格式: server upstream_host:upstream_port
# 如果 UPSTREAM_PROXY 非空，会自动追加到此配置文件
```

### 4.4 后端配置更新

#### 4.4.1 本地开发模式

用户在自己的机器上启动 Clash/V2Ray 等代理后，在 `backend/.env` 中配置：

```ini
EXCHANGE_PROXY=http://127.0.0.1:7890
```

#### 4.4.2 Docker 模式

在 `docker-compose.yml` 中，后端容器强制使用内部代理地址：

```yaml
  backend:
    environment:
      RUN_MODE: docker
      # ... 其他配置 ...
      EXCHANGE_PROXY: http://proxy:8888

  celery-worker:
    environment:
      RUN_MODE: docker
      EXCHANGE_PROXY: http://proxy:8888

  celery-beat:
    environment:
      RUN_MODE: docker
      EXCHANGE_PROXY: http://proxy:8888
```

### 4.5 上游代理链

如果用户已有自己的代理服务（如 Shadowsocks），可通过 `PROXY_UPSTREAM` 环境变量配置：

```bash
# docker-compose 启动时指定
PROXY_UPSTREAM=http://127.0.0.1:7890 docker-compose up -d

# 或写入 .env 文件
PROXY_UPSTREAM=http://your-proxy-server:1080
```

**注意：** 在 Docker 环境下，`127.0.0.1` 指向容器自身。如果代理在宿主机上运行，需使用：
- macOS: `host.docker.internal:7890`
- Linux: 宿主机的实际 IP 地址，或 `172.17.0.1`（默认 Docker 网桥）

### 4.6 Docker 模式下的流量路径

```
Backend (CCXT) ──▶ http://proxy:8888 ──▶ tinyproxy
                                             │
                                     ┌───────┴───────┐
                                     │               │
                              PROXY_UPSTREAM    无上游代理
                              非空                (空)
                                     │               │
                                 上游代理         直连目标
                               (Shadowsocks/     (Binance API
                                V2Ray/Clash)      api.binance.com)
```

---

## 5. 配置说明

### 5.1 环境变量清单

| 变量 | 本地开发 | Docker | 说明 |
|------|----------|--------|------|
| `EXCHANGE_PROXY` | `http://127.0.0.1:7890` | `http://proxy:8888`（自动） | 交易所 API 代理地址 |
| `PROXY_UPSTREAM` | 空 | `http://host.docker.internal:7890` | 上游代理（可选） |

### 5.2 本地开发配置

**步骤：**
1. 在宿主机启动 Clash/V2Ray/Shadowsocks 等代理服务（假设端口 7890）
2. 在 `backend/.env` 中配置：
   ```ini
   EXCHANGE_PROXY=http://127.0.0.1:7890
   ```
3. 启动后端（`uvicorn app.main:app`），CCXT 会自动通过代理访问交易所

### 5.3 Docker 部署配置

**场景 A：用户在宿主机有代理服务**

```bash
# macOS
PROXY_UPSTREAM=http://host.docker.internal:7890 docker-compose up -d

# Linux（宿主机 IP 假设为 192.168.1.100）
PROXY_UPSTREAM=http://192.168.1.100:7890 docker-compose up -d
```

**场景 B：用户无代理服务，但基于海外的服务器部署**

不需要代理，直接设置 `EXCHANGE_PROXY` 为空即可。

**场景 C：用户使用公共代理服务**

```bash
PROXY_UPSTREAM=http://user:pass@proxy-service.com:1080 docker-compose up -d
```

### 5.4 验证代理是否生效

```bash
# 进入后端容器，测试通过代理访问 Binance
docker exec -it ai-trading-system-backend-1 bash
curl -x http://proxy:8888 https://api.binance.com/api/v3/ping

# 预期响应: {}
```

---

## 6. 部署验证

### 6.1 启动验证

```bash
# 启动所有服务
docker-compose up -d

# 检查 proxy 容器状态
docker-compose ps proxy

# 查看日志
docker-compose logs proxy

# 测试代理连通性
curl -x http://localhost:18888 https://api.binance.com/api/v3/ping
```

### 6.2 功能验证

| 测试项 | 方法 | 预期 |
|--------|------|------|
| 币种行情 | 访问 `GET /api/v1/coins/top` | 返回 Top100 行情 |
| K 线数据 | 访问 `GET /api/v1/coins/BTC-USDT/klines` | 返回 K 线数据 |
| 交易所连接测试 | 系统设置 → 交易所管理 → 测试连接 | 连接成功 |

### 6.3 性能影响

| 指标 | 无代理 | 有代理（tinyproxy） | 说明 |
|------|--------|---------------------|------|
| 延迟增加 | 0ms | ~5ms | tinyproxy 转发开销极小 |
| 额外内存 | 0 | ~5MB | tinyproxy 常驻内存 |
| 额外 CPU | 0 | 可忽略 | 纯转发，无计算 |

---

## 7. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 上游代理不稳定 | 行情数据延迟/失败 | 后端有 30s Redis 缓存 + 降级提示 |
| 代理容器故障 | 所有交易所请求失败 | docker-compose 设置 `restart: unless-stopped` |
| 代理地址泄露 | 代理被滥用 | tinyproxy 只监听容器内网，不暴露到公网 |
| 无法连接上游代理 | 请求失败 | 留空 `PROXY_UPSTREAM` 可直连（仅海外服务器可用） |
| WebSocket 代理 | 实时行情中断 | HTTP CONNECT 隧道天然支持 WebSocket |

---

## 附录：CCXT 代理配置原理

CCXT 库支持通过 `httpsProxy` / `httpProxy` / `socksProxy` 配置项指定代理：

```python
# CCXT 官方文档：代理配置
exchange = ccxt.binance({
    'httpsProxy': 'http://proxy:8888',  # 代理地址
    'httpProxy': 'http://proxy:8888',   # HTTP 代理
    'socksProxy': 'socks5://proxy:1080', # SOCKS5 代理
})
```

当前代码已封装此配置：

- [CCXTClient](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/exchange/ccxt_client.py#L72-L75)：
  ```python
  if settings.EXCHANGE_PROXY:
      config["httpsProxy"] = settings.EXCHANGE_PROXY
  ```

- [CCXTBaseAdapter](file:///Users/wangwei/Documents/个人项目/ai-trading-system/backend/app/exchange/ccxt_base.py#L54-L56)：
  ```python
  if settings.EXCHANGE_PROXY:
      config["httpsProxy"] = settings.EXCHANGE_PROXY
  ```