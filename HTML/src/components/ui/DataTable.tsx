import { useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { cn } from "./cn";
import { EmptyState } from "./States";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number; // makes the column sortable
  align?: "left" | "right";
  width?: string;
  hideBelow?: "md" | "lg" | "xl"; // drop low-priority columns on narrow screens
}

const HIDE: Record<NonNullable<Column<unknown>["hideBelow"]>, string> = { md: "hidden md:table-cell", lg: "hidden lg:table-cell", xl: "hidden xl:table-cell" };

/** The standard table: sortable columns, row selection by click or Enter, an empty state. */
export function DataTable<T>({
  rows, columns, rowKey, onRowClick, empty = "Nothing to show", selectedKey, dense,
}: {
  rows: T[]; columns: Column<T>[]; rowKey: (row: T) => string; onRowClick?: (row: T) => void; empty?: ReactNode; selectedKey?: string; dense?: boolean;
}) {
  const [sort, setSort] = useState<{ key: string; asc: boolean } | null>(null);
  const column = sort && columns.find((c) => c.key === sort.key);
  const sorted = column?.sortValue
    ? [...rows].sort((a, b) => {
        const x = column.sortValue!(a);
        const y = column.sortValue!(b);
        return (x < y ? -1 : x > y ? 1 : 0) * (sort!.asc ? 1 : -1);
      })
    : rows;
  if (rows.length === 0) return <EmptyState title={empty} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                style={c.width ? { width: c.width } : undefined}
                className={cn("h-9 px-3 text-2xs font-semibold tracking-wide whitespace-nowrap text-fg-subtle uppercase", c.align === "right" ? "text-right" : "text-left", c.hideBelow && HIDE[c.hideBelow])}
                aria-sort={sort?.key === c.key ? (sort.asc ? "ascending" : "descending") : undefined}
              >
                {c.sortValue ? (
                  <button type="button" className="inline-flex items-center gap-1 tracking-wide uppercase hover:text-fg" onClick={() => setSort((s) => ({ key: c.key, asc: s?.key === c.key ? !s.asc : true }))}>
                    {c.header}
                    {sort?.key === c.key && (sort.asc ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
                  </button>
                ) : (
                  c.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const key = rowKey(row);
            return (
              <tr
                key={key}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={onRowClick ? (e) => e.key === "Enter" && onRowClick(row) : undefined}
                aria-selected={selectedKey === key || undefined}
                className={cn(
                  "border-b border-line last:border-b-0",
                  onRowClick && "cursor-pointer hover:bg-surface-2 focus-visible:bg-surface-2",
                  selectedKey === key && "bg-surface-2",
                )}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn("px-3 align-middle", dense ? "py-1.5" : "py-2.5", c.align === "right" && "text-right tabular", c.hideBelow && HIDE[c.hideBelow])}>
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
