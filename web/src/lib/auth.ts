import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'

const SESSION_COOKIE_NAME = 'session_id'
const SESSION_EXPIRY_DAYS = 7

export interface User {
  id: string
  email: string
  name: string | null
  created_at: Date
}

// Simple hash function for demo (use bcrypt in production)
export async function hashPassword(password: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(password + (process.env.AUTH_SECRET || 'default-secret'))
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  const passwordHash = await hashPassword(password)
  return passwordHash === hash
}

export async function createSession(userId: string): Promise<string> {
  const expiresAt = new Date()
  expiresAt.setDate(expiresAt.getDate() + SESSION_EXPIRY_DAYS)

  const session = await prisma.session.create({
    data: {
      userId,
      expiresAt
    }
  })

  return session.id
}

export async function setSessionCookie(sessionId: string): Promise<void> {
  const cookieStore = await cookies()
  cookieStore.set(SESSION_COOKIE_NAME, sessionId, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 24 * SESSION_EXPIRY_DAYS,
  })
}

export async function getSession(): Promise<{ userId: string; sessionId: string } | null> {
  const cookieStore = await cookies()
  const sessionId = cookieStore.get(SESSION_COOKIE_NAME)?.value

  if (!sessionId) return null

  try {
    const session = await prisma.session.findUnique({
      where: { id: sessionId }
    })

    if (!session || new Date(session.expiresAt) < new Date()) {
      if (session) {
        await prisma.session.delete({ where: { id: sessionId } })
      }
      return null
    }

    return { userId: session.userId, sessionId: session.id }
  } catch {
    return null
  }
}

export async function getCurrentUser(): Promise<User | null> {
  const session = await getSession()
  if (!session) return null

  try {
    const user = await prisma.user.findUnique({
      where: { id: session.userId }
    })

    if (!user) return null

    return {
      id: user.id,
      email: user.email,
      name: user.name,
      created_at: user.createdAt
    }
  } catch {
    return null
  }
}

export async function logout(): Promise<void> {
  const session = await getSession()
  if (session) {
    await prisma.session.delete({ where: { id: session.sessionId } })
  }

  const cookieStore = await cookies()
  cookieStore.delete(SESSION_COOKIE_NAME)
}

export async function requireAuth(redirectTo?: string) {
  const user = await getCurrentUser()
  if (!user) {
    const params = redirectTo ? `?next=${encodeURIComponent(redirectTo)}` : ''
    redirect(`/login${params}`)
  }
  return user
}

export async function register(email: string, password: string, name?: string): Promise<User> {
  const existingUser = await prisma.user.findUnique({
    where: { email }
  })

  if (existingUser) {
    throw new Error('User already exists')
  }

  const passwordHash = await hashPassword(password)

  const newUser = await prisma.user.create({
    data: {
      email,
      passwordHash,
      name
    }
  })

  return {
    id: newUser.id,
    email: newUser.email,
    name: newUser.name,
    created_at: newUser.createdAt
  }
}

export async function login(email: string, password: string): Promise<User> {
  const user = await prisma.user.findUnique({
    where: { email }
  })

  if (!user) {
    throw new Error('Invalid credentials')
  }

  const valid = await verifyPassword(password, user.passwordHash)
  if (!valid) {
    throw new Error('Invalid credentials')
  }

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    created_at: user.createdAt,
  }
}
