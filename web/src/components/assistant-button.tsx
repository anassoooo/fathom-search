'use client'

import { usePathname, useRouter } from 'next/navigation'
import { Sparkles } from 'lucide-react'
import { useAuth } from './auth-provider'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

export function AssistantButton() {
  const { user } = useAuth()
  const pathname = usePathname()
  const router = useRouter()

  const handleClick = () => {
    if (!user) {
      // Redirect to login with return URL and action
      const params = new URLSearchParams({
        next: pathname,
        action: 'open_assistant',
      })
      router.push(`/login?${params.toString()}`)
      return
    }

    // Track assistant open event
    fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eventType: 'assistant_open',
        metadata: { fromPage: pathname },
      }),
    }).catch(() => { })

    // Navigate to assistant in the same tab, passing the current path as next
    router.push(`/assistant?next=${encodeURIComponent(pathname)}`)
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            onClick={handleClick}
            size="lg"
            variant="glow"
            className="fixed bottom-6 right-6 z-50 rounded-full w-14 h-14 shadow-2xl flex items-center justify-center p-0 cursor-pointer"
            aria-label="Open AI Assistant"
          >
            <Sparkles className="h-6 w-6" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left">
          <p>AI Shopping Assistant</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
