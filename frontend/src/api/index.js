const BASE = '/api'

// 上传等长耗时操作的超时阈值 (毫秒)
const DEFAULT_TIMEOUT = 30000   // 普通请求 30s
const UPLOAD_TIMEOUT = 90000     // 上传 (含 LLM 解析) 90s

async function request(url, options = {}) {
  const headers = { ...options.headers }
  const isFormData = options.body instanceof FormData

  // FormData: 不设置 Content-Type, 让浏览器自动添加 boundary
  // JSON: 设置 Content-Type 并序列化 body
  if (options.body && !isFormData) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }

  // 超时控制: AbortController
  const timeout = options.timeout || DEFAULT_TIMEOUT
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  // 透传用户传入的 signal (如有) 与超时 signal 合并
  if (options.signal) {
    options.signal.addEventListener('abort', () => controller.abort())
  }

  let res
  try {
    res = await fetch(`${BASE}${url}`, {
      ...options,
      headers,
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timer)
    if (err.name === 'AbortError') {
      return { success: false, status: 0, message: '请求超时，请稍后重试（简历解析较慢，最多需 90 秒）' }
    }
    return {
      success: false,
      status: 0,
      message: '无法连接后端服务，请确认 FastAPI 已在 127.0.0.1:8000 启动',
    }
  } finally {
    clearTimeout(timer)
  }

  if (!res.ok) {
    // 尝试从响应体提取错误信息
    let detail = ''
    try {
      const errBody = await res.json()
      detail = errBody.detail || errBody.message || ''
    } catch (_) {
      detail = await res.text().catch(() => '')
    }
    return {
      success: false,
      status: res.status,
      message: res.status === 404
        ? '接口不存在（404），请确认启动的是当前项目后端'
        : res.status === 500 && !detail
          ? '后端未启动或代理连接失败，请确认 FastAPI 已在 127.0.0.1:8000 启动'
          : `请求失败 (${res.status})` + (detail ? `: ${detail}` : ''),
    }
  }

  try {
    return await res.json()
  } catch (err) {
    return { success: false, message: `响应解析失败: ${err.message}` }
  }
}

export const getRoles = () => request('/roles')

export const login = (username, password) =>
  request('/login', { method: 'POST', body: { username, password } })

export const uploadResume = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return request('/upload/resume', {
    method: 'POST',
    body: fd,
    timeout: UPLOAD_TIMEOUT,
  })
}

export const parseTextResume = (content) =>
  request('/resume/parse-text', { method: 'POST', body: { content } })

// 报告管理 (阶段2)
export const getReports = () => request('/reports')
export const getReport = (reportId) => request(`/reports/${reportId}`)
export const getReportRadar = (reportId) => request(`/reports/${reportId}/radar`)
