# 在 AWS EC2 上部署 LitFinder

[English](deploy-ec2.md) | **简体中文**

本文用最低的成本把 LitFinder 部署到公网：一台小型 EC2 服务器运行现有的 Docker Compose 配置，前面加一个 [Caddy](https://caddyserver.com) 自动配置 HTTPS。所有操作都在 AWS 网页控制台完成，不需要安装 AWS CLI。

## 架构

```
浏览器 / MCP 客户端
      │  HTTPS (443)
      ▼
┌──────── EC2 t4g.small（Ubuntu 24.04，ARM，2 GB 内存 + 2 GB swap）────────┐
│  Caddy：HTTPS 证书、安全响应头                                            │
│   ├─ /mcp*   → 校验 Bearer token → mcp 容器 :8000                         │
│   └─ 其他路径 → web 容器 :5001（gunicorn + Flask + 重排模型）               │
│  backend/.env 和 deploy/.env：密钥和配置，只有你自己可读                     │
└──────────────────────────────────────────────────────────────────────────┘
安全组：80/443 对所有人开放；22 (SSH) 只对你的 IP 开放。
应用和 MCP server 都不对外暴露端口，只能经过 Caddy 访问。
```

生产环境新增的内容（`deploy/` 目录）：

| 组成部分 | 作用 |
|---|---|
| 用量限制（`backend/usage_limits.py`） | 每个会产生费用的接口都有"每个访客每小时"和"全站每天"两级上限；超过任意一个，接口返回 HTTP 429，并带上 `Retry-After` |
| `deploy/Caddyfile` | HTTPS、HTTP 自动跳转 HTTPS、安全响应头；`/mcp` 要求 `Authorization: Bearer <MCP_TOKEN>` |
| `deploy/docker-compose.prod.yml` | 加入 Caddy；取消应用对外暴露的端口；开启用量限制；信任 Caddy 传来的 `X-Forwarded-For`；禁止跨域调用 API；日志轮转 |
| `deploy/setup-server.sh` | 服务器一次性初始化：swap、从 Docker 官方 apt 源安装 Docker、防火墙、自动安全更新 |
| `deploy/deploy.sh` | 先检查配置文件，再构建并启动所有服务；也可以带上正确的配置文件执行任意 `docker compose` 命令 |

## 费用

以下是 us-west-2 / us-east-1 的大致按需价格，以 AWS 官网为准。

| 项目 | 每月 |
|---|---|
| EC2 t4g.small（2 vCPU、2 GB），全天运行 | 约 12.3 美元 |
| 公网 IPv4 地址（2024 年起单独收费） | 约 3.6 美元 |
| 20 GB gp3 硬盘 | 约 1.6 美元 |
| **服务器合计** | **约 17.5 美元** |
| API 费用（默认每日上限下的最坏情况） | OpenAI 每天不超过约 0.35 美元，另加论文分析；OpenAlex 每天不超过约 0.9 美元，在每天 1 美元的免费额度内 |

省钱的办法：

- **新账号赠送额度。** AWS 会给新账号发放赠送额度，可以抵扣前几个月的费用；具体以注册页面为准。
- **不用时停机。** 实例停止后只收硬盘和 IP 地址的钱，每月约 5 美元。
- **Lightsail。** 它 2 GB 的 Linux 套餐是固定价，约 12 美元/月，已含 IP 地址。下面的步骤在 Lightsail 的 Ubuntu 实例上同样适用。

### 默认用量上限

在 `backend/.env` 里用 `LIMIT_<名称>=<每个访客每小时>,<每个 UTC 日>` 设置；`0` 表示不限。

| 接口 | 配置项 | 默认值 | 单次费用 |
|---|---|---|---|
| `/api/search` 及其他流水线检索 | `LIMIT_SEARCH` | 每小时 20 次，每天 300 次 | 约 0.0014 美元 |
| `/api/agent-search` | `LIMIT_AGENT` | 每小时 10 次，每天 100 次 | 约 0.003–0.008 美元 |
| `/api/publication/<id>/analyze` | `LIMIT_ANALYZE` | 每小时 10 次，每天 50 次 | 一次 `LLM_MODEL` 调用 |
| `/api/publication/<id>` | `LIMIT_DETAILS` | 每小时 60 次，每天 1000 次 | 约 0.0001 美元 |

计数器保存在唯一的 gunicorn 进程的内存里，容器重启后清零。`GET /api/health_check` 会显示当天的用量。

## 1. 注册 AWS 账号（约 30 分钟）

1. 在 [aws.amazon.com](https://aws.amazon.com) 注册，需要一张银行卡和手机号。
2. **给 root 用户开启 MFA**（账号菜单 → Security credentials）。没有 MFA 的 root 密码一旦泄露，可能产生巨额账单。
3. **创建预算提醒：** Billing and Cost Management → Budgets → Create budget → Monthly cost budget，比如 20 美元，在 80% 和 100% 时发邮件提醒。
4. 选定一个区域并一直使用，比如 **us-west-2（俄勒冈）**。

## 2. 创建服务器（约 20 分钟）

EC2 → Launch instance：

| 设置 | 值 |
|---|---|
| 名称 | `litfinder` |
| 系统镜像 | Ubuntu Server 24.04 LTS，**64-bit (Arm)** |
| 实例类型 | `t4g.small` |
| 密钥对 | 新建一个（ED25519），把 `.pem` 文件下载到 `~/.ssh/` |
| 网络设置 | 新建安全组：SSH 来源选 **My IP**；HTTP 和 HTTPS 来源选任意位置 |
| 存储 | 20 GB gp3 |

然后给实例分配一个固定地址：EC2 → Elastic IPs → Allocate Elastic IP address → Actions → Associate，关联到 `litfinder` 实例。

在你自己的电脑上，把密钥文件改成只有你可读（否则 SSH 会拒绝使用）：

```bash
chmod 400 ~/.ssh/litfinder.pem
```

## 3. 选择访问地址

Caddy 需要一个主机名才能申请 HTTPS 证书。二选一：

- **免费、不用配置：** [sslip.io](https://sslip.io)。Elastic IP 是 `3.14.15.92` 的话，直接用 `3-14-15-92.sslip.io`，它已经解析到这个 IP。sslip.io 的域名和所有人共用 Let's Encrypt 的频率限制，偶尔会出现证书签发延迟。
- **自己的域名**（约 10 美元/年，比如在 Cloudflare Registrar 购买）：添加一条 A 记录，比如 `litfinder.example.com` 指向 Elastic IP。写在简历上更好看。

## 4. 配置服务器并启动 LitFinder（约 30 分钟）

登录服务器：

```bash
ssh -i ~/.ssh/litfinder.pem ubuntu@你的ElasticIP
```

拉取代码：

```bash
git clone https://github.com/LynnUoE/om-dissertation-implementation.git litfinder && cd litfinder
```

运行一次性初始化（swap、Docker、防火墙、自动安全更新）：

```bash
sudo bash deploy/setup-server.sh
```

退出并重新登录，让当前用户不用 `sudo` 也能运行 `docker`，然后再次 `cd litfinder`。

创建应用配置。建议为服务器**单独建一个 OpenAI project 和 API key**，并在 OpenAI 账单设置里关闭自动充值，这样即使 key 泄露，最多也只能花掉账户余额：

```bash
cp backend/.env.example backend/.env && nano backend/.env && chmod 600 backend/.env
```

至少要填 `OPENAI_API_KEY`、`OPENALEX_API_KEY` 和 `RESEARCHER_EMAIL`。`DEBUG`、`HOST`、`PORT` 会被 Docker Compose 覆盖。

创建部署配置（访问地址和 MCP token）。先生成一个随机 token：

```bash
openssl rand -hex 32
```

```bash
cp deploy/.env.example deploy/.env && nano deploy/.env && chmod 600 deploy/.env
```

构建并启动。第一次在服务器上构建大约需要 10–15 分钟：

```bash
deploy/deploy.sh
```

## 5. 检查

健康检查应该返回 `"status": "healthy"` 和当天的用量：

```bash
curl https://你的地址/api/health_check
```

- 用浏览器打开 `https://你的地址`，做一次检索。
- 不带 token 访问 `/mcp` 应该返回 401：

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://你的地址/mcp
```

- 在你自己电脑上的 Claude Code 里注册远程 MCP server：

```bash
claude mcp add --transport http litfinder-cloud https://你的地址/mcp --header "Authorization: Bearer 你的MCP_TOKEN"
```

## 6. 日常维护

| 事情 | 做法 |
|---|---|
| 更新到最新代码 | `git pull && deploy/deploy.sh` |
| 看日志 | `deploy/deploy.sh logs -f --tail 100 web`（每个容器的日志最多保留 3 × 10 MB） |
| 查看状态 | `deploy/deploy.sh ps` |
| 重启后自动恢复 | 自动：Docker 开机自启，容器设置了 `restart: unless-stopped` |
| 调整上限 | 修改 `backend/.env` 里的 `LIMIT_*`，再运行 `deploy/deploy.sh` |
| 暂停省钱 | EC2 → Instances → Stop；需要时再 Start（Elastic IP 不变） |
| 费用监控 | AWS Budgets 邮件、OpenAI 用量页面、`/api/health_check` 里的 `usage` |

**安全注意事项**

- SSH 只接受密钥登录（EC2 上 Ubuntu 的默认设置）。如果你的 IP 变了，要更新安全组里的 SSH 规则。
- `backend/.env` 和 `deploy/.env` 已被 git 忽略，永远不要提交。怀疑泄露时立即更换 API key。
- 防火墙（ufw）只放行 SSH、HTTP、HTTPS。Docker 对外发布的端口会绕过 ufw，所以生产配置只发布 Caddy 的端口。
- 应用没有用户账号体系。用量上限封顶了任何人能花掉的钱，但在上限之内，任何人都可以使用这个演示。

## 常见问题

| 现象 | 可能的原因 |
|---|---|
| 浏览器连不上 | 安全组没有放行 80/443，或者域名还没解析到 Elastic IP |
| 刚启动时证书报错 | Caddy 还在申请证书，查看 `deploy/deploy.sh logs caddy` |
| 构建被中断或服务器卡死 | 内存不足：用 `swapon --show` 确认 swap 已开启 |
| `web` 不停重启 | 查看 `deploy/deploy.sh logs web`，通常是 `backend/.env` 缺少 `OPENAI_API_KEY` |
| 提示 "The public demo has used today's ..." | 达到了每日上限，UTC 零点重置，或调高 `LIMIT_*` |
