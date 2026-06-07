import type { CSSProperties } from 'react';

import { useLibraryAvailability } from '../contexts/LibraryAvailabilityContext';
import type { Book, ButtonStateInfo } from '../types';
import { CircularProgress } from './shared';

type ButtonSize = 'sm' | 'md';
type ButtonVariant = 'default' | 'icon';

interface BookGetButtonProps {
  book: Book;
  onGetReleases: (book: Book) => void;
  buttonState?: ButtonStateInfo;
  isLoading?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
  fullWidth?: boolean;
  className?: string;
  style?: CSSProperties;
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-4 py-2.5 text-sm',
};

const iconSizeClasses: Record<ButtonSize, string> = {
  sm: 'p-1.5',
  md: 'p-1.5 sm:p-2',
};

const iconSizes: Record<ButtonSize, string> = {
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
};

const iconOnlySizes: Record<ButtonSize, string> = {
  sm: 'w-4 h-4',
  md: 'w-4 h-4 sm:w-5 sm:h-5',
};

const EbookIcon = ({ className }: { className: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
    />
  </svg>
);

const AudiobookIcon = ({ className }: { className: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z"
    />
  </svg>
);

interface InLibraryButtonProps {
  label: string;
  url: string;
  tone: 'ebook' | 'audiobook';
  isIconVariant: boolean;
  fullWidth: boolean;
  size: ButtonSize;
  className: string;
  style?: CSSProperties;
}

const InLibraryButton = ({
  label,
  url,
  tone,
  isIconVariant,
  fullWidth,
  size,
  className,
  style,
}: InLibraryButtonProps) => {
  const toneClass = tone === 'ebook' ? 'bg-sky-600' : 'bg-violet-600';
  const iconSize = isIconVariant ? iconOnlySizes[size] : iconSizes[size];
  const Icon = tone === 'ebook' ? EbookIcon : AudiobookIcon;
  const clickable = Boolean(url);

  if (isIconVariant) {
    const base =
      `flex items-center justify-center rounded-full text-white ${toneClass} ${iconSizeClasses[size]} ${className}`.trim();
    if (clickable) {
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className={base}
          style={style}
          aria-label={label}
          title={label}
        >
          <Icon className={iconSize} />
        </a>
      );
    }
    return (
      <span
        className={`${base} cursor-not-allowed opacity-80`}
        style={style}
        aria-label={label}
        title={label}
      >
        <Icon className={iconSize} />
      </span>
    );
  }

  const base =
    `inline-flex items-center justify-center gap-1.5 rounded-sm text-white ${toneClass} ${sizeClasses[size]} ${fullWidth ? 'w-full' : ''} ${className}`.trim();
  if (clickable) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className={`${base} transition-colors hover:opacity-90`}
        style={style}
        title={label}
      >
        <Icon className={iconSize} />
        <span>{label}</span>
      </a>
    );
  }
  return (
    <span className={`${base} cursor-not-allowed opacity-80`} style={style} title={label}>
      <Icon className={iconSize} />
      <span>{label}</span>
    </span>
  );
};

