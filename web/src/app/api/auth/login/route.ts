import { NextRequest, NextResponse } from 'next/server'

import { createSession, login, setSessionCookie } from '@/lib/auth'
import { credentialsSchema } from '@/lib/validation'

export async function POST(request: NextRequest) {
  const parsed = credentialsSchema.safeParse(await request.json().catch(() => null))
  if (!parsed.success) {
    // Don't echo which field failed: same answer as a wrong password.
    return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })
  }
  try {
    const user = await login(parsed.data.email, parsed.data.password)
    await setSessionCookie(await createSession(user.id))
    return NextResponse.json({ user: { id: user.id, email: user.email, name: user.name } })
  } catch (error) {
    if (error instanceof Error && error.message === 'Invalid credentials') {
      return NextResponse.json({ error: 'Invalid email or password' }, { status: 401 })
    }
    console.error('Login error:', error)
    return NextResponse.json({ error: 'Login failed' }, { status: 500 })
  }
}
