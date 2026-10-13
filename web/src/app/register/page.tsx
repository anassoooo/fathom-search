'use client'

import React from "react"

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/components/auth-provider'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Spinner } from '@/components/ui/spinner'
import { Header } from '@/components/header'
import { ContourField } from '@/components/brand'

function RegisterForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { register, user, isLoading } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const next = searchParams.get('next') || '/'
  const action = searchParams.get('action')
  const payload = searchParams.get('payload')

  const handlePostAuthAction = () => {
    if (action === 'open_assistant') {
      // Navigate to assistant in the same tab, passing next as a query param
      router.push(`/assistant?next=${encodeURIComponent(next)}`)
    } else if (action === 'add_to_cart' && payload) {
      fetch('/api/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ productId: payload, quantity: 1 }),
      }).then(() => {
        router.push(next)
      })
    } else {
      router.push(next)
    }
  }

  useEffect(() => {
    if (!isLoading && user) {
      handlePostAuthAction()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, isLoading])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setIsSubmitting(true)

    try {
      await register(email, password, name || undefined)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
      setIsSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  return (
    <div className="w-full max-w-md px-4 py-12 sm:py-16">
      <Card className="relative w-full">
        <CardHeader className="space-y-1">
          <CardTitle className="display text-[2rem]">Create an account</CardTitle>
          <CardDescription>
            An account lets you search, see your recent searches, and keep a cart.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} className="space-y-6">
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="name">Name (optional)</Label>
              <Input
                id="name"
                type="text"
                placeholder="Your name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? <Spinner className="size-4" /> : null}
              Create account
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              Already have an account?{' '}
              <Link
                href={`/login?next=${encodeURIComponent(next)}${action ? `&action=${action}` : ''}${payload ? `&payload=${payload}` : ''}`}
                className="font-medium text-ink underline decoration-rule underline-offset-4 hover:decoration-contour"
              >
                Sign in
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}

export default function RegisterPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Spinner className="w-8 h-8" />
      </div>
    }>
      <div className="min-h-screen flex flex-col">
        <Header />
        <div className="relative flex flex-1 items-start justify-center overflow-hidden sm:items-center">
          <ContourField className="absolute left-1/2 top-1/2 w-[64rem] max-w-none -translate-x-1/2 -translate-y-1/2 opacity-70 [mask-image:radial-gradient(closest-side,black_55%,transparent)]" />
          <RegisterForm />
        </div>
      </div>
    </Suspense>
  )
}
