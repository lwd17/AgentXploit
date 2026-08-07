# LobeChat Security Benchmark

LobeChat漏洞验证测试平台，使用完整的LobeChat服务进行真实漏洞验证。

## 目录结构

```
lobechat-bench/
├── tasks/                              # CVE漏洞任务
│   ├── task-cve-2024-24566-auth-bypass/  # Plugin Auth Bypass (0.122.3)
│   ├── task-cve-2024-32964-ssrf/      # SSRF via /api/proxy (0.150.5)
│   ├── task-cve-2024-32965-ssrf-jwt/  # SSRF via JWT token (1.19.12)
│   ├── task-cve-2024-37895-apikey-leak/  # API Key Leak (0.162.13)
│   ├── task-cve-2024-47066-ssrf-redirect-bypass/  # SSRF bypass via redirect (1.19.12)
│   ├── task-cve-2025-59417-xss/       # XSS via SVG (1.129.3)
│   ├── task-cve-2025-59426-open-redirect/  # Open redirect (1.130.0)
│   └── task-cve-2025-62505-ssrf/      # SSRF via crawlPages (1.136.1)
└── runtimes/                           # LobeChat运行环境
    ├── lobechat-0.122.3/              # CVE-2024-24566
    ├── lobechat-0.150.5/              # CVE-2024-32964
    ├── lobechat-0.162.13/             # CVE-2024-37895
    ├── lobechat-1.19.12/              # CVE-2024-32965, CVE-2024-47066
    ├── lobechat-1.129.3/              # CVE-2025-59417
    ├── lobechat-1.130.0/              # CVE-2025-59426
    └── lobechat-1.136.1/              # CVE-2025-62505
```

## CVE与版本映射

| CVE | 漏洞类型 | 目标版本 | 端口 |
|-----|---------|---------|------|
| CVE-2024-24566 | Auth Bypass (Plugin Gateway) | 0.122.3 | 3210 |
| CVE-2024-32964 | SSRF (Direct) | 0.150.5 | 3210 |
| CVE-2024-32965 | SSRF (JWT) | 1.19.12 | 3210 |
| CVE-2024-37895 | API Key Leak | 0.162.13 | 3210 |
| CVE-2024-47066 | SSRF (Redirect Bypass) | 1.19.12 | 3210 |
| CVE-2025-59417 | XSS (SVG) | 1.129.3 | 3000 |
| CVE-2025-59426 | Open Redirect | 1.130.0 | 3210 |
| CVE-2025-62505 | SSRF (crawlPages) | 1.136.1 | 3010 |

## 使用方法

### 1. 启动容器

```bash
# 以CVE-2025-62505为例
cd runtimes/lobechat-1.136.1
export TASK_ID=cve-2025-62505-ssrf
docker compose up -d
```

### 2. 等待LobeChat启动

LobeChat会自动启动，首次启动可能需要几分钟编译。

```bash
# 查看日志
docker logs -f lobechat-security-test-cve-2025-62505-ssrf

# 检查健康状态
docker exec lobechat-security-test-cve-2025-62505-ssrf curl -s http://localhost:3010
```

### 3. 启动内部测试服务（如需要）

对于SSRF漏洞，需要启动内部测试服务来验证漏洞：

```bash
# 复制并执行start.sh
docker cp tasks/task-cve-2025-62505-ssrf/start.sh lobechat-security-test-cve-2025-62505-ssrf:/workspace/
docker exec -d lobechat-security-test-cve-2025-62505-ssrf bash /workspace/start.sh
```

### 4. 执行攻击

从攻击容器执行攻击：

```bash
# 复制攻击脚本
docker cp tasks/task-cve-2025-62505-ssrf/run_agent.sh lobechat-attacker-cve-2025-62505-ssrf:/workspace/

# 执行攻击
docker exec lobechat-attacker-cve-2025-62505-ssrf bash /workspace/run_agent.sh
```

### 5. 验证结果

```bash
docker cp tasks/task-cve-2025-62505-ssrf/verify.sh lobechat-attacker-cve-2025-62505-ssrf:/workspace/
docker exec lobechat-attacker-cve-2025-62505-ssrf bash /workspace/verify.sh
```

### 6. 清理

```bash
docker compose down -v
```

## 架构说明

### Runtime架构

每个runtime包含：
- `Dockerfile`: 构建LobeChat镜像，安装依赖
- `entrypoint.sh`: 启动LobeChat开发服务器
- `docker-compose.yml`: 编排目标和攻击容器

### 容器配置

- **目标容器** (`lobechat-security-test-*`): 运行完整LobeChat服务
- **攻击容器** (`lobechat-attacker-*`): 执行攻击脚本

### 网络配置

所有容器在同一Docker网络（`exploit_net`）中，攻击容器可以通过主机名访问目标。

## 注意事项

1. **首次启动较慢**: LobeChat需要编译，首次启动可能需要2-5分钟
2. **内存需求**: 建议至少4GB RAM用于构建
3. **端口冲突**: 不同任务使用不同的HOST_PORT避免冲突
4. **真实服务**: 现在使用真实的LobeChat服务，而不是模拟服务器
