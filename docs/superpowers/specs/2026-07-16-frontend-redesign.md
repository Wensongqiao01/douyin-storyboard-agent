# 视频分镜分析 — 前端重构设计文档

## 概述

将现有 Gradio 单页应用重构为 FastAPI + Vue 3 全栈应用，面向 5 人内部团队使用。

## 架构

```
Vue 3 SPA (Vite)  ←→  FastAPI REST + SSE  ←→  Python 核心业务逻辑
      ↓                       ↓
  端口 5173               端口 7860
  (dev) / 静态文件      (prod 同一端口)
```

- 前端：Vue 3 + Vite + Tailwind CSS + Naive UI
- 后端：FastAPI + SQLite + JWT + SSE
- 核心模块 `core/` 零改动

## 页面清单

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 落地页 | 暖色调产品介绍，功能卡片，CTA 跳转登录 |
| `/login` | 登录页 | 毛玻璃卡片居中，账号密码 |
| `/dashboard` | 工作台 | 侧边导航 + 任务列表 + 搜索筛选 |
| `/dashboard` (modal) | 新建任务 | 弹窗：粘贴链接 → 四步进度动画 |
| `/result/:id` | 结果页 | 视频播放器 + 时间轴 + 分镜卡片 + 导出 |

## 视觉设计

### 配色

- 主色：橄榄暖绿 oklch(0.58 0.11 105)
- CTA 强调：琥珀 oklch(0.62 0.165 60)
- 落地页背景：微暖杏底 + 径向渐变
- 应用内：纯白底 + 毛玻璃面板

### 字体

- 落地页标题：Noto Serif SC（思源宋体）
- 全局正文/UI：Noto Sans SC（思源黑体）

### 颜色策略

- 落地页：Committed（暖色调承载品牌）
- 应用内：Restrained（主色仅用于交互态和强调）

## 功能需求

1. 实时进度：SSE 推送步骤状态（排队→下载→转写→分镜→完成）
2. 历史记录：按用户隔离的任务列表，支持搜索和状态筛选
3. 视频下载：完整文件下载
4. 分镜导出：SRT / Markdown / CSV / 视频片段
5. 视频清理：3 天 TTL 定时任务
6. 时间轴可视化：水平色块条，点击联动卡片滚动

## API 设计

```
POST   /api/auth/login          登录 → JWT
GET    /api/tasks               任务列表（user_id 隔离）
POST   /api/tasks               创建任务 → task_id
GET    /api/tasks/{id}          任务详情
GET    /api/tasks/{id}/stream   SSE 实时进度
GET    /api/tasks/{id}/video    视频文件下载
GET    /api/tasks/{id}/export   分镜导出（?format=srt|md|csv|clips）
DELETE /api/tasks/{id}          删除任务（含文件）
```

## 多租户

- 管理员创建账号，无公开注册
- JWT Token 认证
- 任务按 user_id 隔离
- 存储路径：`output/{user_id}/{task_id}/`

## 服务器适配

- 目标配置：2 核 4GB 50GB SSD
- max_workers = 1（Whisper 串行执行）
- Whisper 模型：tiny（150MB，推理 5-8 分钟）
- 任务队列：内存 FIFO
- 视频 TTL：3 天自动清理

## 反模式约束

- 不先写后端再写前端
- 不跳过视觉原型确认
- 不硬编码 API Key
- 不做过度设计（Redis/Celery 对 5 人团队是浪费）

## 前端组件树

```
App.vue
├── LandingPage.vue          （暖色落地页，无框架 chrome）
├── LoginPage.vue            （毛玻璃卡片）
├── AppLayout.vue            （侧边栏 + 主内容区）
│   ├── DashboardPage.vue    （任务列表 + 筛选）
│   │   └── NewTaskModal.vue （新建任务弹窗 + 进度）
│   └── ResultPage.vue       （结果展示）
│       ├── TimelineBar.vue  （水平时间轴）
│       └── SceneCard.vue    （分镜卡片）
```

## 当前状态

- 前端视觉原型：已完成（Vue 3 + Vite 项目，5 个页面 mock 数据）
- 后端 API：待实现
- 数据库：待建立
- 部署：待配置
