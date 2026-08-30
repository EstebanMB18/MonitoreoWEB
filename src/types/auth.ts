export type UserRole =
  | 'ADMIN'
  | 'MONITOR_OFICIAL'
  | 'OPERADOR'
  | 'CONSULTA'

export interface AuthStatus {
  initialized: boolean
  users: number
  bootstrap_required: boolean
}

export interface AuthUser {
  user_id: string
  email: string
  display_name: string | null
  role: UserRole
  active: boolean
  mfa_enabled: boolean
  created_at?: string | null
  updated_at?: string | null
  last_login_at?: string | null
}

export interface LoginRequest {
  email: string
  password: string
  mfa_code?: string | null
}

export interface BootstrapRequest {
  email: string
  password: string
  display_name?: string | null
}

export interface LoginResponse {
  access_token?: string
  token?: string
  token_type?: string
  mfa_required?: boolean
  user?: AuthUser
  message?: string
  detail?: string
}

export interface MFASetupResponse {
  secret?: string
  provisioning_uri?: string
  otpauth_uri?: string
  qr_uri?: string
  [key: string]: unknown
}