export const BookGetButton = ({
  book,
  onGetReleases,
  buttonState,
  isLoading = false,
  size = 'md',
  variant = 'default',
  fullWidth = false,
  className = '',
  style,
}: BookGetButtonProps) => {
  const { libraryUrl, audiobookLibraryUrl, allowMissingType } = useLibraryAvailability();
  const isIconVariant = variant === 'icon';
  const widthClasses = fullWidth ? 'w-full' : '';
  const sizeClass = isIconVariant ? iconSizeClasses[size] : sizeClasses[size];
  const iconSize = isIconVariant ? iconOnlySizes[size] : iconSizes[size];

  const ebookInLibrary = Boolean(book.kavita_available);
  const audioInLibrary = Boolean(book.audiobookshelf_available);
  const anyInLibrary = ebookInLibrary || audioInLibrary;
  const exactlyOne = ebookInLibrary !== audioInLibrary;
  const showGet = !anyInLibrary || (exactlyOne && allowMissingType);

  const isCompleted = buttonState?.state === 'complete';
  const hasError = buttonState?.state === 'error';
  const isBlocked = buttonState?.state === 'blocked';
  const isInProgress =
    buttonState && ['queued', 'resolving', 'locating', 'downloading'].includes(buttonState.state);
  const showCircularProgress =
    buttonState?.state === 'downloading' && buttonState.progress !== undefined;
  const showSpinner = (isInProgress && !showCircularProgress) || isLoading;

  const isDisabled = isLoading || isBlocked;

  const getButtonClasses = () => {
    if (isCompleted) {
      return isIconVariant ? 'bg-green-600 text-white' : 'bg-green-600 hover:bg-green-700';
    }
    if (hasError) {
      return isIconVariant ? 'bg-red-600 text-white opacity-75' : 'bg-red-600 hover:bg-red-700';
    }
    if (isBlocked) {
      return isIconVariant
        ? 'text-gray-400 dark:text-gray-500 cursor-not-allowed opacity-70'
        : 'bg-gray-500 opacity-75 cursor-not-allowed';
    }
    if (isLoading) {
      return isIconVariant ? 'text-gray-400 dark:text-gray-500' : 'bg-emerald-600/70';
    }
    if (isInProgress) {
      return isIconVariant ? 'bg-sky-600 text-white' : 'bg-sky-600 hover:bg-sky-700';
    }
    return isIconVariant
      ? 'text-gray-600 dark:text-gray-200 hover-action'
      : 'bg-emerald-600 hover:bg-emerald-700';
  };

  const handleClick = () => {
    if (isDisabled) return;
    onGetReleases(book);
  };

  const getDisplayText = () => {
    if (isBlocked) return buttonState?.text || 'Unavailable';
    if (isCompleted) return 'Downloaded';
    if (hasError) return 'Failed';
    if (isLoading) return 'Loading';
    if (buttonState?.state === 'downloading') return 'Downloading';
    if (buttonState?.state === 'locating') return 'Locating files';
    if (buttonState?.state === 'resolving') return 'Resolving';
    if (buttonState?.state === 'queued') return 'Queued';
    if (buttonState?.state === 'download' && buttonState.text) return buttonState.text;
    return 'Get';
  };

  const renderIcon = () => {
    if (isCompleted) {
      return (
        <svg className={iconSize} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      );
    }

    if (hasError) {
      return (
        <svg className={iconSize} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      );
    }

    if (isBlocked) {
      return (
        <svg className={iconSize} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M16.5 10.5V7.875a4.125 4.125 0 1 0-8.25 0V10.5m-.75 0h9a2.25 2.25 0 0 1 2.25 2.25v6A2.25 2.25 0 0 1 16.5 21h-9a2.25 2.25 0 0 1-2.25-2.25v-6a2.25 2.25 0 0 1 2.25-2.25Z"
          />
        </svg>
      );
    }

    if (showCircularProgress) {
      let progressSize: number;
      if (isIconVariant) {
        progressSize = size === 'sm' ? 16 : 20;
      } else {
        progressSize = size === 'sm' ? 12 : 16;
      }
      return <CircularProgress progress={buttonState?.progress} size={progressSize} />;
    }

    if (showSpinner) {
      return (
        <div
          className={`${iconSize} animate-spin rounded-full border-2 border-current border-t-transparent`}
        />
      );
    }

    return (
      <svg
        className={iconSize}
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        strokeWidth={2}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
      </svg>
    );
  };

  const getButton = isIconVariant ? (
    <button
      type="button"
      className={`flex items-center justify-center rounded-full transition-all duration-200 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-hidden ${sizeClass} ${getButtonClasses()} ${anyInLibrary ? '' : className}`.trim()}
      onClick={handleClick}
      disabled={isDisabled}
      style={anyInLibrary ? undefined : style}
      aria-label={`${getDisplayText()} releases for ${book.title}`}
    >
      {renderIcon()}
    </button>
  ) : (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1.5 rounded-sm text-white transition-all duration-200 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-hidden ${sizeClass} ${widthClasses} ${getButtonClasses()} ${anyInLibrary ? '' : className}`.trim()}
      onClick={handleClick}
      disabled={isDisabled}
      style={anyInLibrary ? undefined : style}
      aria-label={`${getDisplayText()} releases for ${book.title}`}
    >
      {renderIcon()}
      <span>{getDisplayText()}</span>
    </button>
  );

  if (!anyInLibrary) {
    return getButton;
  }

  return (
    <div
      className={`flex ${isIconVariant ? 'flex-row items-center' : 'flex-col'} gap-1.5 ${fullWidth ? 'w-full' : ''} ${className}`.trim()}
      style={style}
    >
      {ebookInLibrary && (
        <InLibraryButton
          label="eBook in Library"
          url={libraryUrl}
          tone="ebook"
          isIconVariant={isIconVariant}
          fullWidth={fullWidth}
          size={size}
          className=""
        />
      )}
      {audioInLibrary && (
        <InLibraryButton
          label="AudioBook in Library"
          url={audiobookLibraryUrl}
          tone="audiobook"
          isIconVariant={isIconVariant}
          fullWidth={fullWidth}
          size={size}
          className=""
        />
      )}
      {showGet && getButton}
    </div>
  );
};
