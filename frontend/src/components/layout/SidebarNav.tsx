import { List, type LucideIcon } from "lucide-react";

interface SidebarNavItem {
  readonly id: string;
  readonly label: string;
  readonly icon: LucideIcon;
}

interface SidebarNavProps {
  readonly title: string;
  readonly items: readonly SidebarNavItem[];
  readonly activeId: string;
  readonly onNavigate: (id: string) => void;
}

export function SidebarNav({ title, items, activeId, onNavigate }: SidebarNavProps) {
  return (
    <aside className="lg:w-64 shrink-0">
      <div className="lg:sticky lg:top-24">
        <div className="flex items-center gap-2 mb-4 text-sm font-medium">
          <List className="h-4 w-4" />
          {title}
        </div>
        <nav aria-label={title} className="space-y-1">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={activeId === item.id ? "true" : undefined}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors text-left ${
                activeId === item.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              }`}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {item.label}
            </button>
          ))}
        </nav>
      </div>
    </aside>
  );
}

export type { SidebarNavItem };
