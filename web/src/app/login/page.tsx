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

function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { login, user, isLoading } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const next = searchParams.get('next') || '/'
  const action = searchParams.get('action')
  const payload = searchParams.get('payload')

  const handlePostAuthAction = () => {
    // Handle pending actions after authentication
    if (action === 'open_assistant') {
      // Navigate to assistant in the same tab, passing next as a query param
      router.push(`/assistant?next=${encodeURIComponent(next)}`)
    } else if (action === 'add_to_cart' && payload) {
      // Add to cart then redirect
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
    setIsSubmitting(true)

    try {
      await login(email, password)
      // handlePostAuthAction will be called by useEffect when user changes
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
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
          <CardTitle className="display text-[2rem]">Sign in</CardTitle>
          <CardDescription>
            Sign in to search by description or by photo.
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
                autoComplete="current-password"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col space-y-4">
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? <Spinner className="size-4" /> : null}
              Sign in
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              Don&apos;t have an account?{' '}
              <Link
                href={`/register?next=${encodeURIComponent(next)}${action ? `&action=${action}` : ''}${payload ? `&payload=${payload}` : ''}`}
                className="font-medium text-ink underline decoration-rule underline-offset-4 hover:decoration-contour"
              >
                Sign up
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}

export default function LoginPage() {
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
          <LoginForm />
        </div>
      </div>
    </Suspense>
  )
}
