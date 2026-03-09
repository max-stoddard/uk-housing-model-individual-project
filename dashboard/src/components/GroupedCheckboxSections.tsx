interface GroupedCheckboxItem {
  id: string;
  label: string;
  description?: string;
  checked: boolean;
  disabled?: boolean;
}

interface GroupedCheckboxSection {
  id: string;
  title: string;
  items: GroupedCheckboxItem[];
}

interface GroupedCheckboxSectionsProps {
  sections: GroupedCheckboxSection[];
  onToggle: (id: string) => void;
  className?: string;
  sectionClassName?: string;
}

export function GroupedCheckboxSections({
  sections,
  onToggle,
  className = 'param-groups',
  sectionClassName
}: GroupedCheckboxSectionsProps) {
  return (
    <div className={className}>
      {sections.map((section) => (
        <div key={section.id} className={sectionClassName}>
          <h3>{section.title}</h3>
          {section.items.map((item) => (
            <label
              key={item.id}
              className={`checkbox-row ${item.disabled ? 'checkbox-row-disabled' : ''}`}
            >
              <input
                type="checkbox"
                checked={item.checked}
                disabled={item.disabled}
                onChange={() => onToggle(item.id)}
              />
              <span className="checkbox-row-text">
                <span>{item.label}</span>
                {item.description && <small className="checkbox-row-description">{item.description}</small>}
              </span>
            </label>
          ))}
        </div>
      ))}
    </div>
  );
}
