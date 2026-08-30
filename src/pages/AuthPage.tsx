import {
  type FormEvent,
  useState,
} from 'react'

import { api } from '../services/api'
import {
  clearAccessToken,
  setAccessToken,
} from '../services/authSession'

import type {
  AuthUser,
  LoginResponse,
} from '../types/auth'

interface AuthPageProps {
  bootstrapRequired: boolean
  onAuthenticated: (user: AuthUser) => void
  onBootstrapComplete: () => Promise<void>
}

function extractToken(response: LoginResponse) {
  return response.access_token ?? response.token ?? null
}

export function AuthPage({
  bootstrapRequired,
  onAuthenticated,
  onBootstrapComplete,
}: AuthPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] =
    useState('')

  const [mfaCode, setMfaCode] = useState('')
  const [mfaRequired, setMfaRequired] =
    useState(false)

  const [loading, setLoading] = useState(false)
  const [error, setError] =
    useState<string | null>(null)

  async function authenticate(
    code?: string,
  ) {
    const response = await api.login({
      email: email.trim(),
      password,
      mfa_code: code || null,
    })

    if (response.mfa_required) {
      setMfaRequired(true)
      setMfaCode('')
      return
    }

    const token = extractToken(response)

    if (!token) {
      throw new Error(
        'El backend autentic? la solicitud pero no devolvi? access_token/token.',
      )
    }

    setAccessToken(token)

    try {
      const user =
        response.user ?? (await api.me())

      setPassword('')
      setMfaCode('')
      setMfaRequired(false)

      onAuthenticated(user)
    } catch (err) {
      clearAccessToken()
      throw err
    }
  }

  async function handleLogin(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    setError(null)
    setLoading(true)

    try {
      await authenticate(
        mfaRequired ? mfaCode.trim() : undefined,
      )
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible iniciar sesión.',
      )
    } finally {
      setLoading(false)
    }
  }

  async function handleBootstrap(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault()

    setError(null)
    setLoading(true)

    try {
      await api.bootstrap({
        email: email.trim(),
        password,
        display_name:
          displayName.trim() || null,
      })

      setPassword('')
      setDisplayName('')

      await onBootstrapComplete()
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'No fue posible crear el administrador inicial.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-brand">
        <div className="auth-brand-mark">
          N
        </div>

        <div>
          <span className="auth-eyebrow">
            Centro de Monitoreo Compensar
          </span>

          <h1>NEXUS</h1>

          <p>
            Monitoreo, análisis y acción en una
            sola plataforma.
          </p>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <span className="auth-card-eyebrow">
            {bootstrapRequired
              ? 'Configuración inicial'
              : mfaRequired
                ? 'Verificación MFA'
                : 'Acceso seguro'}
          </span>

          <h2>
            {bootstrapRequired
              ? 'Crear administrador'
              : mfaRequired
                ? 'Código de autenticación'
                : 'Iniciar sesión'}
          </h2>

          <p className="auth-description">
            {bootstrapRequired
              ? 'NEXUS aún no tiene usuarios. Crea la cuenta administrativa inicial.'
              : mfaRequired
                ? 'Ingresa el código temporal generado por tu aplicación autenticadora.'
                : 'Ingresa con tu cuenta local de NEXUS.'}
          </p>

          <form
            className="auth-form"
            onSubmit={
              bootstrapRequired
                ? handleBootstrap
                : handleLogin
            }
          >
            {!mfaRequired && (
              <>
                {bootstrapRequired && (
                  <label>
                    Nombre
                    <input
                      type="text"
                      value={displayName}
                      onChange={(event) =>
                        setDisplayName(
                          event.target.value,
                        )
                      }
                      autoComplete="name"
                      placeholder="Administrador NEXUS"
                    />
                  </label>
                )}

                <label>
                  Correo
                  <input
                    type="email"
                    value={email}
                    onChange={(event) =>
                      setEmail(event.target.value)
                    }
                    autoComplete="username"
                    required
                    placeholder="usuario@compensar.com"
                  />
                </label>

                <label>
                  Contraseña
                  <input
                    type="password"
                    value={password}
                    onChange={(event) =>
                      setPassword(
                        event.target.value,
                      )
                    }
                    autoComplete={
                      bootstrapRequired
                        ? 'new-password'
                        : 'current-password'
                    }
                    required
                  />
                </label>
              </>
            )}

            {mfaRequired && (
              <label>
                Código TOTP
                <input
                  className="auth-code-input"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={mfaCode}
                  onChange={(event) =>
                    setMfaCode(
                      event.target.value.replace(
                        /\D/g,
                        '',
                      ),
                    )
                  }
                  maxLength={8}
                  required
                  autoFocus
                  placeholder="000000"
                />
              </label>
            )}

            {error && (
              <div
                className="auth-error"
                role="alert"
              >
                {error}
              </div>
            )}

            <button
              className="auth-submit"
              type="submit"
              disabled={loading}
            >
              {loading
                ? 'Procesando...'
                : bootstrapRequired
                  ? 'Crear administrador'
                  : mfaRequired
                    ? 'Verificar código'
                    : 'Ingresar'}
            </button>

            {mfaRequired && (
              <button
                className="auth-secondary"
                type="button"
                disabled={loading}
                onClick={() => {
                  setMfaRequired(false)
                  setMfaCode('')
                  setPassword('')
                  setError(null)
                }}
              >
                Volver al inicio de sesión
              </button>
            )}
          </form>

          <div className="auth-security-note">
            La sesión se conserva únicamente mientras
            NEXUS permanece abierto. El token no se
            guarda en almacenamiento persistente del
            navegador.
          </div>
        </div>
      </section>
    </main>
  )
}
