import type { Book } from '../../types';

interface KavitaBadgeProps {
  book: Book;
  variant?: 'overlay' | 'inline';
}

export const KavitaBadge = ({ book, variant = 'inline' }: KavitaBadgeProps) => {
  const owned = book.kavita_series_owned;
  const total = book.series_count;
  const showSeries = typeof owned === 'number' && owned > 0;
  if (!showSeries) {
    return null;
  }

  const base =
    'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold text-white';
  const overlayShadow =
    variant === 'overlay'
      ? { boxShadow: '0 2px 8px rgba(0,0,0,0.4), 0 1px 3px rgba(0,0,0,0.3)' }
      : undefined;

  return (
    <span className={variant === 'overlay' ? 'flex flex-col items-end gap-1' : 'inline-flex gap-1'}>
      <span
        className={`${base} border border-indigo-700 bg-indigo-600`}
        style={overlayShadow}
        title="Books of this series already in your Kavita library"
      >
        Library {owned}
        {typeof total === 'number' && total > 0 ? `/${total}` : ''}
      </span>
    </span>
  );
};
