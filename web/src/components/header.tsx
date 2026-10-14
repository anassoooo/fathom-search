'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { ShoppingCart, LogOut, History, UserRound, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useAuth } from '@/components/auth-provider'
import { Wordmark } from '@/components/brand'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

/** Search sits behind sign-in; send signed-out visitors through login and back. */
export function searchHref(signedIn: boolean, query?: string) {
  const target = query ? `/assistant?q=${encodeURIComponent(query)}` : '/assistant'
  return signedIn ? target : `/login?next=${encodeURIComponent(target)}`
}

export function Header({ onHistoryClick }: { onHistoryClick?: () => void }) {
  const { user, logout, isLoading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  const handleLogout = async () => {
    await logout()
    router.refresh()
  }

  const trackOpen = () => {
    fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ eventType: 'assistant_open', metadata: { fromPage: pathname } }),
    }).catch(() => {})
  }

  const navLink = (active: boolean) =>
    cn(
      'rounded-md px-3 py-1.5 text-[0.9375rem] transition-colors',
      active ? 'text-ink font-medium' : 'text-ink-soft hover:text-ink',
    )

  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/85 backdrop-blur-md supports-[backdrop-filter]:bg-paper/75">
      <div className="shell flex h-16 items-center gap-2">
        <Link href="/" aria-label="Fathom home" className="mr-3 rounded-md">
          <Wordmark />
        </Link>

        <nav className="flex items-center" aria-label="Main">
          <Link
            href={searchHref(!!user)}
            onClick={user ? trackOpen : undefined}
            className={navLink(pathname === '/assistant')}
          >
            Search
          </Link>
          <Link href="/#catalog" className={cn(navLink(false), 'hidden sm:inline-block')}>
            Browse
          </Link>
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <ThemeToggle />
          {isLoading ? (
            <div className="size-8 rounded-full bg-shoal animate-pulse" />
          ) : user ? (
            <>
              {onHistoryClick && (
                <Button variant="ghost" size="icon" onClick={onHistoryClick} aria-label="Recent searches">
                  <History className="size-[1.15rem]" />
                </Button>
              )}
              <Button variant="ghost" size="icon" asChild>
                <Link href="/cart" aria-label="Cart">
                  <ShoppingCart className="size-[1.15rem]" />
                </Link>
              </Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="Account">
                    <UserRound className="size-[1.15rem]" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <div className="px-2 py-1.5">
                    <p className="text-sm font-medium">{user.name || user.email}</p>
                    <p className="text-xs text-ink-soft">{user.email}</p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/cart" className="cursor-pointer">
                      <ShoppingCart className="mr-2 size-4" />
                      Cart
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive">
                    <LogOut className="mr-2 size-4" />
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link href="/login">Sign in</Link>
              </Button>
              <Button asChild className="hidden sm:inline-flex">
                <Link href="/register">Create account</Link>
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

/** Both icons render and CSS picks one, so server and client markup always match. */
function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const dark = resolvedTheme === 'dark'
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(dark ? 'light' : 'dark')}
      aria-label="Switch between light and dark theme"
      title="Switch between light and dark theme"
    >
      <Moon className="size-[1.15rem] dark:hidden" />
      <Sun className="hidden size-[1.15rem] dark:block" />
    </Button>
  )
}
