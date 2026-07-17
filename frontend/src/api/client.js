// 统一 API 客户端：自动带 token，401 统一跳登录
const BASE = '/api'

async function request(path, options = {}) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  let res
  try {
    res = await fetch(BASE + path, { ...options, headers })
  } catch {
    throw new Error('网络连接失败，请检查服务是否在线')
  }
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('登录已过期')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `请求失败 (${res.status})`)
  }
  return res.json()
}

function tokenQuery() {
  return `token=${encodeURIComponent(localStorage.getItem('token') || '')}`
}

export const api = {
  login: (username, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  listTasks: () => request('/tasks'),
  createTask: (url) =>
    request('/tasks', { method: 'POST', body: JSON.stringify({ url }) }),
  getTask: (id) => request(`/tasks/${id}`),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
  // EventSource / <video> / 下载链接无法带 header，用 query token
  streamUrl: (id) => `${BASE}/tasks/${id}/stream?${tokenQuery()}`,
  videoUrl: (id) => `${BASE}/tasks/${id}/video?${tokenQuery()}`,
  exportUrl: (id, format) =>
    `${BASE}/tasks/${id}/export?format=${format}&${tokenQuery()}`,
}
