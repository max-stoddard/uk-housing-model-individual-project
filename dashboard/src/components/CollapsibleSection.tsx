import { useId, useState, type ReactNode } from 'react';

interface CollapsibleSectionProps {
  title: ReactNode;
  defaultOpen?: boolean;
  summary?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

export function CollapsibleSection({
  title,
  defaultOpen = false,
  summary,
  className,
  bodyClassName,
  children
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const contentId = useId();

  const rootClassName = ['collapsible-section', isOpen ? 'is-open' : 'is-collapsed', className]
    .filter(Boolean)
    .join(' ');
  const contentClassName = ['collapsible-section-body', bodyClassName].filter(Boolean).join(' ');

  return (
    <section className={rootClassName}>
      <button
        type="button"
        className="collapsible-section-toggle"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
        aria-controls={contentId}
      >
        <span className="collapsible-section-heading">
          <span className="collapsible-section-indicator" aria-hidden="true">
            {isOpen ? '▾' : '▸'}
          </span>
          <span className="collapsible-section-title">{title}</span>
        </span>
        {summary ? <span className="collapsible-section-summary">{summary}</span> : null}
      </button>

      <div id={contentId} className={contentClassName} hidden={!isOpen}>
        {children}
      </div>
    </section>
  );
}
