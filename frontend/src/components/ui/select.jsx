import { cn } from '../../lib/utils'

function Select({ className, children, ...props }) {
  return (
    <select
      className={cn(
        'h-10 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export { Select }
