import type { CSSProperties, ReactNode } from 'react';

import { useLibraryAvailability } from '../../contexts/LibraryAvailabilityContext';
import type { Book } from '../../types';

interface LibraryAvailabilityBadgesProps {
  book: Book;
  variant?: 'overlay' | 'inline';
}

const EbookIcon = () => (
  <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
    />
  </svg>
);

const AudiobookIcon = () => (
  <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z"
    />
  </svg>
);

const Chip = ({
  label,
  url,
  tone,
  icon,
  overlayShadow,
}: {
  label: string;
  url: string;
  tone: 'ebook' | 'audiobook';
  icon: ReactNode;
  overlayShadow?: CSSProperties;
}) => {
  const toneClass = tone === 'ebook' ? 'bg-sky-600' : 'bg-violet-600';
  const base = `inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold text-white ${toneClass}`;
  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} transition-opacity hover:opacity-90`}
        style={overlayShadow}
        title={`${label} — open library`}
      >
        {icon}
        <span>{label}</span>
      </a>
    );
  }
  return (
    <span className={base} style={overlayShadow} title={label}>
      {icon}
      <span>{label}</span>
    </span>
  );
};

export const LibraryAvailabilityBadges = ({
  book,
  variant = 'inline',
}: LibraryAvailabilityBadgesProps) => {
  const { libraryUrl, audiobookLibraryUrl } = useLibraryAvailability();
  const ebook = Boolean(book.kavita_available);
  const audio = Boolean(book.audiobookshelf_available);
  if (!ebook && !audio) {
    return null;
  }

  const overlayShadow =
    variant === 'overlay'
      ? { boxShadow: '0 2px 8px rgba(0,0,0,0.4), 0 1px 3px rgba(0,0,0,0.3)' }
      : undefined;

  return (
    <span className="inline-flex flex-wrap gap-1">
      {ebook && (
        <Chip
          label="eBook"
          url={libraryUrl}
          tone="ebook"
          icon={<EbookIcon />}
          overlayShadow={overlayShadow}
        />
      )}
      {audio && (
        <Chip
          label="Audiobook"
          url={audiobookLibraryUrl}
          tone="audiobook"
          icon={<AudiobookIcon />}
          overlayShadow={overlayShadow}
        />
      )}
    </span>
  );
};
