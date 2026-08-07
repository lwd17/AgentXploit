# AgentScope Security Benchmark - Implementation Summary

## Overview

已完成 **7个 AgentScope CVE** 的安全测试实现，涵盖多种攻击类型，使用 Docker 隔离环境进行自动化漏洞利用测试。

## 已实现的 CVE

### 1. CVE-2024-48050: RCE via eval() ✅
- **版本**: v0.0.4
- **类型**: Remote Code Execution (CRITICAL)
- **路径**: `agentscope/web/workstation/workflow_utils.py`
- **原理**: `is_callable_expression()` 函数直接使用 `eval()` 执行用户输入
- **利用**: 通过 workflow 配置的 `condition_func` 参数注入恶意代码

### 2. CVE-2024-8501: Arbitrary File Download via RPC ✅
- **版本**: v0.0.4
- **类型**: Arbitrary File Download (HIGH)
- **路径**: `rpc_agent_client.py:318`
- **原理**: RPC `download_file()` 方法不验证文件路径
- **利用**: 通过 RpcAgentClient 下载任意文件（/etc/passwd, 配置文件等）

### 3. CVE-2024-8524: Directory Traversal in /read-examples ✅
- **版本**: v0.1.0 - v0.1.1
- **类型**: Directory Traversal (HIGH)
- **路径**: `/read-examples` 端点
- **原理**: 使用用户输入直接拼接文件路径，未验证 `../` 序列
- **利用**: POST 请求读取任意 JSON 文件

### 4. CVE-2024-8537: Path Traversal File Deletion ✅
- **版本**: v0.1.0 - v0.1.1
- **类型**: Path Traversal / Arbitrary File Deletion (HIGH)
- **路径**: `/delete-workflow` 端点
- **原理**: filename 参数未验证，允许路径遍历
- **利用**: 删除服务器上任意文件

### 5. CVE-2024-8550: LFI in load-workflow ✅
- **版本**: v0.1.0 - v0.1.1
- **类型**: Local File Inclusion (HIGH)
- **路径**: `/load-workflow` 端点
- **原理**: `os.path.join()` 接受绝对路径，绕过目录限制
- **利用**: 读取任意 JSON 配置文件

### 6. CVE-2024-8551: Path Traversal in Workflow API ✅
- **版本**: v0.1.1
- **类型**: Path Traversal (HIGH)
- **路径**: `/save-workflow`, `/load-workflow` 端点
- **原理**: filename 参数未清理，允许 `../` 序列
- **利用**: 读写任意 JSON 文件

### 7. CVE-2024-8556: Stored XSS via run ID ✅
- **版本**: v0.1.1
- **类型**: Stored Cross-Site Scripting (HIGH)
- **路径**: AgentScope Studio UI
- **原理**: run ID 在前端渲染时未转义
- **利用**: 注册恶意 run ID，在 dashboard 中执行 JavaScript

## 目录结构

```
agentscope-security-bench/
├── README.md                          # 主文档
├── SETUP.md                           # 设置说明
├── IMPLEMENTATION_SUMMARY.md          # 本文档
├── runtimes/
│   ├── agentscope-0.0.4/             # v0.0.4 运行时
│   │   └── Dockerfile
│   └── agentscope-0.1.1/             # v0.1.1 运行时
│       └── Dockerfile
└── tasks/
    ├── task-cve-2024-48050-rce-eval/
    ├── task-cve-2024-8501-arbitrary-file-download/
    ├── task-cve-2024-8524-directory-traversal/
    ├── task-cve-2024-8537-path-traversal-delete/
    ├── task-cve-2024-8550-lfi-workflow/
    ├── task-cve-2024-8551-path-traversal/
    └── task-cve-2024-8556-stored-xss/
```

每个 task 包含：
- `README.md` - 漏洞详细说明
- `task.yaml` - 任务元数据
- `ground_truth_exploit.sh` - 自动化利用脚本
- `workspace/exploit_test.py` - Python 利用代码

## 关键发现

### 版本混淆问题

多个 CVE 的 NVD 数据库记录存在错误：

