# HCP-Lab 前端修复计划

## 📋 文档信息

- **任务名称**: 实验列表页面渲染修复与代码质量整顿
- **关联模块**: `hcp-ui-lab` (Vue 3 + Vite + Pinia)
- **排除范围**: AI 实验生成功能（`Generate.vue`、`/api/ai/*` 接口、`experiments/generate` 路由）
- **文档版本**: v1.0
- **最后更新**: 2026-04-24

---

## 1. 任务概述

### 原始问题
实验列表页面 (`/experiments`) 在浏览器中显示为空（"暂无实验数据"），但后端 API `/api/experiments` 正确返回 8 条实验数据，`curl` 与 Vite 代理测试均正常。

### 修复目标
1. 确保实验列表页面正确渲染 8 个实验卡片
2. 消除 API 调用链中的类型不匹配与隐患
3. 整顿 `Result.vue` 中的错误处理与资源管理问题
4. 统一前后端数据模型字段命名

---

## 2. 已完成的工作

| 序号 | 工作内容 | 状态 |
|------|----------|------|
| 1 | 后端 API 验证（`/api/experiments` 返回 8 条数据） | ✅ 正常 |
| 2 | Vite 代理验证（`/api` → `localhost:9090`） | ✅ 正常 |
| 3 | `index.vue` 恢复 `experimentStore.loadExperiments()` 调用 | ✅ 已改 |
| 4 | `experiment.ts` API 层改为直接调用 `axiosInstance` | ✅ 已改 |
| 5 | `axiosInstance.ts` interceptor 返回完整 `response` 对象 | ✅ 已改 |
| 6 | `Result.vue` 重构结果展示、添加日志滚动、WebSocket 重连 | ✅ 已改 |

---

## 3. 剩余问题清单（排除 AI 功能）

### 🔴 严重问题

#### 3.1 `src/views/Experiments/Result.vue` — WebSocket 重连 Timer 泄漏

**位置**: `connectWS()` 函数内 `socket.onclose` 回调

**现象**: 组件卸载时调用 `ws.value?.close()` 会触发 `onclose`，其中 `setTimeout(connectWS, 3000)` 创建了一个未被清理的定时器。频繁挂载/卸载可能导致 timer 累积。

**根因**: `onUnmounted` 中只关闭了 WebSocket，未取消已注册的 reconnect timer。

**修复建议**:
```typescript
const reconnectTimer = ref<number | null>(null)

socket.onclose = () => {
  reconnectTimer.value = window.setTimeout(connectWS, 3000)
}

onUnmounted(() => {
  if (reconnectTimer.value) {
    clearTimeout(reconnectTimer.value)
    reconnectTimer.value = null
  }
  ws.value?.close()
})
```

---

#### 3.2 `src/views/Experiments/Result.vue` — `fetch` 获取文件不校验响应状态

**位置**: `loadMarkdown()` / `loadJson()` 函数

**现象**: 使用 `fetch(url)` 直接获取结果文件，未检查 `resp.ok`。当文件不存在（404）时，`resp.text()` 会返回 HTML 错误页面内容并直接展示给用户。

**根因**: 绕过了 `axiosInstance` 的统一错误处理，且未处理 HTTP 错误状态。

**修复建议**:
```typescript
const resp = await fetch(url)
if (!resp.ok) {
  throw new Error(`HTTP ${resp.status}: ${resp.statusText}`)
}
```

---

### 🟡 中等问题

#### 3.3 `src/views/Experiments/Result.vue` — WebSocket URL 硬编码

**位置**: `connectWS()` 函数

**现象**: `ws://${window.location.hostname}:9090/ws` 直接连接后端端口，绕过 Vite 代理。开发环境正常，但生产部署时若前端与后端分离或端口不同，连接失败。

**根因**: 未使用配置化的 `WS_URL`，而是硬编码端口。

