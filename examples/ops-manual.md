# 资源中心平台运维手册（演示知识库）

> 本手册为演示用虚构文档，用于 MyOpenWeb 知识库问答与检索评测。

## 1. 系统架构

资源中心平台由以下组件构成：

- 接入层：Nginx 反向代理，监听 443 端口，证书位于 `/etc/nginx/certs/rc.pem`
- 应用层：resource-api 服务（Spring Boot），监听 8080 端口，部署 2 个实例
- 任务层：resource-job 定时任务服务，监听 8081 端口，单实例部署
- 缓存层：Redis 6.2 哨兵模式，主节点端口 6379，最大内存配置 4GB
- 数据层：MySQL 8.0 主从架构，主库端口 3306，从库用于报表查询
- 消息层：RabbitMQ 3.9，管理端口 15672，业务端口 5672

## 2. 环境要求

- 操作系统：CentOS 7.9 或 Ubuntu 20.04
- JDK 版本：OpenJDK 11，禁止使用 JDK 8 运行 resource-api
- 应用服务器最低配置：4 核 CPU、8GB 内存、100GB 数据盘
- MySQL 服务器最低配置：8 核 CPU、16GB 内存、500GB SSD

## 3. 服务启停

### 3.1 启动顺序

必须按以下顺序启动，否则 resource-api 会因依赖检查失败而退出：

1. MySQL
2. Redis
3. RabbitMQ
4. resource-api
5. resource-job
6. Nginx

### 3.2 常用命令

- 启动应用：`systemctl start resource-api`
- 停止应用：`systemctl stop resource-api`
- 查看状态：`systemctl status resource-api`
- 重载 Nginx 配置：`nginx -s reload`

## 4. 日志规范

- resource-api 应用日志：`/data/logs/resource-api/app.log`，按天滚动，保留 30 天
- resource-api 错误日志：`/data/logs/resource-api/error.log`
- resource-job 任务日志：`/data/logs/resource-job/job.log`
- Nginx 访问日志：`/var/log/nginx/rc-access.log`
- 日志级别线上环境统一为 INFO，排障时可临时调整为 DEBUG，排障完成后必须改回，避免磁盘写满

## 5. 监控与告警阈值

| 指标 | 告警阈值 | 处理时限 |
|------|---------|---------|
| CPU 使用率 | 持续 5 分钟超过 80% | 30 分钟内响应 |
| 内存使用率 | 超过 85% | 30 分钟内响应 |
| 磁盘使用率 | 超过 90% | 15 分钟内响应 |
| 接口 P95 响应时间 | 超过 2 秒 | 1 小时内定位 |
| MySQL 主从延迟 | 超过 60 秒 | 立即处理 |
| RabbitMQ 队列积压 | 超过 10000 条 | 立即处理 |

## 6. 常见故障处置

### 6.1 数据库连接池耗尽

现象：日志出现 `CannotGetJdbcConnectionException`，接口大量超时。

处置步骤：

1. 执行 `SHOW PROCESSLIST` 检查 MySQL 是否存在慢查询堆积
2. 检查连接池配置：resource-api 的 HikariCP 最大连接数默认为 50
3. 如存在慢 SQL，先 kill 慢查询恢复业务，再走 SQL 优化流程
4. 临时扩容连接池需评估 MySQL `max_connections`（当前为 500），避免打满数据库

### 6.2 Redis 内存占用过高

现象：Redis 内存超过 3.5GB，出现 key 淘汰，缓存命中率下降。

处置步骤：

1. 执行 `redis-cli info memory` 确认 used_memory
2. 执行 `redis-cli --bigkeys` 定位大 key
3. 资源中心历史版本曾因资源快照缓存未设置过期时间导致内存泄漏，快照 key 前缀为 `rc:snapshot:`，可确认是否有该前缀的 key 未设置 TTL
4. 清理需在业务低峰期执行，禁止直接 `FLUSHALL`

### 6.3 磁盘空间告警

现象：数据盘使用率超过 90% 告警。

处置步骤：

1. 执行 `du -sh /data/logs/*` 确认日志占用
2. 优先清理 30 天以前的历史日志压缩包
3. 检查是否有人将日志级别调成 DEBUG 后忘记改回
4. 清理后仍超过 80%，提交磁盘扩容工单

### 6.4 接口响应超时

现象：P95 响应时间超过 2 秒，前端反馈加载缓慢。

处置步骤：

1. 查看 `rc-access.log` 确认慢请求集中的接口路径
2. 资源列表接口 `/api/v2/resources` 是历史慢接口，当分页参数 pageSize 超过 200 时会触发全表扫描，需确认调用方参数
3. 检查 Redis 命中率，命中率低于 80% 时优先排查缓存失效
4. 必要时对慢接口开启限流，单实例阈值为 100 QPS

### 6.5 证书过期

现象：客户端报 SSL 证书错误，浏览器提示不安全。

处置步骤：

1. 执行 `openssl x509 -enddate -noout -in /etc/nginx/certs/rc.pem` 查看到期时间
2. 证书由安全组统一签发，到期前 30 天应收到续期提醒邮件
3. 替换证书后执行 `nginx -s reload`，无需重启应用

### 6.6 消息队列积压

现象：RabbitMQ 队列 `rc.resource.sync` 积压超过 10000 条。

处置步骤：

1. 登录管理台（15672 端口）确认消费者是否在线
2. resource-job 是该队列唯一消费者，检查其进程与日志
3. 常见原因是下游资源同步接口超时导致消费缓慢，可临时将消费者并发从 4 调整为 8
4. 积压超过 10 万条时，评估是否启用应急直连同步通道

## 7. 备份与恢复

- MySQL 全量备份：每天凌晨 2 点执行，保留 7 天，备份目录 `/data/backup/mysql`
- MySQL binlog：保留 3 天，用于时间点恢复
- 恢复演练：每季度执行一次，恢复目标时间（RTO）要求 2 小时以内
- Redis 使用 RDB 持久化，每 6 小时一次，不承诺缓存数据零丢失

## 8. 发布检查清单

发布前：

1. 确认变更单已审批，发布窗口为工作日 20:00 之后
2. 确认数据库变更脚本已在预发环境验证
3. 确认回滚包与回滚 SQL 已准备

发布中：

1. 摘除一台实例流量，发布并验证健康检查接口 `/actuator/health`
2. 核心接口冒烟通过后再发布第二台

发布后：

1. 观察 30 分钟监控大盘，重点看错误率与 P95
2. 在变更群同步发布结果

## 9. 应急预案

- 一级故障（全站不可用）：10 分钟内电话上报值班经理，同时拉应急群
- 二级故障（核心功能受损）：30 分钟内群内上报
- 数据库主库故障：执行主从切换预案，预计影响时间 5 分钟，切换后必须验证主从复制方向
- 机房级故障：启用同城灾备环境，DNS 切换生效时间约 10 分钟
