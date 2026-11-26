import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export function PoleMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className}>
      <rect x="8" y="2" width="8" height="20" rx="4" fill="#fff" />
      <clipPath id="pole-clip">
        <rect x="8" y="2" width="8" height="20" rx="4" />
      </clipPath>
      <g clipPath="url(#pole-clip)" strokeWidth="2.2">
        <path d="M6 9l12-6M6 15l12-6M6 21l12-6" stroke="var(--pole-red)" />
        <path d="M6 12l12-6M6 18l12-6" stroke="var(--pole-blue)" />
      </g>
    </svg>
  );
}

export function DeskAvatar({ className }: { className?: string }) {
  return (
    <Avatar className={className}>
      <AvatarFallback className="bg-primary/10">
        <PoleMark className="size-[70%]" />
      </AvatarFallback>
    </Avatar>
  );
}
