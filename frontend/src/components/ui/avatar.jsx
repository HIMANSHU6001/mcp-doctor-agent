import { cn } from '../../lib/utils'

function Avatar({ className, children, ...props }) {
  return (
    <span
      className={cn('relative inline-flex h-10 w-10 shrink-0 overflow-hidden rounded-full', className)}
      {...props}
    >
      {children}
    </span>
  )
}

function AvatarImage({ className, src, alt, ...props }) {
  return <img className={cn('aspect-square h-full w-full object-cover', className)} src={src} alt={alt} {...props} />
}

function AvatarFallback({ className, children, ...props }) {
  return (
    <span
      className={cn('flex h-full w-full items-center justify-center rounded-full bg-slate-200 text-slate-700', className)}
      {...props}
    >
      {children}
    </span>
  )
}

export { Avatar, AvatarFallback, AvatarImage }
