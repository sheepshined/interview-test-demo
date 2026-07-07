const BASE = '/api'

async function request(url, options = {}) {
  const headers = { ...options.headers }
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(options.body)
  }
  const res = await fetch(`${BASE}${url}`, { ...options, headers })
  if (!res.ok) return { success: false, message: '请求失败 (' + res.status + ')' }
  return res.json()
}

export const getRoles = () => request('/roles')

export const uploadResume = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return request('/upload/resume', { method: 'POST', body: fd })
}

export const parseTextResume = (content) =>
  request('/resume/parse-text', { method: 'POST', body: { content } })
