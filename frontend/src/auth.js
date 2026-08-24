const TOKEN_KEY = 'interview_auth_token'
const USERNAME_KEY = 'interview_auth_username'

export function saveAuth(token, username) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USERNAME_KEY, username)
  localStorage.removeItem('token')
  localStorage.removeItem('username')
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USERNAME_KEY)
  localStorage.removeItem('token')
  localStorage.removeItem('username')
}

export function isAuthenticated() {
  const token = localStorage.getItem(TOKEN_KEY) || ''
  const username = localStorage.getItem(USERNAME_KEY) || ''
  return username === 'admin' && /^[a-f0-9]{32}$/.test(token)
}

export function getUsername() {
  return localStorage.getItem(USERNAME_KEY) || ''
}