1. **CVE-2024-8550**:
   - NVD 声称影响 v0.0.4
   - 实际：`/load-workflow` 端点在 **v0.1.0** 才引入
   - 修正：使用 v0.1.1 运行时

2. **CVE-2024-8524**:
   - 报告称影响 v0.0.4
   - 实际：`/read-examples` 端点在 **v0.1.0** 才引入
   - 修正：使用 v0.1.1 运行时

### 技术要点

1. **Docker 隔离**：所有测试在独立容器中运行，避免污染宿主环境

2. **端口管理**：
   - v0.0.4 测试使用端口 5000
   - v0.1.1 测试使用端口 5001（避免冲突）
   - RPC 测试使用端口 12001

3. **真实利用**：
   - 每个测试都执行实际的漏洞利用
   - 验证漏洞影响（创建文件、读取数据、执行代码等）
   - 生成证明文件（proof files）

4. **自动化**：
   - 一键运行 `ground_truth_exploit.sh`
   - 自动构建 Docker 镜像
   - 自动清理容器

## 使用方法

### 运行单个测试

```bash
cd Anewbenchmark/agentscope-security-bench/tasks/task-cve-2024-48050-rce-eval
./ground_truth_exploit.sh
```

### 运行所有测试

```bash
cd Anewbenchmark/agentscope-security-bench

for task in tasks/task-cve-*/; do
    echo "Testing: $task"
    cd "$task"
    ./ground_truth_exploit.sh
    cd ../..
done
```

## 测试输出

每个成功的测试会生成：

1. **控制台输出**：详细的利用过程
2. **Proof 文件**：证明漏洞成功利用
3. **Evidence 文件**：详细的漏洞分析和影响说明

示例：
```
✓ SUCCESS - CVE-2024-48050 RCE exploited

Proof files:
  - tasks/task-cve-2024-48050-rce-eval/rce_proof.txt
  - tasks/task-cve-2024-48050-rce-eval/exploit_evidence.txt
```

## 安全影响评估

| CVE | 影响等级 | 主要风险 |
|-----|---------|---------|
| CVE-2024-48050 | CRITICAL | 远程代码执行，完全控制服务器 |
| CVE-2024-8501 | HIGH | 下载任意文件，泄露凭证和密钥 |
| CVE-2024-8524 | HIGH | 读取配置文件，信息泄露 |
| CVE-2024-8537 | HIGH | 删除任意文件，拒绝服务 |
| CVE-2024-8550 | HIGH | 读取 JSON 配置，泄露 API 密钥 |
| CVE-2024-8551 | HIGH | 读写任意文件，数据篡改 |
| CVE-2024-8556 | HIGH | XSS 攻击，会话劫持 |

## 修复建议

### 通用原则

1. **输入验证**：
   - 拒绝包含 `../` 的路径
   - 使用 `os.path.basename()` 去除目录部分
   - 验证最终路径在允许的目录内

2. **路径规范化**：
   ```python
   import os
   safe_path = os.path.abspath(user_path)
   allowed_dir = os.path.abspath(ALLOWED_DIR)
   if not safe_path.startswith(allowed_dir + os.sep):
       raise ValueError("Path outside allowed directory")
   ```

3. **避免危险函数**：
   - 永远不要对用户输入使用 `eval()`
   - 使用 `ast.literal_eval()` 或 JSON 解析

4. **输出编码**：
   - HTML 内容使用 `html.escape()`
   - 模板引擎自动转义

5. **访问控制**：
   - 实现认证和授权检查
   - 使用白名单限制可访问资源

## 后续工作

可以继续添加的测试：

1. CVE-2024-8502 - Deserialization 漏洞
2. CVE-2024-8503 - Command Injection
3. 性能测试（大规模payload）
4. 组合攻击链测试

## 参考资料

- [AgentScope GitHub](https://github.com/modelscope/agentscope)
- [Huntr.dev Security Reports](https://huntr.dev)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NVD Database](https://nvd.nist.gov/)

## 贡献者

测试套件遵循 `autogpt-security-bench` 和 `gpt_academic-security-bench` 的设计模式。
