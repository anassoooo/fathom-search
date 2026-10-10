import { NextRequest, NextResponse } from 'next/server'

import { createSession, register, setSessionCookie } from '@/lib/auth'
import { firstIssue, registerSchema } from '@/lib/validation'

export async function POST(request: NextRequest) {
  const parsed = registerSchema.safeParse(await request.json().catch(() => null))
  if (!parsed.success) {
    return NextResponse.json({ error: firstIssue(parsed.error) }, { status: 400 })
  }
  const { email, password, name } = parsed.data
  try {
    const user = await register(email, password, name || undefined)
    await setSessionCookie(await createSession(user.id))
    return NextResponse.json({ user: { id: user.id, email: user.email, name: user.name } })
  } catch (error) {
    if (error instanceof Error && error.message === 'User already exists') {
      return NextResponse.json({ error: 'An account with this email already exists' }, { status: 409 })
    }
    console.error('Registration error:', error)
    return NextResponse.json({ error: 'Registration failed' }, { status: 500 })
  }
}
