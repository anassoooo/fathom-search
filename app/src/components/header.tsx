'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { ShoppingCart, User, LogOut, ArrowLeft, History } from 'lucide-react'
import { useAuth } from '@/components/auth-provider'
import Image from 'next/image'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function Header({ children, onHistoryClick }: { children?: React.ReactNode, onHistoryClick?: () => void }) {
  const { user, logout, isLoading } = useAuth()
  const router = useRouter()
  const pathname = usePathname()
  const isHomePage = pathname === '/'

  const handleLogout = async () => {
    await logout()
    router.refresh()
  }

  return (
    <header className="sticky top-0 z-50 w-full bg-linear-to-b from-background via-background 85% to-transparent border-none">
      <div className="container-premium flex h-36 items-start pt-5 justify-between gap-4 [mask-image:linear-gradient(to_right,transparent,black_40px,black_calc(100%-40px),transparent)]">
        <div className="flex items-start gap-4 flex-1 -mt-3">
          {!isHomePage && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.back()}
              className="h-10 w-10 rounded-full hover:bg-muted transition-all text-muted-foreground hover:text-foreground shrink-0 mt-1"
              aria-label="Go back"
            >
              <ArrowLeft className="h-5 w-5" />
            </Button>
          )}
          <Link href="/" className="flex flex-col items-center gap-1 group">
            <div className="relative w-12 h-12 transition-transform duration-300 group-hover:scale-110 group-hover:rotate-3">
              <Image
                src="/logo-original.png"
                alt="VioStore Logo"
                fill
                className="object-contain mix-blend-multiply brightness-110 contrast-110"
                priority
              />
            </div>
            <span className="font-bold text-xs uppercase tracking-[0.2em] bg-clip-text text-transparent bg-linear-to-r from-primary to-accent leading-none">VioStore</span>
          </Link>
        </div>

        <div className="flex-1 flex justify-center items-start mt-2">
          {children}
        </div>

        <nav className="flex items-start gap-2 flex-1 justify-end mt-1">
          {isLoading ? (
            <div className="w-8 h-8 rounded-full bg-muted animate-pulse" />
          ) : user ? (
            <>
              {onHistoryClick && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onHistoryClick}
                  aria-label="Search history"
                  className="hover:text-accent transition-colors"
                >
                  <History className="h-5 w-5" />
                </Button>
              )}
              <Link href="/cart">
                <Button variant="ghost" size="icon" aria-label="Shopping cart">
                  <ShoppingCart className="h-5 w-5" />
                </Button>
              </Link>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="User menu">
                    <User className="h-5 w-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <div className="px-2 py-1.5">
                    <p className="text-sm font-medium">{user.name || user.email}</p>
                    <p className="text-xs text-muted-foreground">{user.email}</p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/cart" className="cursor-pointer">
                      <ShoppingCart className="mr-2 h-4 w-4" />
                      My Cart
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive">
                    <LogOut className="mr-2 h-4 w-4" />
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          ) : (
            <>
              <Link href="/login">
                <Button variant="ghost">Sign in</Button>
              </Link>
              <Link href="/register">
                <Button variant="glow" className="shadow-lg">Sign up</Button>
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
