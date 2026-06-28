import type { ReactNode } from 'react';

type BadgeVariant =
  | 'success'
  | 'warning'
  | 'error'
  | 'info'
  | 'food'
  | 'size'
  | 'modifier'
  | 'cardinal';

interface BadgeProps {
  variant: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  error:   'bg-red-50 text-red-700 border-red-200',
  info:    'bg-indigo-50 text-indigo-700 border-indigo-200',
  food:    'bg-[#EEF2FF] text-[#4338CA] border-[#C7D2FE]',
  size:    'bg-[#FEF3C7] text-[#92400E] border-[#FDE68A]',
  modifier:'bg-[#DCFCE7] text-[#166534] border-[#BBF7D0]',
  cardinal:'bg-[#E0F2FE] text-[#075985] border-[#BAE6FD]',
};

export default function Badge({ variant, children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-full border ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