**修复建议**: 恢复使用 `import { WS_URL } from '@/api/config'`，或根据当前页面协议/域名动态构建：
```typescript
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const wsUrl = `${protocol}//${window.location.host}/ws`
```

---

#### 3.4 `src/views/Experiments/index.vue` — 加载失败不展示错误原因

**位置**: 模板 `el-empty` 条件

**现象**: 当 `experimentStore.loadExperiments()` 失败时，`el-empty` 只显示 "暂无实验数据"，不展示 `experimentStore.error`，用户无法区分"加载失败"与"数据为空"。

**修复建议**: 在 `el-empty` 上方增加错误提示区域：
```vue
<el-alert
  v-if="experimentStore.error && experimentStore.experiments.length === 0"
  :title="experimentStore.error"
  type="error"
  show-icon
/>
```

---

#### 3.5 `src/api/experiment.ts` — `getTasks` 查询参数未 URL 编码

**位置**: `getTasks()` 函数

**现象**: `const query = expId ? \`?exp_id=${expId}\` : ''` 直接拼接字符串。若 `expId` 包含 `&`、`=`、`?` 等特殊字符，会导致参数解析错误。

**修复建议**:
```typescript
export function getTasks(expId?: string) {
  const params = expId ? new URLSearchParams({ exp_id: expId }).toString() : ''
  const url = params ? `/api/tasks?${params}` : '/api/tasks'
  return axiosInstance.get<ApiResponse<Task[]>>(url).then(r => r.data.data)
}
```

---

#### 3.6 `src/views/Experiments/Result.vue` — 图片下载可能不触发文件保存

**位置**: `downloadFile()` 函数

**现象**: `window.open(url, '_blank')` 在某些浏览器中会在新标签页打开图片，而非触发下载。

**修复建议**: 使用 `<a download>` 元素：
```typescript
function downloadFile(file: string | { path: string }) {
  const path = typeof file === 'string' ? file : file.path
  const url = getResultFileUrl(taskId, path)
  const a = document.createElement('a')
  a.href = url
  a.download = path.split('/').pop() || path
  a.click()
}
```

---

#### 3.7 `src/views/Experiments/Result.vue` — `otherFiles` 过滤隐藏了辅助文件

**位置**: `otherFiles` computed

**现象**: `.filter(f => !f.endsWith('.svg') && !f.endsWith('.md') && !f.endsWith('result.json') && !f.endsWith('.aux') && !f.endsWith('.log'))` 将 `.aux` 和 `.log` 文件排除在用户视野外。LaTeX 编译失败的排查需要查看 `.log` 文件。

**修复建议**: 移除 `.aux` 和 `.log` 的过滤，或将其归入独立的"日志文件"区域展示。

---

### 🟢 轻微问题

#### 3.8 `src/types/experiment.ts` — 字段名与后端不匹配

**位置**: `Experiment` 接口

**现象**: 前端定义 `script_path: string`，后端返回 `run_script: string` 与 `report_dir: string`。TypeScript 类型在运行时消失，不影响列表渲染，但会导致开发时类型提示错误，且任何依赖 `script_path` 的代码会拿到 `undefined`。

**修复建议**: 同步前端类型定义：
```typescript
export interface Experiment {
  id: string
  name: string
  description: string
  run_script: string
  report_dir: string
  params: ParamSchema[]
}
```

---

#### 3.9 `src/api/experiment.ts` — `axiosInstance.get` 泛型参数类型描述不准确

**位置**: 所有 API 函数

**现象**: `axiosInstance.get<{data: Experiment[]}>(...)` 中的 `{data: Experiment[]}` 描述的是 `response.data` 的类型，但实际 `response.data` 是 `{ code: number, message: string, data: Experiment[] }`（即 `ApiResponse<Experiment[]>`）。虽然不会导致运行时错误，但类型系统描述与真实数据结构不符。

