import i18n from '../i18n'

export interface AuthStatus {
  status: 'logged_out' | 'pending' | 'logged_in'
  is_logged_in: boolean
  user_info?: UserInfo
  tokenExpired?: boolean
}

export interface UserInfo {
  id: string
  username: string
  phone?: string
  email?: string
  image_url?: string
  provider?: string
  credits?: number
  created_at?: string
  updated_at?: string
}

export interface AuthResult {
  status: string
  token: string
  user_info: UserInfo
  message?: string
}

function errorDetail(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg)
  }
  return fallback
}

export async function fetchCaptcha(): Promise<{
  captcha_id: string
  image_base64: string
}> {
  const response = await fetch('/api/auth/captcha')
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(data, i18n.t('common:auth.captchaLoadFailed')))
  }
  return {
    captcha_id: data.captcha_id,
    image_base64: data.image_base64,
  }
}

export async function registerWithPhone(
  phone: string,
  password: string,
  captchaId: string,
  captchaCode: string
): Promise<AuthResult> {
  const response = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone,
      password,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(data, i18n.t('common:auth.registerFailed')))
  }
  saveAuthData(data.token, data.user_info)
  return data
}

export async function loginWithPhone(
  phone: string,
  password: string
): Promise<AuthResult> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone, password }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(data, i18n.t('common:auth.loginFailed')))
  }
  saveAuthData(data.token, data.user_info)
  return data
}

export async function resetPasswordWithCaptcha(
  phone: string,
  password: string,
  captchaId: string,
  captchaCode: string
): Promise<{ message: string }> {
  const response = await fetch('/api/auth/forgot-password/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      phone,
      password,
      captcha_id: captchaId,
      captcha_code: captchaCode,
    }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(data, i18n.t('common:auth.resetPasswordFailed')))
  }
  return data
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const token = localStorage.getItem('access_token')
  const userInfo = localStorage.getItem('user_info')

  if (token && userInfo) {
    try {
      const refreshed = await refreshToken(token)
      localStorage.setItem('access_token', refreshed.new_token)
      if (refreshed.user_info) {
        localStorage.setItem('user_info', JSON.stringify(refreshed.user_info))
      }
      return {
        status: 'logged_in',
        is_logged_in: true,
        user_info: refreshed.user_info || JSON.parse(userInfo),
      }
    } catch (error) {
      if (error instanceof Error && error.message === 'TOKEN_EXPIRED') {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user_info')
        return {
          status: 'logged_out',
          is_logged_in: false,
          tokenExpired: true,
        }
      }
      return {
        status: 'logged_in',
        is_logged_in: true,
        user_info: JSON.parse(userInfo),
      }
    }
  }

  return {
    status: 'logged_out',
    is_logged_in: false,
  }
}

export async function logout(): Promise<{ status: string; message: string }> {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user_info')
  return {
    status: 'success',
    message: i18n.t('common:auth.logoutSuccessMessage'),
  }
}

export async function getUserProfile(): Promise<UserInfo> {
  const userInfo = localStorage.getItem('user_info')
  if (!userInfo) {
    throw new Error(i18n.t('common:auth.notLoggedIn'))
  }
  return JSON.parse(userInfo)
}

export function saveAuthData(token: string, userInfo: UserInfo) {
  localStorage.setItem('access_token', token)
  localStorage.setItem('user_info', JSON.stringify(userInfo))
}

export function getAccessToken(): string | null {
  return localStorage.getItem('access_token')
}

export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getAccessToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return fetch(url, {
    ...options,
    headers,
  })
}

export async function refreshToken(currentToken: string): Promise<{
  new_token: string
  user_info?: UserInfo
}> {
  const response = await fetch('/api/auth/refresh-token', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${currentToken}`,
    },
  })

  if (response.status === 200) {
    return await response.json()
  }
  if (response.status === 401) {
    throw new Error('TOKEN_EXPIRED')
  }
  throw new Error(`NETWORK_ERROR: ${response.status}`)
}

/** Client-side password rules (mirror backend) */
export function validatePhoneClient(phone: string): string | null {
  if (!phone.trim()) return i18n.t('common:auth.phoneRequired')
  if (!/^1[3-9]\d{9}$/.test(phone.trim())) {
    return i18n.t('common:auth.phoneInvalid')
  }
  return null
}

export function validatePasswordClient(password: string): string | null {
  if (password.length < 8) return i18n.t('common:auth.passwordTooShort')
  if (!/[a-z]/.test(password)) return i18n.t('common:auth.passwordNeedLower')
  if (!/[A-Z]/.test(password)) return i18n.t('common:auth.passwordNeedUpper')
  if (!/\d/.test(password)) return i18n.t('common:auth.passwordNeedDigit')
  if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(password)) {
    return i18n.t('common:auth.passwordNeedSpecial')
  }
  return null
}
