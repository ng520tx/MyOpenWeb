# 资源中心开放接口文档（演示知识库）

> 本文档为演示用虚构文档，与运维手册共同构成检索评测语料。

## 1. 接入说明

- 接口根地址：`https://rc.example.com/api/v2`
- 认证方式：请求头携带 `X-RC-Token`，令牌在开放平台申请，有效期 90 天
- 全部接口仅支持 HTTPS，请求与响应均为 JSON
- 分页参数统一为 `pageNo`（从 1 开始）与 `pageSize`（默认 20，上限 200）

## 2. 限流策略

- 单令牌默认配额：每分钟 600 次请求
- 超出配额返回错误码 42901，响应头 `X-RC-Retry-After` 给出建议重试秒数
- 批量接口（路径含 `/batch/`）单独限流：每分钟 60 次

## 3. 资源查询接口

### 3.1 分页查询资源列表

- 方法与路径：`GET /api/v2/resources`
- 查询参数：
  - `status`：资源状态，可选值 `online` / `offline` / `maintaining`
  - `categoryCuid`：资源分类编码
  - `keyword`：名称模糊搜索，最短 2 个字符
- 响应字段：`total`、`pageNo`、`pageSize`、`items[]`
- 说明：`pageSize` 超过 200 会被强制截断为 200

### 3.2 查询资源详情

- 方法与路径：`GET /api/v2/resources/{resourceCuid}`
- 路径参数：`resourceCuid` 资源唯一编码
- 响应包含 `baseInfo`、`fields[]`、`relations[]` 三段
- 资源不存在返回错误码 40401

## 4. 资源变更接口

### 4.1 创建资源

- 方法与路径：`POST /api/v2/resources`
- 必填字段：`categoryCuid`、`label`、`fields`
- 幂等控制：请求头 `X-RC-Request-Id`，相同 ID 60 秒内重复提交返回首次结果

### 4.2 更新资源字段

- 方法与路径：`PUT /api/v2/resources/{resourceCuid}/fields`
- 请求体为字段数组，单次最多更新 50 个字段
- 字段校验失败返回错误码 42201，`detail` 中列出未通过的 columnIndex

### 4.3 资源上线 / 下线

- 方法与路径：`POST /api/v2/resources/{resourceCuid}/status`
- 请求体：`{"action": "online"}` 或 `{"action": "offline"}`
- 下线前会检查关联工单，存在未闭环工单时返回错误码 40901

## 5. 资源同步回调

- 平台在资源变更后向订阅方推送回调，队列名 `rc.resource.sync`
- 回调重试策略：失败后按 1/5/30 分钟三次重试，仍失败进入死信队列
- 订阅方需在 3 秒内返回 `{"code": 0}`，否则视为失败

## 6. 错误码汇总

| 错误码 | 含义 | 处理建议 |
|--------|------|---------|
| 40001 | 参数缺失或格式错误 | 检查必填字段 |
| 40101 | 令牌无效或过期 | 重新申请令牌 |
| 40401 | 资源不存在 | 确认 resourceCuid |
| 40901 | 存在未闭环工单，禁止下线 | 先处理关联工单 |
| 42201 | 字段校验失败 | 按 detail 修正字段 |
| 42901 | 触发限流 | 按 X-RC-Retry-After 重试 |
| 50001 | 服务内部错误 | 携带 traceId 联系平台 |

## 7. 变更历史

- v2.3：新增资源上线/下线接口，回调增加死信队列
- v2.2：分页上限从 500 下调为 200，防止大分页拖垮数据库
- v2.1：令牌有效期从 30 天延长为 90 天