**修复建议**: 统一使用 `ApiResponse<T>` 泛型：
```typescript
return axiosInstance.get<ApiResponse<Experiment[]>>('/api/experiments').then(r => r.data.data)
```

---

#### 3.10 `src/views/Experiments/Result.vue` — 已完成的任务重复加载报告

**位置**: `loadTask()` 函数

**现象**: 轮询间隔 3000ms，每次都会判断 `task.value?.status === 'completed' && oldStatus !== 'completed'`。若任务长期处于 completed 状态，首次加载后 `oldStatus` 被赋值为 `'completed'`，后续轮询条件为 `false`，**不会重复加载**。但若用户在任务完成前进入页面，完成后 `oldStatus` 为 `undefined` 或 `running`，会触发一次加载。此后每次轮询 `oldStatus` 与当前状态相同，不再触发。

**结论**: 实际不会导致重复加载，但逻辑可读性较差。建议将报告加载逻辑独立到 `watch(task, ...)` 中，或添加一个 `hasLoadedReport` 标志位。

---

## 4. 修复优先级

| 优先级 | 问题 | 影响 |
|--------|------|------|
| P0 | WebSocket 重连 Timer 泄漏 | 内存泄漏，页面切换越多问题越严重 |
| P0 | `fetch` 不校验 `resp.ok` | 404 时展示 HTML 错误页面给用户 |
| P1 | WebSocket URL 硬编码 | 生产环境部署失败 |
| P1 | 加载失败不展示错误 | 用户无法区分空数据与加载失败 |
| P1 | `getTasks` 参数未编码 | 特殊字符导致查询异常 |
| P2 | 字段名不匹配 | 开发体验差，潜在运行时隐患 |
| P2 | 泛型参数不准确 | 类型系统与运行时数据不一致 |
| P2 | 图片下载方式 | 部分浏览器行为不一致 |
| P2 | `otherFiles` 过滤 | 调试信息被隐藏 |

---

## 5. 验证步骤

### 5.1 实验列表渲染验证

1. 启动后端：`cd hcp-lab/hcp-lab-server && go run main.go`
2. 启动前端：`cd hcp-ui-lab && npm run dev`
3. 浏览器访问 `http://localhost:5174/experiments`
4. 预期：页面展示 8 个实验卡片，无 "暂无实验数据" 提示
5. 断网测试：关闭后端，刷新页面，预期展示错误提示（非空状态）

### 5.2 WebSocket 验证

1. 进入任意实验结果页 `/tasks/:id/results`
2. 启动对应实验
3. 预期：实时日志正常滚动，WebSocket 连接/断开/重连无异常
4. 组件切换：快速切换路由离开/返回结果页，浏览器 DevTools Performance 中 Timer 数量不应持续增长

### 5.3 结果文件下载验证

1. 等待实验完成，进入结果页
2. 点击 SVG 图表下方的"下载"按钮
3. 预期：浏览器触发文件下载（非新标签页打开图片）
4. 检查 `.log` 文件是否在"其他结果文件"列表中可见

### 5.4 删除任务验证

1. 进入任务管理页 `/tasks`
2. 删除任意已完成任务
3. 预期：请求方法为 POST，URL 为 `/api/tasks/{id}/delete`，返回 200

---

## 6. 后续建议

1. **统一 API 错误处理**: 将所有 `fetch` 调用统一到 `axiosInstance`，利用 interceptor 集中处理 401/403/500 等状态码。
2. **类型同步机制**: 建立前后端类型共享脚本，避免 `Experiment`、`Task` 等核心模型字段漂移。
3. **E2E 测试**: 引入 Playwright 或 Cypress 对列表渲染、实验执行、结果展示等核心流程进行自动化回归。
4. **性能监控**: 对高频日志场景（>100 条/秒）测试 `scrollToBottom` 的性能影响，必要时引入防抖。

---

**文档版本**: v1.0  
**最后更新**: 2026-04-24  
**维护者**: HCP Team
