import { randomBytes } from 'node:crypto'

import bcrypt from 'bcryptjs'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { prisma } from '@/lib/prisma'

const SESSION_COOKIE_NAME = 'session_id'
const SESSION_EXPIRY_DAYS = 7
const BCRYPT_COST = 12
// Compared against when the email is unknown, so login timing doesn't reveal which
// emails have accounts. (bcrypt hash of a random throwaway string.)
const DUMMY_HASH = bcrypt.hashSync(randomBytes(16).toString('hex'), BCRYPT_COST)

export interface User {
  id: string
  email: string
  name: string | null
  created_at: Date
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase()
}

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, BCRYPT_COST)
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash)
}

export async function createSession(userId: string): Promise<string> {
  const expiresAt = new Date()
  expiresAt.setDate(expiresAt.getDate() + SESSION_EXPIRY_DAYS)

  // 256-bit random token: unguessable, unlike sequential/cuid-style ids.
  const session = await prisma.session.create({
    data: { id: randomBytes(32).toString('hex'), userId, expiresAt },
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

export async function register(rawEmail: string, password: string, name?: string): Promise<User> {
  const email = normalizeEmail(rawEmail)
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
    where: { email: normalizeEmail(email) }
  })

  // Always run one bcrypt comparison so unknown emails take as long as wrong passwords.
  const valid = await verifyPassword(password, user?.passwordHash ?? DUMMY_HASH)
  if (!user || !valid) {
    throw new Error('Invalid credentials')
  }

  return {
    id: user.id,
    email: user.email,
    name: user.name,
    created_at: user.createdAt,
  }
}

/** Admins are listed by email in ADMIN_EMAILS (comma-separated). Used for /metrics. */
export async function isAdmin(): Promise<boolean> {
  const user = await getCurrentUser()
  if (!user) return false
  const admins = (process.env.ADMIN_EMAILS ?? '')
    .split(',')
    .map((e) => normalizeEmail(e))
    .filter(Boolean)
  return admins.includes(normalizeEmail(user.email))
}
