// Author: Max Stoddard
import type { ElementType } from 'react';

type SkeletonElement = 'div' | 'span' | 'li';

interface LoadingSkeletonProps {
  className?: string;
  as?: SkeletonElement;
  ariaLabel?: string;
}

interface LoadingSkeletonGroupProps {
  className?: string;
  as?: SkeletonElement;
  count?: number;
  itemClassName?: string;
  ariaLabel?: string;
}

function joinClassNames(...names: Array<string | undefined>): string {
  return names.filter(Boolean).join(' ');
}

export function LoadingSkeleton({
  className,
  as = 'div',
  ariaLabel = 'Loading'
}: LoadingSkeletonProps) {
  const Component = as as ElementType;
  return (
    <Component
      className={joinClassNames('loading-skeleton', className)}
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      <span className="visually-hidden">{ariaLabel}</span>
    </Component>
  );
}

export function LoadingSkeletonGroup({
  className,
  as = 'div',
  count = 3,
  itemClassName,
  ariaLabel = 'Loading'
}: LoadingSkeletonGroupProps) {
  const Item = as as ElementType;
  return (
    <div className={className} role="status" aria-live="polite" aria-label={ariaLabel}>
      <span className="visually-hidden">{ariaLabel}</span>
      {Array.from({ length: count }, (_, index) => (
        <Item
          key={`loading-skeleton-${index}`}
          className={joinClassNames('loading-skeleton', itemClassName)}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}
